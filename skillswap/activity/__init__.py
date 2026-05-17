# filepath: skillswap/activity/__init__.py
"""
SkillSwap — Activity Feed helper.
Call log_activity() anywhere to record an event.
"""

from __future__ import annotations


def log_activity(actor_id: int, event_type: str,
                 object_id: int = None, object_title: str = "") -> None:
    """
    Record an activity event. Safe to call anywhere — fails silently.

    Usage:
        from skillswap.activity import log_activity
        log_activity(user.id, "skill_added", skill.id, skill.title)
    """
    try:
        from extensions import db
        from models import ActivityEvent
        event = ActivityEvent(
            actor_id=actor_id,
            event_type=event_type,
            object_id=object_id,
            object_title=object_title or "",
        )
        db.session.add(event)
        # Caller commits the session
    except Exception:
        pass
