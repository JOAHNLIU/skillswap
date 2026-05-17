# filepath: skillswap/reports/routes.py
"""
SkillSwap — Reports Blueprint.
Users can file complaints against other users.
Admins review reports in admin panel.
"""

from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db
from models import User, Report
from forms import ReportForm
from skillswap.reports import reports_bp


@reports_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    """File a report against a user."""
    reported_id = request.args.get("user_id", type=int) or request.form.get("reported_id", type=int)
    if not reported_id:
        abort(400)

    reported_user = User.query.get_or_404(reported_id)

    if reported_user.id == current_user.id:
        flash("Не можна подати жалобу на себе.", "warning")
        return redirect(url_for("users.profile", user_id=reported_id))

    # Check if already reported (pending)
    existing = Report.query.filter_by(
        reporter_id=current_user.id,
        reported_id=reported_id,
        status="pending",
    ).first()
    if existing:
        flash("Ви вже подали жалобу на цього користувача. Вона на розгляді.", "info")
        return redirect(url_for("users.profile", user_id=reported_id))

    form = ReportForm()
    form.reported_id.data = reported_id

    if form.validate_on_submit():
        report = Report(
            reporter_id=current_user.id,
            reported_id=int(form.reported_id.data),
            reason=form.reason.data,
            description=form.description.data.strip(),
            status="pending",
        )
        db.session.add(report)
        db.session.commit()
        flash("Жалобу подано. Адміністрація розгляне її найближчим часом.", "success")
        return redirect(url_for("users.profile", user_id=reported_id))

    return render_template(
        "reports/create.html",
        title="Подати жалобу",
        form=form,
        reported_user=reported_user,
    )
