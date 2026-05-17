# filepath: skillswap/support/routes.py
"""SkillSwap — Support Ticket Blueprint."""

from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db
from models import SupportTicket
from skillswap.support import support_bp


@support_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    """List user's support tickets + create new."""
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        body = request.form.get("body", "").strip()
        if not subject or not body:
            flash("Заповніть всі поля.", "warning")
        elif len(subject) > 200:
            flash("Тема занадто довга (макс. 200 символів).", "warning")
        else:
            ticket = SupportTicket(
                user_id=current_user.id,
                subject=subject,
                body=body,
                status="open",
            )
            db.session.add(ticket)
            db.session.commit()
            flash("✅ Тікет створено! Адміністрація відповість найближчим часом.", "success")
            return redirect(url_for("support.index"))

    tickets = (
        SupportTicket.query
        .filter_by(user_id=current_user.id)
        .order_by(SupportTicket.created_at.desc())
        .all()
    )
    return render_template("support/index.html", title="Підтримка", tickets=tickets)


@support_bp.route("/<int:ticket_id>")
@login_required
def detail(ticket_id: int):
    """View a single ticket."""
    ticket = SupportTicket.query.get_or_404(ticket_id)
    if ticket.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return render_template("support/detail.html", title=f"Тікет #{ticket_id}", ticket=ticket)
