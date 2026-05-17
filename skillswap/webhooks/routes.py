# filepath: skillswap/webhooks/routes.py
import secrets, json
from flask import render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Webhook
from skillswap.webhooks import webhooks_bp


@webhooks_bp.route("/")
@login_required
def index():
    hooks = Webhook.query.filter_by(user_id=current_user.id).all()
    return render_template("webhooks/index.html", title="Вебхуки",
                           hooks=hooks, available_events=Webhook.EVENTS)


@webhooks_bp.route("/create", methods=["POST"])
@login_required
def create():
    url    = request.form.get("url", "").strip()
    events = request.form.getlist("events")
    if not url.startswith(("http://", "https://")):
        flash("URL повинен починатись з http:// або https://", "danger")
        return redirect(url_for("webhooks.index"))
    if not events:
        flash("Оберіть хоча б одну подію.", "warning")
        return redirect(url_for("webhooks.index"))
    if Webhook.query.filter_by(user_id=current_user.id).count() >= 5:
        flash("Максимум 5 вебхуків на акаунт.", "warning")
        return redirect(url_for("webhooks.index"))
    hook = Webhook(user_id=current_user.id, url=url,
                   secret=secrets.token_hex(32), is_active=True)
    hook.set_events(events)
    db.session.add(hook)
    db.session.commit()
    flash(f"✅ Вебхук створено! Secret: {hook.secret[:16]}...", "success")
    return redirect(url_for("webhooks.detail", hook_id=hook.id))


@webhooks_bp.route("/<int:hook_id>")
@login_required
def detail(hook_id: int):
    hook = Webhook.query.get_or_404(hook_id)
    if hook.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    return render_template("webhooks/detail.html", title=f"Вебхук #{hook_id}",
                           hook=hook, available_events=Webhook.EVENTS)


@webhooks_bp.route("/<int:hook_id>/toggle", methods=["POST"])
@login_required
def toggle(hook_id: int):
    hook = Webhook.query.get_or_404(hook_id)
    if hook.user_id != current_user.id: abort(403)
    hook.is_active = not hook.is_active
    db.session.commit()
    flash(f"Вебхук {'увімкнено' if hook.is_active else 'вимкнено'}.", "info")
    return redirect(url_for("webhooks.index"))


@webhooks_bp.route("/<int:hook_id>/delete", methods=["POST"])
@login_required
def delete(hook_id: int):
    hook = Webhook.query.get_or_404(hook_id)
    if hook.user_id != current_user.id and not current_user.is_admin: abort(403)
    db.session.delete(hook)
    db.session.commit()
    flash("Вебхук видалено.", "warning")
    return redirect(url_for("webhooks.index"))


@webhooks_bp.route("/<int:hook_id>/test", methods=["POST"])
@login_required
def test_webhook(hook_id: int):
    hook = Webhook.query.get_or_404(hook_id)
    if hook.user_id != current_user.id: abort(403)
    from skillswap.webhooks.dispatcher import fire_event
    fire_event("test.ping", {"message": "Тестовий запит від SkillSwap",
                              "webhook_id": hook.id, "user": current_user.email})
    flash("📡 Тестовий запит надіслано. Перевір URL-отримувач.", "info")
    return redirect(url_for("webhooks.detail", hook_id=hook_id))


@webhooks_bp.route("/incoming/test", methods=["POST"])
def incoming_test():
    """Built-in test receiver — logs to PyCharm console."""
    event = request.headers.get("X-SkillSwap-Event", "")
    try:
        data = request.get_json(force=True) or {}
        print(f"\n{'='*50}\n[WEBHOOK] event={event}")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        print('='*50)
    except Exception:
        pass
    return jsonify({"received": True, "event": event}), 200
