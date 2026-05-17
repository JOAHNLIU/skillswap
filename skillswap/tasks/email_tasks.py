# filepath: skillswap/tasks/email_tasks.py
"""SkillSwap — Async email tasks via Celery."""

from skillswap.tasks import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email_task(self, user_id: int):
    """Send email verification asynchronously."""
    try:
        from extensions import db
        from models import User
        from skillswap.email_service import send_verification_email
        from app import create_app
        app = create_app()
        with app.app_context():
            user = db.session.get(User, user_id)
            if user and not user.email_verified:
                send_verification_email(user)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_task(self, user_id: int):
    """Send password reset email asynchronously."""
    try:
        from extensions import db
        from models import User
        from skillswap.email_service import send_password_reset_email
        from app import create_app
        app = create_app()
        with app.app_context():
            user = db.session.get(User, user_id)
            if user:
                send_password_reset_email(user)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task
def send_notification_email_task(user_id: int, subject: str, body_html: str):
    """Send generic notification email asynchronously."""
    try:
        from extensions import db
        from models import User
        from skillswap.email_service import send_exchange_notification
        from app import create_app
        app = create_app()
        with app.app_context():
            user = db.session.get(User, user_id)
            if user:
                send_exchange_notification(user, subject, body_html)
    except Exception:
        pass
