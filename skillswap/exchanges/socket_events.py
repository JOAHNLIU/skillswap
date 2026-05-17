# filepath: skillswap/exchanges/socket_events.py
"""SkillSwap — Socket.IO event handlers for real-time chat."""

from flask import request
from flask_login import current_user
from flask_socketio import join_room, emit
from extensions import db, socketio
from models import Exchange, Message


def register_events():
    """Register all Socket.IO events. Called from create_app."""

    @socketio.on("connect")
    def on_connect():
        """Join personal notification room on connect."""
        from flask_login import current_user
        if current_user.is_authenticated:
            join_room(f"user_{current_user.id}")

    @socketio.on("join_exchange")
    def on_join(data):
        exchange_id = data.get("exchange_id")
        if not exchange_id or not current_user.is_authenticated:
            return
        exchange = db.session.get(Exchange, int(exchange_id))
        if not exchange:
            return
        if current_user.id not in (exchange.proposer_id, exchange.receiver_id):
            return
        room = f"exchange_{exchange_id}"
        join_room(room)

    @socketio.on("send_message")
    def on_message(data):
        if not current_user.is_authenticated:
            return
        exchange_id = data.get("exchange_id")
        body = (data.get("body") or "").strip()
        if not exchange_id or not body:
            return
        exchange = db.session.get(Exchange, int(exchange_id))
        if not exchange:
            return
        if current_user.id not in (exchange.proposer_id, exchange.receiver_id):
            return

        msg = Message(
            exchange_id=exchange.id,
            sender_id=current_user.id,
            body=body[:2000],
        )
        db.session.add(msg)
        db.session.commit()

        room = f"exchange_{exchange_id}"
        emit("new_message", {
            "sender_id": current_user.id,
            "sender_name": current_user.full_name or current_user.email,
            "avatar": current_user.avatar_or_default(),
            "body": msg.body,
            "time": msg.created_at.strftime("%H:%M"),
        }, room=room)
