# filepath: skillswap/users/routes.py
"""
SkillSwap — Users Blueprint: public profiles, profile editing, account deletion.
"""

import os
import uuid
from collections import Counter

from flask import render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user, logout_user
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from extensions import db
from forms import ProfileEditForm
from models import (
    ActivityEvent,
    AuditLog,
    BannedUser,
    Dispute,
    Endorsement,
    Exchange,
    ExchangeAgreement,
    GlobalReview,
    Message,
    Notification,
    Report,
    Review,
    Session,
    Skill,
    SkillTrustScore,
    SupportTicket,
    User,
    Webhook,
    user_badges,
    user_roles,
)
from skillswap.skills.matching import compute_match_score
from skillswap.users import users_bp


def _save_avatar(file_storage) -> str:
    """Save avatar file and return URL path."""
    folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    ext = secure_filename(file_storage.filename).rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(folder, filename)
    file_storage.save(path)
    return f"/static/uploads/avatars/{filename}"


def _delete_local_avatar(avatar_url: str) -> None:
    """Delete local avatar file if it belongs to this project."""
    if not avatar_url or not avatar_url.startswith("/static/uploads/avatars/"):
        return

    filename = os.path.basename(avatar_url)
    if not filename or filename == ".gitkeep":
        return

    folder = current_app.config.get("UPLOAD_FOLDER", "skillswap/static/uploads/avatars")
    path = os.path.join(folder, filename)

    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        current_app.logger.warning("Could not delete avatar file: %s", path)


def _delete_current_user_account(user: User) -> None:
    """
    Permanently remove the current user's account and dependent records.

    The project has many optional modules. This helper deletes records in a safe
    order so database foreign keys do not block deletion. Audit rows are kept,
    but actor_id is anonymized because AuditLog.actor_id is nullable.
    """
    user_id = user.id
    avatar_url = user.avatar_url

    user_exchange_ids = [
        row[0]
        for row in db.session.query(Exchange.id)
        .filter(or_(Exchange.proposer_id == user_id, Exchange.receiver_id == user_id))
        .all()
    ]

    user_skill_ids = [
        row[0]
        for row in db.session.query(Skill.id)
        .filter(Skill.user_id == user_id)
        .all()
    ]

    if user_exchange_ids:
        ExchangeAgreement.query.filter(ExchangeAgreement.exchange_id.in_(user_exchange_ids)).delete(synchronize_session=False)
        Dispute.query.filter(Dispute.exchange_id.in_(user_exchange_ids)).delete(synchronize_session=False)
        Review.query.filter(Review.exchange_id.in_(user_exchange_ids)).delete(synchronize_session=False)
        Session.query.filter(Session.exchange_id.in_(user_exchange_ids)).delete(synchronize_session=False)
        Message.query.filter(Message.exchange_id.in_(user_exchange_ids)).delete(synchronize_session=False)
        Exchange.query.filter(Exchange.id.in_(user_exchange_ids)).delete(synchronize_session=False)

    if user_skill_ids:
        Endorsement.query.filter(Endorsement.skill_id.in_(user_skill_ids)).delete(synchronize_session=False)
        SkillTrustScore.query.filter(SkillTrustScore.skill_id.in_(user_skill_ids)).delete(synchronize_session=False)
        Skill.query.filter(Skill.id.in_(user_skill_ids)).delete(synchronize_session=False)

    Endorsement.query.filter(Endorsement.endorser_id == user_id).delete(synchronize_session=False)
    Review.query.filter(or_(Review.reviewer_id == user_id, Review.reviewee_id == user_id)).delete(synchronize_session=False)
    Message.query.filter(Message.sender_id == user_id).delete(synchronize_session=False)
    Notification.query.filter(Notification.user_id == user_id).delete(synchronize_session=False)
    GlobalReview.query.filter(GlobalReview.author_id == user_id).delete(synchronize_session=False)
    Report.query.filter(or_(Report.reporter_id == user_id, Report.reported_id == user_id)).delete(synchronize_session=False)
    BannedUser.query.filter(or_(BannedUser.user_id == user_id, BannedUser.banned_by_id == user_id)).delete(synchronize_session=False)
    ActivityEvent.query.filter(ActivityEvent.actor_id == user_id).delete(synchronize_session=False)
    SupportTicket.query.filter(SupportTicket.user_id == user_id).delete(synchronize_session=False)
    Webhook.query.filter(Webhook.user_id == user_id).delete(synchronize_session=False)

    Dispute.query.filter(Dispute.opener_id == user_id).delete(synchronize_session=False)
    Dispute.query.filter(Dispute.resolved_by_id == user_id).update(
        {Dispute.resolved_by_id: None},
        synchronize_session=False,
    )
    AuditLog.query.filter(AuditLog.actor_id == user_id).update(
        {AuditLog.actor_id: None},
        synchronize_session=False,
    )

    db.session.execute(user_badges.delete().where(user_badges.c.user_id == user_id))
    db.session.execute(user_roles.delete().where(user_roles.c.user_id == user_id))

    db.session.delete(user)
    db.session.commit()

    _delete_local_avatar(avatar_url)


@users_bp.route("/<int:user_id>")
@login_required
def profile(user_id: int):
    """Public profile page."""
    user = User.query.get_or_404(user_id)

    match_score = 0
    if current_user.id != user.id:
        match_score = compute_match_score(current_user, user)
        try:
            user.profile_views = (user.profile_views or 0) + 1
            db.session.commit()
        except Exception:
            db.session.rollback()

    offer_skills = user.skills.filter_by(skill_type="offer").all()
    want_skills = user.skills.filter_by(skill_type="want").all()
    reviews = (
        Review.query.filter_by(reviewee_id=user.id)
        .order_by(Review.created_at.desc())
        .limit(10)
        .all()
    )
    badges = user.badges.all()
    pending_reports = user.pending_reports_count()

    total_ex = Exchange.query.filter(
        (Exchange.proposer_id == user.id) | (Exchange.receiver_id == user.id)
    ).count()
    completed_ex = Exchange.query.filter(
        ((Exchange.proposer_id == user.id) | (Exchange.receiver_id == user.id)),
        Exchange.status == "completed",
    ).count()
    rejected_ex = Exchange.query.filter(
        ((Exchange.proposer_id == user.id) | (Exchange.receiver_id == user.id)),
        Exchange.status == "rejected",
    ).count()
    pending_ex = Exchange.query.filter(
        ((Exchange.proposer_id == user.id) | (Exchange.receiver_id == user.id)),
        Exchange.status == "pending",
    ).count()
    exchange_stats = {
        "total": total_ex,
        "completed": completed_ex,
        "rejected": rejected_ex,
        "pending": pending_ex,
        "success_rate": int(completed_ex / total_ex * 100) if total_ex > 0 else 0,
    }

    all_skills = user.skills.all()
    cat_counts = Counter(s.category for s in all_skills if s.category)
    top_categories = cat_counts.most_common(3)

    return render_template(
        "users/profile.html",
        title=user.full_name or user.email,
        profile_user=user,
        offer_skills=offer_skills,
        want_skills=want_skills,
        reviews=reviews,
        badges=badges,
        match_score=match_score,
        is_own=current_user.id == user.id,
        pending_reports=pending_reports,
        exchange_stats=exchange_stats,
        top_categories=top_categories,
    )


@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
def edit(user_id: int):
    """Edit own profile."""
    user = User.query.get_or_404(user_id)
    if user.id != current_user.id:
        abort(403)

    form = ProfileEditForm(obj=user)
    if form.validate_on_submit():
        user.full_name = form.full_name.data.strip()
        user.age = form.age.data
        user.gender = form.gender.data
        user.city = form.city.data.strip() if form.city.data else ""
        user.bio = form.bio.data.strip() if form.bio.data else ""
        user.available_from = form.available_from.data
        user.available_to = form.available_to.data

        if form.avatar.data:
            _delete_local_avatar(user.avatar_url)
            user.avatar_url = _save_avatar(form.avatar.data)

        db.session.commit()
        flash("Профіль оновлено!", "success")
        return redirect(url_for("users.profile", user_id=user.id))

    if request.method == "GET":
        form.available_from.data = user.available_from or "09:00"
        form.available_to.data = user.available_to or "21:00"

    return render_template(
        "users/edit.html",
        title="Редагувати профіль",
        form=form,
        profile_user=user,
    )


@users_bp.route("/<int:user_id>/delete-account", methods=["POST"])
@login_required
def delete_account(user_id: int):
    """Allow a user to permanently delete only their own account."""
    user = User.query.get_or_404(user_id)
    if user.id != current_user.id:
        abort(403)

    confirmation = request.form.get("confirm_delete", "").strip()
    if confirmation != "DELETE":
        flash("Акаунт не видалено. Для підтвердження потрібно ввести DELETE.", "danger")
        return redirect(url_for("users.profile", user_id=user.id))

    email_for_message = user.email

    try:
        logout_user()
        _delete_current_user_account(user)
        flash(f"Акаунт {email_for_message} видалено назавжди.", "success")
        return redirect(url_for("main.index"))
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("Account deletion failed for user_id=%s", user_id)
        flash(f"Не вдалося видалити акаунт: {exc}", "danger")
        return redirect(url_for("users.profile", user_id=user_id))


@users_bp.route("/")
@login_required
def list_users():
    """Browse all users."""
    q = request.args.get("q", "").strip()
    city = request.args.get("city", "").strip()

    banned_ids = db.session.query(BannedUser.user_id).scalar_subquery()
    query = User.query.filter(
        User.id != current_user.id,
        User.onboarding_done == True,
        ~User.id.in_(banned_ids),
    )
    if q:
        query = query.filter(
            (User.full_name.ilike(f"%{q}%")) | (User.bio.ilike(f"%{q}%"))
        )
    if city:
        query = query.filter(User.city.ilike(f"%{city}%"))

    users = query.order_by(User.rating_points.desc()).all()
    user_cards = [
        {"user": u, "match_score": compute_match_score(current_user, u)}
        for u in users
    ]
    user_cards.sort(key=lambda x: x["match_score"], reverse=True)

    return render_template(
        "users/list.html",
        title="Користувачі",
        user_cards=user_cards,
        q=q,
        city=city,
    )


@users_bp.route("/compare")
@login_required
def compare():
    """Compare two user profiles side by side."""
    id_a = request.args.get("a", type=int)
    id_b = request.args.get("b", type=int)
    if not id_a or not id_b:
        flash("Вкажи двох користувачів для порівняння (?a=ID&b=ID).", "warning")
        return redirect(url_for("users.list_users"))

    user_a = User.query.get_or_404(id_a)
    user_b = User.query.get_or_404(id_b)

    def _stats(u):
        total = Exchange.query.filter(
            (Exchange.proposer_id == u.id) | (Exchange.receiver_id == u.id)
        ).count()
        completed = Exchange.query.filter(
            ((Exchange.proposer_id == u.id) | (Exchange.receiver_id == u.id)),
            Exchange.status == "completed",
        ).count()
        return {
            "total": total,
            "completed": completed,
            "skills": u.skills.count(),
            "rating": u.rating_points,
        }

    return render_template(
        "users/compare.html",
        title="Порівняння профілів",
        user_a=user_a,
        user_b=user_b,
        stats_a=_stats(user_a),
        stats_b=_stats(user_b),
    )


@users_bp.route("/<int:user_id>/preview")
@login_required
def preview(user_id: int):
    """Preview own profile as others see it."""
    if user_id != current_user.id and not current_user.is_admin:
        return redirect(url_for("users.profile", user_id=user_id))

    user = User.query.get_or_404(user_id)
    offer_skills = user.skills.filter_by(skill_type="offer").all()
    want_skills = user.skills.filter_by(skill_type="want").all()
    reviews = Review.query.filter_by(reviewee_id=user.id).limit(5).all()
    badges = user.badges.all()

    return render_template(
        "users/profile.html",
        title=f"Перегляд профілю — {user.full_name or user.email}",
        profile_user=user,
        offer_skills=offer_skills,
        want_skills=want_skills,
        reviews=reviews,
        badges=badges,
        match_score=0,
        is_own=False,
        pending_reports=0,
        exchange_stats={"total": 0, "completed": 0, "rejected": 0, "pending": 0, "success_rate": 0},
        top_categories=[],
        preview_mode=True,
    )
