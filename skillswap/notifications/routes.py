# filepath: skillswap/notifications/routes.py
"""
from extensions import socketio

SkillSwap — Notifications Blueprint.
Routes: list, mark-read, mark-all-read.
Helper: notify() called from other blueprints.
"""

from flask import render_template, redirect, url_for, jsonify, request
from flask_login import login_required, current_user
from extensions import db
from models import Notification
from skillswap.notifications import notifications_bp


# ── Helper (imported by other blueprints) ─────────────────────────────────

def notify(user_id: int, title: str, body: str = "",
           link: str = "", notif_type: str = "") -> None:
    """Create a notification for a user. Safe to call anywhere."""
    icon = Notification.ICONS.get(notif_type, "🔔")
    n = Notification(
        user_id=user_id,
        title=f"{icon} {title}",
        body=body,
        link=link,
        is_read=False,
    )
    db.session.add(n)
    # Commit is handled by the caller's transaction


# ── Routes ────────────────────────────────────────────────────────────────

@notifications_bp.route("/")
@login_required
def index():
    """Show all notifications for current user."""
    notifs = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .all()
    )
    return render_template(
        "notifications/index.html",
        title="Сповіщення",
        notifications=notifs,
    )


@notifications_bp.route("/<int:notif_id>/read", methods=["POST"])
@login_required
def mark_read(notif_id: int):
    """Mark a single notification as read."""
    n = Notification.query.get_or_404(notif_id)
    if n.user_id != current_user.id:
        return jsonify({"ok": False}), 403
    n.is_read = True
    db.session.commit()
    return jsonify({"ok": True})


@notifications_bp.route("/read-all", methods=["POST"])
@login_required
def mark_all_read():
    """Mark all notifications as read."""
    Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({"is_read": True})
    db.session.commit()
    return redirect(url_for("notifications.index"))


@notifications_bp.route("/api/unread-count")
@login_required
def unread_count():
    """Return unread count as JSON (polled by navbar JS)."""
    count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()
    return jsonify({"count": count})


def push_notification(user_id: int, title: str, body: str = "") -> None:
    """Push real-time notification via Socket.IO to user's room."""
    try:
        socketio.emit("notification", {"title": title, "body": body},
                      room=f"user_{user_id}")
    except Exception:
        pass
