# filepath: skillswap/disputes/routes.py
"""SkillSwap — Dispute Resolution: open, view, resolve."""

from datetime import datetime, timezone
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db
from models import Dispute, Exchange
from skillswap.disputes import disputes_bp
from skillswap.audit import log_action


@disputes_bp.route("/exchange/<int:exchange_id>/open", methods=["GET", "POST"])
@login_required
def open_dispute(exchange_id: int):
    exchange = Exchange.query.get_or_404(exchange_id)
    if current_user.id not in (exchange.proposer_id, exchange.receiver_id):
        abort(403)
    if exchange.status not in ("accepted", "completed"):
        flash("Диспут можна відкрити лише для прийнятого або завершеного обміну.", "warning")
        return redirect(url_for("exchanges.detail", exchange_id=exchange_id))

    existing = Dispute.query.filter(
        Dispute.exchange_id == exchange_id,
        Dispute.status.in_(["open", "under_review"])
    ).first()
    if existing:
        flash("Активний диспут вже існує.", "info")
        return redirect(url_for("disputes.detail", dispute_id=existing.id))

    if request.method == "POST":
        reason      = request.form.get("reason", "other")
        description = request.form.get("description", "").strip()
        if len(description) < 20:
            flash("Опис занадто короткий (мінімум 20 символів).", "warning")
        else:
            dispute = Dispute(
                exchange_id=exchange_id,
                opener_id=current_user.id,
                reason=reason,
                description=description,
                status="open",
            )
            db.session.add(dispute)
            # Transition via state machine
            try:
                from skillswap.exchanges.state_machine import transition
                transition(exchange, "disputed", current_user.id)
            except Exception:
                exchange.status = "disputed"
                exchange.updated_at = datetime.now(timezone.utc)
                db.session.commit()
            log_action("dispute_opened", "exchange", exchange_id,
                       old_value="accepted", new_value="disputed")
            db.session.commit()
            flash("⚠️ Диспут відкрито. Адміністрація розгляне протягом 24 годин.", "warning")
            return redirect(url_for("disputes.detail", dispute_id=dispute.id))

    reasons = list(Dispute.REASONS.items())
    return render_template("disputes/open.html", title="Відкрити диспут",
                           exchange=exchange, reasons=reasons)


@disputes_bp.route("/<int:dispute_id>")
@login_required
def detail(dispute_id: int):
    dispute = Dispute.query.get_or_404(dispute_id)
    ex = dispute.exchange
    if current_user.id not in (ex.proposer_id, ex.receiver_id) \
            and not current_user.is_admin:
        abort(403)
    return render_template("disputes/detail.html",
                           title=f"Диспут #{dispute_id}", dispute=dispute)


@disputes_bp.route("/<int:dispute_id>/resolve", methods=["POST"])
@login_required
def resolve(dispute_id: int):
    """Admin resolves a dispute and applies outcome to exchange."""
    from skillswap.rbac import has_permission
    if not has_permission(current_user, "can_resolve_reports"):
        abort(403)

    dispute  = Dispute.query.get_or_404(dispute_id)
    outcome  = request.form.get("outcome", "")
    note     = request.form.get("note", "").strip()

    if outcome not in ("complete", "cancel", "warn"):
        flash("Оберіть рішення.", "warning")
        return redirect(url_for("disputes.detail", dispute_id=dispute_id))

    dispute.status          = f"resolved_{outcome}"
    dispute.resolution_note = note
    dispute.resolved_by_id  = current_user.id
    dispute.updated_at      = datetime.now(timezone.utc)

    ex = dispute.exchange
    try:
        from skillswap.exchanges.state_machine import transition
        dest = "completed" if outcome in ("complete", "warn") else "cancelled"
        transition(ex, dest, current_user.id, admin_override=True)
    except Exception:
        if outcome == "complete":
            ex.status = "completed"
        elif outcome == "cancel":
            ex.status = "cancelled"
        db.session.commit()

    log_action("dispute_resolved", "dispute", dispute_id,
               old_value="open", new_value=dispute.status,
               actor_id=current_user.id)
    db.session.commit()

    # Notify participants
    try:
        from skillswap.notifications.routes import notify
        outcome_labels = {
            "complete": "✅ Диспут вирішено: обмін завершено.",
            "cancel":   "❌ Диспут вирішено: обмін скасовано.",
            "warn":     "⚠️ Диспут вирішено: попередження.",
        }
        msg = outcome_labels.get(outcome, "Диспут вирішено.")
        for uid in (ex.proposer_id, ex.receiver_id):
            notify(uid, msg, body=note[:80] if note else "",
                   link=url_for("disputes.detail", dispute_id=dispute_id),
                   notif_type="exchange_completed")
        db.session.commit()
    except Exception:
        pass

    flash(f"✅ Диспут #{dispute_id} вирішено.", "success")
    return redirect(url_for("admin.disputes_list"))


@disputes_bp.route("/my")
@login_required
def my_disputes():
    """List disputes opened by or involving current user."""
    from sqlalchemy import or_
    disputes = (
        Dispute.query
        .join(Exchange, Dispute.exchange_id == Exchange.id)
        .filter(or_(
            Exchange.proposer_id == current_user.id,
            Exchange.receiver_id == current_user.id,
        ))
        .order_by(Dispute.created_at.desc())
        .all()
    )
    return render_template("disputes/my_list.html",
                           title="Мої диспути", disputes=disputes)
