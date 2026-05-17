# filepath: skillswap/tasks/__init__.py
"""
SkillSwap — Celery background tasks.

Start worker (requires Redis):
  celery -A skillswap.tasks.celery_app worker --loglevel=info

Start beat scheduler (for reminders):
  celery -A skillswap.tasks.celery_app beat --loglevel=info

Without Redis, all tasks run synchronously (task_always_eager=True).
"""

import os
from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")


def make_celery(app=None):
    """Create Celery instance bound to Flask app context."""
    celery = Celery(
        "skillswap",
        broker=REDIS_URL,
        backend=REDIS_URL,
        include=["skillswap.tasks.email_tasks", "skillswap.tasks.reminder_tasks"],
    )
    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Europe/Kyiv",
        enable_utc=True,
        task_always_eager=not bool(os.environ.get("REDIS_URL", "")),
        # Beat schedule — check for upcoming sessions every 5 minutes
        beat_schedule={
            "send-session-reminders": {
                "task": "skillswap.tasks.reminder_tasks.send_session_reminders",
                "schedule": 300.0,  # every 5 minutes
            },
        },
    )
    if app is not None:
        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        celery.Task = ContextTask
    return celery


celery_app = make_celery()
