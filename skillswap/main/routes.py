# filepath: skillswap/main/routes.py
"""Main pages for SkillSwap."""

from __future__ import annotations

from flask import render_template, redirect, url_for, current_app
from flask_login import current_user, login_required
from models import User, Skill, Exchange
from skillswap.main import main_bp


@main_bp.route("/")
def index():
    """Lightweight public landing page.

    On Render Free the first request after sleep must be as light as possible.
    Therefore database counters are optional and disabled by default with
    LIGHTWEIGHT_LANDING=1.
    """
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    try:
        stats = {
            "users": User.query.count(),
            "skills": Skill.query.count(),
            "exchanges": Exchange.query.count(),
        }
    except Exception:
        stats = {"users": 0, "skills": 0, "exchanges": 0}

    return render_template("main/index.html", stats=stats, title="SkillSwap")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    """Authenticated user dashboard."""
    user = current_user

    recent_exchanges = (
        Exchange.query.filter(
            (Exchange.proposer_id == user.id) | (Exchange.receiver_id == user.id)
        )
        .order_by(Exchange.created_at.desc())
        .limit(5)
        .all()
    )

    pending_incoming = Exchange.query.filter_by(
        receiver_id=user.id, status="pending"
    ).count()

    if current_app.config.get("FAST_DASHBOARD", True):
        matches = []
    else:
        from skillswap.skills.matching import get_matches
        matches = get_matches(user, limit=4)

    stats = {
        "skills_offer": user.skills.filter_by(skill_type="offer").count(),
        "skills_want": user.skills.filter_by(skill_type="want").count(),
        "exchanges_total": (
            Exchange.query.filter(
                (Exchange.proposer_id == user.id) | (Exchange.receiver_id == user.id)
            ).count()
        ),
        "rating": round(user.rating_points, 1),
    }

    return render_template(
        "main/dashboard.html",
        title="Дашборд",
        recent_exchanges=recent_exchanges,
        pending_incoming=pending_incoming,
        matches=matches,
        stats=stats,
    )


@main_bp.route("/about")
def about():
    """About page."""
    return render_template("main/about.html", title="Про платформу")


@main_bp.route("/system")
def system_overview():
    """Diploma-oriented system overview page."""
    modules = [
        {
            "name": "Користувачі та профілі",
            "description": "Реєстрація, авторизація, профіль, аватар, місто, доступність, 2FA.",
        },
        {
            "name": "Каталог навичок",
            "description": "CRUD навичок, категорії, рівні, пошук, фільтрація та перегляд деталей.",
        },
        {
            "name": "Алгоритм підбору",
            "description": "Порівняння навичок, міста, графіку доступності та рейтингу користувача.",
        },
        {
            "name": "Обміни та сесії",
            "description": "Створення запиту на бартер, зміна статусів, планування сесій, завершення обміну.",
        },
        {
            "name": "Довіра та якість",
            "description": "Відгуки, бейджі, рейтинги, скарги, диспути, перевірка користувачів.",
        },
        {
            "name": "Адміністрування",
            "description": "Адмін-панель, модерація користувачів, навичок, тікетів, ролей і скарг.",
        },
        {
            "name": "API та моніторинг",
            "description": "REST API, health-check, системні метрики, готовність до хмарного деплою.",
        },
    ]
    return render_template("main/system.html", title="Огляд системи", modules=modules)
