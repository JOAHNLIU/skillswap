# filepath: skillswap/skills/routes.py
"""
SkillSwap — Skills Blueprint: list/search, create, edit, delete.
Includes pagination and cached match scores.
"""

from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db
from models import User, Skill
from forms import SkillForm, SearchFilterForm
from skillswap.skills import skills_bp
from skillswap.skills.matching import compute_match_score


@skills_bp.route("/", methods=["GET"])
@login_required
def index():
    form = SearchFilterForm(request.args)
    from models import BannedUser
    banned_ids = db.session.query(BannedUser.user_id).scalar_subquery()
    query = Skill.query.join(User).filter(
        User.id != current_user.id,
        ~User.id.in_(banned_ids)
    )

    q = request.args.get("q", "").strip()
    if q:
        # Full-text search: split query into tokens, match any token
        tokens = [t for t in q.split() if len(t) >= 2]
        if tokens:
            from sqlalchemy import or_
            conditions = [
                or_(
                    Skill.title.ilike(f"%{t}%"),
                    Skill.description.ilike(f"%{t}%"),
                    Skill.category.ilike(f"%{t}%"),
                )
                for t in tokens
            ]
            query = query.filter(or_(*conditions))

    category = request.args.get("category", "")
    if category:
        query = query.filter(Skill.category == category)

    level = request.args.get("level", "")
    if level:
        query = query.filter(Skill.level == level)

    skill_type = request.args.get("skill_type", "")
    if skill_type:
        query = query.filter(Skill.skill_type == skill_type)

    city = request.args.get("city", "").strip()
    if city:
        query = query.filter(User.city.ilike(f"%{city}%"))

    gender = request.args.get("gender", "")
    if gender:
        query = query.filter(User.gender == gender)

    age_min = request.args.get("age_min", type=int)
    age_max = request.args.get("age_max", type=int)
    if age_min:
        query = query.filter(User.age >= age_min)
    if age_max:
        query = query.filter(User.age <= age_max)

    min_rating = request.args.get("min_rating", type=float)
    if min_rating:
        query = query.filter(User.rating_points >= min_rating)

    min_reviews = request.args.get("min_reviews", type=int)
    if min_reviews:
        query = query.filter(User.review_count >= min_reviews)

    skills = query.order_by(Skill.created_at.desc()).all()

    # Build unique user cards with match score
    seen_user_ids = set()
    user_cards = []
    for skill in skills:
        if skill.user_id not in seen_user_ids:
            seen_user_ids.add(skill.user_id)
            score = compute_match_score(current_user, skill.user)
            user_cards.append({"user": skill.user, "match_score": score})

    user_cards.sort(key=lambda x: x["match_score"], reverse=True)

    # Manual pagination over user_cards
    page = request.args.get("page", 1, type=int)
    per_page = 12
    total = len(user_cards)
    start = (page - 1) * per_page
    end = start + per_page
    paged_cards = user_cards[start:end]
    total_pages = (total + per_page - 1) // per_page

    return render_template(
        "skills/index.html",
        title="Пошук навичок",
        form=form,
        user_cards=paged_cards,
        total=total,
        page=page,
        total_pages=total_pages,
    )


@skills_bp.route("/my")
@login_required
def my_skills():
    offer_skills = current_user.skills.filter_by(skill_type="offer").order_by(Skill.created_at.desc()).all()
    want_skills = current_user.skills.filter_by(skill_type="want").order_by(Skill.created_at.desc()).all()
    return render_template(
        "skills/my_skills.html",
        title="Мої навички",
        offer_skills=offer_skills,
        want_skills=want_skills,
    )


@skills_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    form = SkillForm()
    if form.validate_on_submit():
        skill = Skill(
            title=form.title.data.strip(),
            description=form.description.data.strip() if form.description.data else "",
            category=form.category.data,
            subcategory=form.subcategory.data.strip() if form.subcategory.data else "",
            level=form.level.data,
            skill_type=form.skill_type.data,
            user_id=current_user.id,
        )
        db.session.add(skill)
        db.session.commit()
        from skillswap.onboarding.routes import _maybe_award_badge
        _maybe_award_badge(current_user)
        from skillswap.activity import log_activity
        log_activity(current_user.id, "skill_added", skill.id, skill.title)
        db.session.commit()
        flash("Навичку додано!", "success")
        return redirect(url_for("skills.my_skills"))

    from forms import SKILLS_BY_CATEGORY
    return render_template("skills/form.html", form=form, title="Додати навичку",
                           action="create", skills_by_category=SKILLS_BY_CATEGORY)


@skills_bp.route("/<int:skill_id>/edit", methods=["GET", "POST"])
@login_required
def edit(skill_id: int):
    skill = Skill.query.get_or_404(skill_id)
    if skill.user_id != current_user.id:
        abort(403)

    form = SkillForm(obj=skill)
    if form.validate_on_submit():
        skill.title = form.title.data.strip()
        skill.description = form.description.data.strip() if form.description.data else ""
        skill.category = form.category.data
        skill.subcategory = form.subcategory.data.strip() if form.subcategory.data else ""
        skill.level = form.level.data
        skill.skill_type = form.skill_type.data
        db.session.commit()
        flash("Навичку оновлено!", "success")
        return redirect(url_for("skills.my_skills"))

    from forms import SKILLS_BY_CATEGORY
    return render_template("skills/form.html", form=form, title="Редагувати навичку",
                           action="edit", skill=skill, skills_by_category=SKILLS_BY_CATEGORY)


@skills_bp.route("/<int:skill_id>/delete", methods=["POST"])
@login_required
def delete(skill_id: int):
    skill = Skill.query.get_or_404(skill_id)
    if skill.user_id != current_user.id:
        abort(403)
    db.session.delete(skill)
    db.session.commit()
    flash("Навичку видалено.", "warning")
    return redirect(url_for("skills.my_skills"))


@skills_bp.route("/<int:skill_id>")
@login_required
def detail(skill_id: int):
    skill = Skill.query.get_or_404(skill_id)
    return render_template("skills/detail.html", skill=skill, title=skill.title)
