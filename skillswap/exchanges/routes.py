# filepath: skillswap/exchanges/routes.py
"""
SkillSwap — Exchanges Blueprint.
Handles: create, list, detail, accept/reject/complete, chat, sessions, reviews.
Integrates notify() for in-app notifications.
"""

from datetime import datetime, timezone
import os
from uuid import uuid4
from flask import current_app, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db
from models import User, Skill, Exchange, Message, Review, Session, Badge, ExchangeAgreement
from forms import ExchangeCreateForm, MessageForm, SessionForm, ReviewForm
from skillswap.exchanges import exchanges_bp
from werkzeug.utils import secure_filename


def _save_chat_attachment(file_storage):
    """Save an uploaded chat file into static/uploads/messages and return metadata."""
    if not file_storage or not getattr(file_storage, "filename", ""):
        return "", "", ""

    original_name = secure_filename(file_storage.filename)
    if not original_name:
        return "", "", ""

    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    allowed = current_app.config.get("ALLOWED_EXTENSIONS", set())
    if ext and ext not in allowed:
        flash("Файл цього типу не дозволено.", "warning")
        return "", "", ""

    upload_root = os.path.join(current_app.static_folder, "uploads", "messages")
    os.makedirs(upload_root, exist_ok=True)
    stored_name = f"{uuid4().hex}_{original_name}"
    absolute_path = os.path.join(upload_root, stored_name)
    file_storage.save(absolute_path)
    public_url = url_for("static", filename=f"uploads/messages/{stored_name}")
    return public_url, original_name, file_storage.mimetype or "application/octet-stream"


def _notify(user_id, title, body="", link="", notif_type=""):
    """Safe wrapper around notify() to avoid circular imports."""
    try:
        from skillswap.notifications.routes import notify
        notify(user_id=user_id, title=title, body=body, link=link, notif_type=notif_type)
    except Exception:
        pass


def _award_exchange_badges(user: User) -> None:
    completed = Exchange.query.filter(
        ((Exchange.proposer_id == user.id) | (Exchange.receiver_id == user.id)),
        Exchange.status == "completed",
    ).count()
    badge_slugs = {b.slug for b in user.badges.all()}
    for threshold, slug in [(1, "first_exchange"), (5, "experienced"), (10, "master")]:
        if completed >= threshold and slug not in badge_slugs:
            badge = Badge.query.filter_by(slug=slug).first()
            if badge:
                user.badges.append(badge)
                db.session.commit()
                flash(f"{badge.icon} Значок «{badge.name}»!", "info")
                _notify(user.id, f"Новий значок «{badge.name}»",
                        notif_type="badge_new",
                        link=url_for("users.profile", user_id=user.id))
    if user.rating_points >= 100 and "top_mentor" not in badge_slugs:
        badge = Badge.query.filter_by(slug="top_mentor").first()
        if badge:
            user.badges.append(badge)
            db.session.commit()
            flash(f"{badge.icon} Значок «{badge.name}»!", "info")


@exchanges_bp.route("/")
@login_required
def index():
    uid = current_user.id
    status_filter = request.args.get("status", "")
    page = request.args.get("page", 1, type=int)

    base = Exchange.query.filter(
        (Exchange.proposer_id == uid) | (Exchange.receiver_id == uid)
    )
    if status_filter:
        base = base.filter(Exchange.status == status_filter)

    pagination = base.order_by(Exchange.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )
    return render_template(
        "exchanges/index.html",
        title="Мої обміни",
        pagination=pagination,
        exchanges=pagination.items,
        status_filter=status_filter,
    )


@exchanges_bp.route("/create", methods=["GET", "POST"])
@login_required
def create():
    receiver_id = request.args.get("receiver_id", type=int) or request.form.get("receiver_id", type=int)
    receiver = User.query.get_or_404(receiver_id) if receiver_id else None
    if receiver and receiver.id == current_user.id:
        flash("Не можна створити обмін із самим собою. Оберіть іншого користувача.", "warning")
        return redirect(url_for("users.list_users"))

    form = ExchangeCreateForm()
    form.receiver_id.data = receiver_id

    my_offers = [(s.id, s.title) for s in current_user.skills.filter_by(skill_type="offer").all()]
    my_offers.insert(0, (0, "— оберіть —"))
    form.offered_skill_id.choices = my_offers

    if receiver:
        their_offers = [(s.id, s.title) for s in receiver.skills.filter_by(skill_type="offer").all()]
    else:
        their_offers = []
    their_offers.insert(0, (0, "— оберіть —"))
    form.requested_skill_id.choices = their_offers

    if form.validate_on_submit():
        if int(form.receiver_id.data) == current_user.id:
            flash("Не можна надсилати пропозицію обміну самому собі.", "warning")
            return redirect(url_for("users.list_users"))
        offered_id = form.offered_skill_id.data or None
        requested_id = form.requested_skill_id.data or None
        exchange = Exchange(
            proposer_id=current_user.id,
            receiver_id=int(form.receiver_id.data),
            offered_skill_id=offered_id if offered_id else None,
            requested_skill_id=requested_id if requested_id else None,
            message=form.message.data.strip() if form.message.data else "",
            status="pending",
        )
        db.session.add(exchange)
        db.session.commit()

        from skillswap.activity import log_activity
        log_activity(current_user.id, "exchange_started", exchange.id,
                     f"обмін з {exchange.receiver.full_name or exchange.receiver.email}")
        _notify(
            exchange.receiver_id,
            f"Нова пропозиція обміну від {current_user.full_name or current_user.email}",
            body=exchange.message[:80] if exchange.message else "",
            link=url_for("exchanges.detail", exchange_id=exchange.id),
            notif_type="exchange_new",
        )
        db.session.commit()

        flash("Пропозицію надіслано!", "success")
        return redirect(url_for("exchanges.detail", exchange_id=exchange.id))

    return render_template(
        "exchanges/create.html",
        title="Нова пропозиція обміну",
        form=form,
        receiver=receiver,
    )


@exchanges_bp.route("/<int:exchange_id>", methods=["GET", "POST"])
@login_required
def detail(exchange_id: int):
    exchange = Exchange.query.get_or_404(exchange_id)
    if current_user.id not in (exchange.proposer_id, exchange.receiver_id):
        abort(403)

    msg_form = MessageForm()
    if msg_form.validate_on_submit():
        text = (msg_form.body.data or "").strip()
        attachment_url, attachment_filename, attachment_mime = _save_chat_attachment(msg_form.attachment.data)
        if not text and not attachment_url:
            flash("Напишіть повідомлення або додайте файл.", "warning")
            return redirect(url_for("exchanges.detail", exchange_id=exchange.id))

        msg = Message(
            exchange_id=exchange.id,
            sender_id=current_user.id,
            body=text,
            attachment_url=attachment_url,
            attachment_filename=attachment_filename,
            attachment_mime=attachment_mime,
        )
        db.session.add(msg)
        # Notify the other participant
        other_id = (exchange.receiver_id
                    if current_user.id == exchange.proposer_id
                    else exchange.proposer_id)
        preview = text[:60] if text else f"Файл: {attachment_filename}"
        _notify(
            other_id,
            f"Нове повідомлення від {current_user.full_name or current_user.email}",
            body=preview,
            link=url_for("exchanges.detail", exchange_id=exchange.id),
            notif_type="message_new",
        )
        db.session.commit()
        return redirect(url_for("exchanges.detail", exchange_id=exchange.id))

    messages = exchange.messages.order_by(Message.created_at.asc()).all()
    sessions = exchange.sessions.order_by(Session.scheduled_at.asc()).all()
    my_review = Review.query.filter_by(
        exchange_id=exchange.id, reviewer_id=current_user.id
    ).first()

    return render_template(
        "exchanges/detail.html",
        title=f"Обмін #{exchange.id}",
        exchange=exchange,
        messages=messages,
        sessions=sessions,
        msg_form=msg_form,
        my_review=my_review,
    )


@exchanges_bp.route("/<int:exchange_id>/accept", methods=["POST"])
@login_required
def accept(exchange_id: int):
    exchange = Exchange.query.get_or_404(exchange_id)
    try:
        from skillswap.exchanges.state_machine import transition
        transition(exchange, "accepted", current_user.id)
        _notify(
            exchange.proposer_id,
            "Вашу пропозицію обміну прийнято",
            body="Тепер встановіть умови контракту для партнера.",
            link=url_for("agreements.view", exchange_id=exchange.id),
            notif_type="exchange_accepted",
        )
        db.session.commit()
        flash("Обмін прийнято! 🎉", "success")
    except Exception as e:
        flash(f"Помилка: {e}", "danger")
    return redirect(url_for("exchanges.detail", exchange_id=exchange_id))


@exchanges_bp.route("/<int:exchange_id>/reject", methods=["POST"])
@login_required
def reject(exchange_id: int):
    exchange = Exchange.query.get_or_404(exchange_id)
    try:
        from skillswap.exchanges.state_machine import transition
        transition(exchange, "rejected", current_user.id)
        flash("Обмін відхилено.", "info")
    except Exception as e:
        flash(f"Помилка: {e}", "danger")
    return redirect(url_for("exchanges.index"))


@exchanges_bp.route("/<int:exchange_id>/complete", methods=["POST"])
@login_required
def complete(exchange_id: int):
    exchange = Exchange.query.get_or_404(exchange_id)
    if current_user.id not in (exchange.proposer_id, exchange.receiver_id):
        abort(403)
    try:
        from skillswap.exchanges.state_machine import transition
        transition(exchange, "completed", current_user.id)
        for uid in (exchange.proposer_id, exchange.receiver_id):
            u = db.session.get(User, uid)
            if u:
                _award_exchange_badges(u)
        from skillswap.activity import log_activity
        log_activity(current_user.id, "exchange_completed", exchange_id)
        db.session.commit()
        flash("Обмін завершено! Залиште відгук.", "success")
        return redirect(url_for("exchanges.review", exchange_id=exchange_id))
    except Exception as e:
        flash(f"Помилка: {e}", "danger")
        return redirect(url_for("exchanges.detail", exchange_id=exchange_id))


@exchanges_bp.route("/<int:exchange_id>/call")
@login_required
def call(exchange_id: int):
    """Contract-protected call room for exchange participants."""
    exchange = Exchange.query.get_or_404(exchange_id)
    if current_user.id not in (exchange.proposer_id, exchange.receiver_id):
        abort(403)

    agreement = ExchangeAgreement.query.filter_by(exchange_id=exchange.id).first()
    if exchange.status != "accepted" or not agreement or not agreement.is_signed_by_both:
        flash("Дзвінок доступний тільки після підписання дійсного контракту обома сторонами.", "warning")
        return redirect(url_for("exchanges.detail", exchange_id=exchange.id))

    return render_template(
        "exchanges/call.html",
        title=f"Дзвінок — Обмін #{exchange.id}",
        exchange=exchange,
        room_name=f"skillswap-exchange-{exchange.id}",
    )


@exchanges_bp.route("/<int:exchange_id>/review", methods=["GET", "POST"])
@login_required
def review(exchange_id: int):
    exchange = Exchange.query.get_or_404(exchange_id)
    if current_user.id not in (exchange.proposer_id, exchange.receiver_id):
        abort(403)
    if exchange.status != "completed":
        flash("Відгук можна залишити лише після завершення обміну.", "warning")
        return redirect(url_for("exchanges.detail", exchange_id=exchange_id))

    existing = Review.query.filter_by(
        exchange_id=exchange.id, reviewer_id=current_user.id
    ).first()
    if existing:
        flash("Ви вже залишили відгук.", "info")
        return redirect(url_for("exchanges.detail", exchange_id=exchange_id))

    reviewee_id = (
        exchange.receiver_id
        if current_user.id == exchange.proposer_id
        else exchange.proposer_id
    )

    form = ReviewForm()
    if form.validate_on_submit():
        rev = Review(
            exchange_id=exchange.id,
            reviewer_id=current_user.id,
            reviewee_id=reviewee_id,
            rating=form.rating.data,
            comment=form.comment.data.strip() if form.comment.data else "",
            review_type=form.review_type.data,
        )
        db.session.add(rev)
        reviewee = db.session.get(User, reviewee_id)
        if reviewee:
            reviewee.recalculate_rating()
            _award_exchange_badges(reviewee)
        _notify(
            reviewee_id,
            f"Новий відгук від {current_user.full_name or current_user.email}",
            body=f"Оцінка: {'★' * form.rating.data}",
            link=url_for("users.profile", user_id=reviewee_id),
            notif_type="review_new",
        )
        db.session.commit()
        flash("Відгук збережено! Дякуємо.", "success")
        return redirect(url_for("exchanges.detail", exchange_id=exchange_id))

    reviewee = db.session.get(User, reviewee_id)
    return render_template(
        "exchanges/review.html",
        title="Залишити відгук",
        form=form,
        exchange=exchange,
        reviewee=reviewee,
    )


@exchanges_bp.route("/<int:exchange_id>/sessions/create", methods=["GET", "POST"])
@login_required
def create_session(exchange_id: int):
    exchange = Exchange.query.get_or_404(exchange_id)
    if current_user.id not in (exchange.proposer_id, exchange.receiver_id):
        abort(403)
    if exchange.status not in ("accepted", "completed"):
        flash("Можна планувати сесії лише для прийнятих обмінів.", "warning")
        return redirect(url_for("exchanges.detail", exchange_id=exchange_id))

    form = SessionForm()
    if form.validate_on_submit():
        try:
            scheduled_dt = datetime.fromisoformat(form.scheduled_at.data)
        except ValueError:
            flash("Невірний формат дати. Використовуйте YYYY-MM-DDTHH:MM", "danger")
            return render_template("exchanges/session_form.html", form=form, exchange=exchange)

        session = Session(
            exchange_id=exchange.id,
            scheduled_at=scheduled_dt,
            duration_minutes=form.duration_minutes.data,
            notes=form.notes.data.strip() if form.notes.data else "",
        )
        db.session.add(session)
        other_id = (exchange.receiver_id
                    if current_user.id == exchange.proposer_id
                    else exchange.proposer_id)
        _notify(
            other_id,
            "Заплановано нову сесію",
            body=f"{scheduled_dt.strftime('%d.%m.%Y %H:%M')} · {form.duration_minutes.data} хв.",
            link=url_for("exchanges.detail", exchange_id=exchange_id),
        )
        db.session.commit()
        flash("Сесію заплановано!", "success")
        return redirect(url_for("exchanges.detail", exchange_id=exchange_id))

    return render_template(
        "exchanges/session_form.html",
        title="Запланувати сесію",
        form=form,
        exchange=exchange,
    )


@exchanges_bp.route("/<int:exchange_id>/sessions/<int:session_id>/delete", methods=["POST"])
@login_required
def delete_session(exchange_id: int, session_id: int):
    exchange = Exchange.query.get_or_404(exchange_id)
    session = Session.query.get_or_404(session_id)
    if current_user.id not in (exchange.proposer_id, exchange.receiver_id):
        abort(403)
    db.session.delete(session)
    db.session.commit()
    flash("Сесію видалено.", "warning")
    return redirect(url_for("exchanges.detail", exchange_id=exchange_id))
