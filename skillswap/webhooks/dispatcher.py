# filepath: skillswap/webhooks/dispatcher.py
"""SkillSwap — Webhook Dispatcher (HMAC-SHA256 signed POST requests)."""

import json, hashlib, hmac, threading
from datetime import datetime, timezone


def fire_event(event_slug: str, payload: dict) -> None:
    """Fire webhook event asynchronously (non-blocking)."""
    threading.Thread(target=_dispatch_all, args=(event_slug, payload), daemon=True).start()


def _dispatch_all(event_slug: str, payload: dict) -> None:
    try:
        from app import create_app
        app = create_app()
        with app.app_context():
            from models import Webhook
            from extensions import db
            for hook in Webhook.query.filter_by(is_active=True).all():
                if event_slug in hook.get_events():
                    _send_one(hook, event_slug, payload)
            db.session.commit()
    except Exception as e:
        print(f"[WEBHOOK] dispatch error: {e}")


def _send_one(hook, event_slug: str, payload: dict) -> None:
    import requests as req
    from extensions import db
    body = json.dumps({
        "event": event_slug,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }, ensure_ascii=False)
    sig = "sha256=" + hmac.new(hook.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    try:
        resp = req.post(hook.url, data=body,
                        headers={"Content-Type": "application/json",
                                 "X-SkillSwap-Event": event_slug,
                                 "X-SkillSwap-Signature": sig},
                        timeout=10)
        hook.last_status_code  = resp.status_code
        hook.last_triggered_at = datetime.now(timezone.utc)
    except Exception:
        hook.last_status_code  = 0
        hook.last_triggered_at = datetime.now(timezone.utc)


def verify_signature(body: bytes, secret: str, signature: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
