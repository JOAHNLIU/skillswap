# filepath: skillswap/reviews/routes.py
"""
SkillSwap — Reviews Blueprint.
Public wall of all GlobalReviews. Create, filter by category, delete own.
"""

from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db
from models import GlobalReview
from forms import GlobalReviewForm
from skillswap.reviews import reviews_bp


@reviews_bp.route("/", methods=["GET", "POST"])
@login_required
def wall():
    """Review wall — all global reviews with category filter."""
    form = GlobalReviewForm()
    category_filter = request.args.get("category", "")
    page = request.args.get("page", 1, type=int)

    if form.validate_on_submit():
        mentioned_un = (form.mentioned_username.data or "").lstrip("@").lower().strip()
        rev = GlobalReview(
            author_id=current_user.id,
            category=form.category.data,
            rating=form.rating.data,
            title=form.title.data.strip() if form.title.data else "",
            body=form.body.data.strip(),
            is_visible=True,
            mentioned_username=mentioned_un if mentioned_un else None,
        )
        db.session.add(rev)
        db.session.commit()
        flash("Відгук опубліковано! ✅", "success")
        return redirect(url_for("reviews.wall"))

    query = GlobalReview.query.filter_by(is_visible=True)
    if category_filter:
        query = query.filter_by(category=category_filter)

    pagination = query.order_by(GlobalReview.created_at.desc()).paginate(
        page=page, per_page=15, error_out=False
    )

    # Stats
    stats = {}
    for cat in ("app", "user", "exchange"):
        count = GlobalReview.query.filter_by(category=cat, is_visible=True).count()
        stats[cat] = count

    avg_rating = db.session.query(
        db.func.avg(GlobalReview.rating)
    ).filter_by(is_visible=True).scalar() or 0

    return render_template(
        "reviews/wall.html",
        title="Відгуки",
        form=form,
        pagination=pagination,
        reviews=pagination.items,
        category_filter=category_filter,
        stats=stats,
        avg_rating=round(avg_rating, 1),
    )


@reviews_bp.route("/<int:review_id>/delete", methods=["POST"])
@login_required
def delete(review_id: int):
    """Delete own review or admin deletes any."""
    rev = GlobalReview.query.get_or_404(review_id)
    if rev.author_id != current_user.id and not current_user.is_admin:
        abort(403)
    db.session.delete(rev)
    db.session.commit()
    flash("Відгук видалено.", "warning")
    return redirect(url_for("reviews.wall"))
