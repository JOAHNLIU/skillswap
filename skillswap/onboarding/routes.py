# filepath: skillswap/onboarding/routes.py
"""
SkillSwap — Onboarding Blueprint.
Step 1: required profile fields. Step 2: at least one offered and one wanted skill.
"""

import os
import uuid
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from extensions import db
from models import User, Skill, Badge
from forms import OnboardingForm, CATEGORY_CHOICES, LEVEL_CHOICES, SKILLS_BY_CATEGORY
from skillswap.onboarding import onboarding_bp


def _save_avatar(file_storage) -> str:
    """Save uploaded avatar and return relative URL."""
    folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    ext = secure_filename(file_storage.filename).rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(folder, filename)
    file_storage.save(path)
    return f"/static/uploads/avatars/{filename}"


def _profile_is_filled(user: User) -> bool:
    """Basic onboarding profile completeness: bio is intentionally optional."""
    return bool(
        user.full_name and user.age and user.gender and user.city
        and user.available_from and user.available_to
    )


def _has_required_skills(user: User) -> bool:
    return bool(user.get_skills_offer()) and bool(user.get_skills_want())


@onboarding_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Onboarding step 1: fill required profile data. Skills are added on the next page."""
    user: User = current_user
    form = OnboardingForm(obj=user)

    if request.method == "GET":
        form.available_from.data = user.available_from or "09:00"
        form.available_to.data = user.available_to or "21:00"

    if form.validate_on_submit():
        user.full_name = form.full_name.data.strip()
        user.age = form.age.data
        user.gender = form.gender.data
        user.city = form.city.data.strip()
        user.bio = form.bio.data.strip() if form.bio.data else ""
        user.available_from = form.available_from.data
        user.available_to = form.available_to.data

        if form.avatar.data:
            user.avatar_url = _save_avatar(form.avatar.data)

        # Do not mark onboarding as done here. The user must add skills first.
        user.onboarding_done = _has_required_skills(user)
        db.session.commit()
        flash("Профіль збережено. Тепер додайте навички для роботи з системою.", "success")
        return redirect(url_for("onboarding.skills_setup"))

    return render_template(
        "onboarding/profile.html",
        form=form,
        title="Налаштування профілю",
    )


@onboarding_bp.route("/skills", methods=["GET", "POST"])
@login_required
def skills_setup():
    """Onboarding step 2: user must add at least one offered and one wanted skill."""
    user: User = current_user
    if not _profile_is_filled(user):
        flash("Спочатку заповніть обов’язкові дані профілю.", "warning")
        return redirect(url_for("onboarding.profile"))

    if request.method == "POST":
        _process_skills_from_request(user)
        db.session.flush()
        if not _has_required_skills(user):
            db.session.commit()
            flash("Для функціонування з системою потрібно додати мінімум одну навичку, яку ви надаєте, і мінімум одну навичку, яку шукаєте.", "danger")
            return redirect(url_for("onboarding.skills_setup"))
        user.onboarding_done = True
        db.session.commit()
        _maybe_award_badge(user)
        flash("Навички збережено. Тепер вам доступна вся система SkillSwap.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template(
        "onboarding/skills.html",
        title="Мої навички",
        categories=CATEGORY_CHOICES,
        levels=LEVEL_CHOICES,
        skills_by_category=SKILLS_BY_CATEGORY,
        offer_skills=user.get_skills_offer(),
        want_skills=user.get_skills_want(),
    )


def _process_skills_from_request(user: User) -> None:
    """Parse skill lists from POST request and persist them."""
    for skill_type in ("offer", "want"):
        raw_list = request.form.getlist(f"skills_{skill_type}[]")
        for raw in raw_list:
            parts = raw.split("|")
            if len(parts) >= 1 and parts[0].strip():
                title = parts[0].strip()
                category = parts[1].strip() if len(parts) > 1 else "Інше"
                level = parts[2].strip() if len(parts) > 2 else "beginner"
                exists = Skill.query.filter_by(
                    user_id=user.id,
                    title=title,
                    skill_type=skill_type,
                ).first()
                if not exists:
                    db.session.add(
                        Skill(
                            title=title,
                            category=category,
                            level=level,
                            skill_type=skill_type,
                            user_id=user.id,
                        )
                    )


def _maybe_award_badge(user: User) -> None:
    """Award badges based on current state."""
    badge_slugs = {b.slug for b in user.badges.all()}
    if user.skills.count() > 0 and "first_skill" not in badge_slugs:
        badge = Badge.query.filter_by(slug="first_skill").first()
        if badge:
            user.badges.append(badge)
            db.session.commit()
            flash(f"🏅 Ви отримали значок «{badge.name}»!", "info")
