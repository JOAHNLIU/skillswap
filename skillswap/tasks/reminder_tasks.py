# filepath: skillswap/tasks/reminder_tasks.py
"""SkillSwap — Session reminder background task."""

from skillswap.tasks import celery_app


@celery_app.task
def send_session_reminders():
    """
    Check for sessions starting in 60 minutes and send reminders.
    Runs every 5 minutes via Celery Beat.
    """
    try:
        from datetime import datetime, timezone, timedelta
        from app import create_app
        from extensions import db
        from models import Session, Exchange, User
        from skillswap.email_service import send_exchange_notification

        app = create_app()
        with app.app_context():
            now = datetime.now(timezone.utc)
            remind_from = now + timedelta(minutes=55)
            remind_to   = now + timedelta(minutes=65)

            upcoming = Session.query.filter(
                Session.scheduled_at >= remind_from,
                Session.scheduled_at <= remind_to,
            ).all()

            for session in upcoming:
                exchange = session.exchange
                for uid in (exchange.proposer_id, exchange.receiver_id):
                    user = db.session.get(User, uid)
                    if not user:
                        continue
                    dt_str = session.scheduled_at.strftime("%d.%m.%Y о %H:%M")
                    send_exchange_notification(
                        user,
                        "Нагадування про сесію",
                        f"""
                        <div style="font-family:sans-serif;">
                          <h3>⏰ Нагадування про сесію</h3>
                          <p>Через 1 годину у вас запланована сесія: <b>{dt_str}</b></p>
                          <p>Тривалість: {session.duration_minutes} хвилин</p>
                          {f'<p>Нотатки: {session.notes}</p>' if session.notes else ''}
                        </div>
                        """
                    )
    except Exception as e:
        print(f"[REMINDER ERROR] {e}")
