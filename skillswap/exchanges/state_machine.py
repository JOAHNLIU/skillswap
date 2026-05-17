# filepath: skillswap/exchanges/state_machine.py
"""
SkillSwap — Exchange State Machine.

Valid states:   pending → accepted → completed
                pending → rejected
                accepted → disputed
                disputed → completed | cancelled
                any → cancelled  (admin only)

Each transition:
  - checks who is allowed to trigger it
  - updates exchange.status in DB
  - writes an AuditLog entry
  - fires post-transition side-effects (notification, rating update)
"""
from __future__ import annotations
from datetime import datetime, timezone


VALID_TRANSITIONS: dict[str, list[str]] = {
    "pending":   ["accepted", "rejected", "cancelled"],
    "accepted":  ["completed", "disputed", "cancelled"],
    "disputed":  ["completed", "cancelled"],
    "completed": [],
    "rejected":  [],
    "cancelled": [],
}

ACTOR_RULES: dict[str, str] = {
    # trigger-name → who: "receiver" | "participant" | "admin"
    "accepted":  "receiver",
    "rejected":  "receiver",
    "completed": "participant",
    "disputed":  "participant",
    "cancelled": "admin",
}


class InvalidTransitionError(Exception):
    pass


class PermissionError(Exception):
    pass


def transition(exchange, new_status: str, actor_id: int,
               admin_override: bool = False) -> None:
    """
    Transition `exchange` to `new_status`.

    Raises:
        InvalidTransitionError  — if the transition is not allowed from current status.
        PermissionError         — if actor is not allowed to trigger this transition.
    """
    from extensions import db
    from skillswap.audit import log_action

    current = exchange.status

    # Validate transition
    if new_status not in VALID_TRANSITIONS.get(current, []):
        raise InvalidTransitionError(
            f"Cannot move exchange from '{current}' to '{new_status}'"
        )

    # Check actor permission
    if not admin_override:
        rule = ACTOR_RULES.get(new_status, "participant")
        if rule == "receiver" and actor_id != exchange.receiver_id:
            raise PermissionError("Only receiver can perform this transition")
        if rule == "participant" and actor_id not in (exchange.proposer_id,
                                                       exchange.receiver_id):
            raise PermissionError("Only participants can perform this transition")
        if rule == "admin":
            from models import User
            actor = db.session.get(User, actor_id)
            if not actor or not actor.is_admin:
                raise PermissionError("Admin only transition")

    old_status = exchange.status
    exchange.status = new_status
    exchange.updated_at = datetime.now(timezone.utc)

    # Audit
    log_action(f"exchange_transition_{new_status}",
               target_type="exchange",
               target_id=exchange.id,
               old_value=old_status,
               new_value=new_status,
               actor_id=actor_id)

    db.session.commit()

    # Post-effects
    _post_effects(exchange, old_status, new_status, actor_id)


def _post_effects(exchange, old_status: str,
                  new_status: str, actor_id: int) -> None:
    """Side-effects after a successful transition."""
    from extensions import db
    from models import User

    if new_status == "completed":
        for uid in (exchange.proposer_id, exchange.receiver_id):
            u = db.session.get(User, uid)
            if u:
                u.recalculate_rating()
        db.session.commit()

    # Notification to the other participant
    try:
        from skillswap.notifications.routes import notify
        labels = {
            "accepted":  "✅ Обмін прийнято!",
            "rejected":  "❌ Обмін відхилено.",
            "completed": "🏁 Обмін завершено!",
            "disputed":  "⚠️ Відкрито диспут.",
            "cancelled": "🚫 Обмін скасовано.",
        }
        msg = labels.get(new_status, f"Статус змінено: {new_status}")
        other_id = (exchange.receiver_id
                    if actor_id == exchange.proposer_id
                    else exchange.proposer_id)
        from flask import url_for
        notify(other_id, msg,
               link=url_for("exchanges.detail", exchange_id=exchange.id),
               notif_type=f"exchange_{new_status}")
        db.session.commit()
    except Exception:
        pass


def allowed_transitions(exchange, actor_id: int, is_admin: bool = False) -> list[str]:
    """Return the list of statuses the actor can transition to from current state."""
    result = []
    for new_status in VALID_TRANSITIONS.get(exchange.status, []):
        try:
            rule = ACTOR_RULES.get(new_status, "participant")
            if rule == "receiver" and actor_id != exchange.receiver_id:
                continue
            if rule == "participant" and actor_id not in (exchange.proposer_id,
                                                           exchange.receiver_id):
                continue
            if rule == "admin" and not is_admin:
                continue
            result.append(new_status)
        except Exception:
            pass
    return result
