# filepath: skillswap/exchanges/session_routes.py
"""SkillSwap — Full Session Lifecycle (confirm, mark-done, mark-missed, cancel)."""

from datetime import datetime, timezone
from flask import redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db
from models import Session, Exchange, Dispute
from skillswap.exchanges import exchanges_bp
from skillswap.audit import log_action


def _load(session_id: int):
    session = Session.query.get_or_404(session_id)
    ex = session.exchange
    if current_user.id not in (ex.proposer_id, ex.receiver_id):
        abort(403)
    return session, ex


@exchanges_bp.route("/sessions/<int:session_id>/confirm", methods=["POST"])
@login_required
def confirm_session(session_id: int):
    session, ex = _load(session_id)
    if session.status not in ("proposed", "confirmed"):
        flash("Не можна підтвердити в поточному статусі.", "warning")
        return redirect(url_for("exchanges.detail", exchange_id=ex.id))
    now = datetime.now(timezone.utc)
    is_prop = current_user.id == ex.proposer_id
    if is_prop and not session.proposer_confirmed_at:
        session.proposer_confirmed_at = now
    elif not is_prop and not session.receiver_confirmed_at:
        session.receiver_confirmed_at = now
    else:
        flash("Ви вже підтвердили участь.", "info")
        return redirect(url_for("exchanges.detail", exchange_id=ex.id))
    if session.proposer_confirmed_at and session.receiver_confirmed_at:
        session.status = "confirmed"
        try:
            from skillswap.notifications.routes import notify
            other = ex.receiver_id if is_prop else ex.proposer_id
            notify(other, "✅ Обидва підтвердили участь у сесії!",
                   link=url_for("exchanges.detail", exchange_id=ex.id))
        except Exception:
            pass
    log_action("session_confirmed", "session", session_id, new_value=current_user.email)
    db.session.commit()
    flash("✅ Участь підтверджено!", "success")
    return redirect(url_for("exchanges.detail", exchange_id=ex.id))


@exchanges_bp.route("/sessions/<int:session_id>/mark-done", methods=["POST"])
@login_required
def mark_session_done(session_id: int):
    session, ex = _load(session_id)
    if session.status in ("cancelled", "completed"):
        flash("Сесія вже має фінальний статус.", "warning")
        return redirect(url_for("exchanges.detail", exchange_id=ex.id))
    now = datetime.now(timezone.utc)
    is_prop = current_user.id == ex.proposer_id
    if is_prop:
        session.proposer_completed_at = now
        session.proposer_marked_missed = False
    else:
        session.receiver_completed_at = now
        session.receiver_marked_missed = False
    # Conflict: one says done, other says missed
    p_missed = session.proposer_marked_missed
    r_missed = session.receiver_marked_missed
    if p_missed is not None and r_missed is not None and p_missed != r_missed:
        session.status = "missed"
        _auto_dispute(session, ex)
        flash("⚠️ Конфлікт! Відкрито диспут автоматично.", "danger")
    elif session.proposer_completed_at and session.receiver_completed_at:
        session.status = "completed"
        flash("🏁 Сесія завершена обома учасниками!", "success")
        try:
            from skillswap.notifications.routes import notify
            other = ex.receiver_id if is_prop else ex.proposer_id
            notify(other, "🏁 Обидва підтвердили завершення сесії!",
                   link=url_for("exchanges.detail", exchange_id=ex.id))
        except Exception:
            pass
    else:
        session.status = "in_progress"
        flash("✅ Збережено. Очікуємо підтвердження партнера.", "info")
        try:
            from skillswap.notifications.routes import notify
            other = ex.receiver_id if is_prop else ex.proposer_id
            notify(other, "⏳ Партнер позначив сесію як завершену — підтвердіть свій статус.",
                   link=url_for("exchanges.detail", exchange_id=ex.id))
        except Exception:
            pass
    log_action("session_mark_done", "session", session_id, new_value=current_user.email)
    db.session.commit()
    return redirect(url_for("exchanges.detail", exchange_id=ex.id))


@exchanges_bp.route("/sessions/<int:session_id>/mark-missed", methods=["POST"])
@login_required
def mark_session_missed(session_id: int):
    session, ex = _load(session_id)
    if session.status in ("cancelled", "completed"):
        flash("Сесія вже має фінальний статус.", "warning")
        return redirect(url_for("exchanges.detail", exchange_id=ex.id))
    is_prop = current_user.id == ex.proposer_id
    if is_prop:
        session.proposer_marked_missed = True
    else:
        session.receiver_marked_missed = True
    # Both say missed
    if session.proposer_marked_missed and session.receiver_marked_missed:
        session.status = "missed"
        flash("Сесія позначена як що не відбулась.", "warning")
    # Conflict
    elif (session.proposer_marked_missed is not None and
          session.receiver_marked_missed is not None and
          session.proposer_marked_missed != session.receiver_marked_missed):
        session.status = "missed"
        _auto_dispute(session, ex)
        flash("⚠️ Конфлікт зафіксовано. Відкрито диспут.", "danger")
    else:
        session.status = "in_progress"
        flash("⚠️ Статус збережено. Очікуємо відповіді партнера.", "warning")
        try:
            from skillswap.notifications.routes import notify
            other = ex.receiver_id if is_prop else ex.proposer_id
            notify(other, "⚠️ Партнер каже що сесія не відбулась — підтвердіть ваш статус.",
                   link=url_for("exchanges.detail", exchange_id=ex.id))
        except Exception:
            pass
    log_action("session_mark_missed", "session", session_id, new_value=current_user.email)
    db.session.commit()
    return redirect(url_for("exchanges.detail", exchange_id=ex.id))


@exchanges_bp.route("/sessions/<int:session_id>/cancel", methods=["POST"])
@login_required
def cancel_session(session_id: int):
    session, ex = _load(session_id)
    if session.status in ("completed", "cancelled"):
        flash("Цю сесію не можна скасувати.", "warning")
        return redirect(url_for("exchanges.detail", exchange_id=ex.id))
    session.status = "cancelled"
    try:
        from skillswap.notifications.routes import notify
        is_prop = current_user.id == ex.proposer_id
        other = ex.receiver_id if is_prop else ex.proposer_id
        notify(other, "❌ Сесію скасовано партнером.",
               link=url_for("exchanges.detail", exchange_id=ex.id))
    except Exception:
        pass
    log_action("session_cancelled", "session", session_id, new_value=current_user.email)
    db.session.commit()
    flash("Сесію скасовано.", "warning")
    return redirect(url_for("exchanges.detail", exchange_id=ex.id))


def _auto_dispute(session: Session, ex: Exchange) -> None:
    try:
        existing = Dispute.query.filter(
            Dispute.exchange_id == ex.id,
            Dispute.status.in_(["open", "under_review"])
        ).first()
        if not existing:
            d = Dispute(exchange_id=ex.id, opener_id=ex.proposer_id,
                        reason="no_show",
                        description="Автоматично відкрито: учасники не погоджуються щодо сесії.",
                        status="open")
            db.session.add(d)
            ex.status = "disputed"
    except Exception:
        pass
