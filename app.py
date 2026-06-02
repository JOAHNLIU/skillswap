from __future__ import annotations

import os
from flask import Flask
from config import config
from extensions import db, migrate, login_manager, csrf, cache, mail, socketio, limiter, compress


def _init_sentry() -> None:
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if not dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=dsn,
        integrations=[FlaskIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.05")),
        environment=os.environ.get("FLASK_ENV", "production"),
    )


def create_app(config_name: str | None = None) -> Flask:
    _init_sentry()

    env_name = config_name or os.environ.get("FLASK_ENV", "development")
    cfg = config.get(env_name, config["default"])

    app = Flask(
        __name__,
        template_folder="skillswap/templates",
        static_folder="skillswap/static",
    )
    app.config.from_object(cfg)

    app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", "587"))
    app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "1") == "1"
    app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
    app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")
    app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER") or app.config["MAIL_USERNAME"] or "noreply@skillswap.local"

    os.makedirs(app.config.get("UPLOAD_FOLDER"), exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    cache.init_app(app)
    limiter.init_app(app)
    compress.init_app(app)
    mail.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*", async_mode="threading")

    _configure_login()
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_context_processors(app)
    _register_request_hooks(app)
    _register_template_helpers(app)

    if app.config.get("ENABLE_REALTIME"):
        from skillswap.exchanges.socket_events import register_events
        register_events()

    if app.config.get("AUTO_DB_INIT"):
        with app.app_context():
            _bootstrap_database()

    return app


def _configure_login() -> None:
    from models import User

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Увійдіть у систему, щоб продовжити."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None


def _register_blueprints(app: Flask) -> None:
    from commands import cli_bp
    from skillswap.admin import admin_bp
    from skillswap.agreements import agreements_bp
    from skillswap.api import api_bp
    from skillswap.apiv1 import apiv1_bp
    from skillswap.auth import auth_bp
    from skillswap.disputes import disputes_bp
    from skillswap.exchanges import exchanges_bp
    from skillswap.health import health_bp
    from skillswap.main import main_bp
    from skillswap.notifications import notifications_bp
    from skillswap.onboarding import onboarding_bp
    from skillswap.reports import reports_bp
    from skillswap.reviews import reviews_bp
    from skillswap.skills import skills_bp
    from skillswap.support import support_bp
    from skillswap.totp import totp_bp
    from skillswap.trust import trust_bp
    from skillswap.users import users_bp
    from skillswap.webhooks import webhooks_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(main_bp)
    app.register_blueprint(skills_bp, url_prefix="/skills")
    app.register_blueprint(exchanges_bp, url_prefix="/exchanges")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(onboarding_bp, url_prefix="/onboarding")
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(notifications_bp, url_prefix="/notifications")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(reviews_bp, url_prefix="/reviews")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(totp_bp, url_prefix="/2fa")
    app.register_blueprint(support_bp, url_prefix="/support")
    app.register_blueprint(disputes_bp, url_prefix="/disputes")
    app.register_blueprint(agreements_bp, url_prefix="/agreements")
    app.register_blueprint(trust_bp, url_prefix="/trust")
    app.register_blueprint(webhooks_bp, url_prefix="/webhooks")
    app.register_blueprint(apiv1_bp, url_prefix="/api/v1")
    app.register_blueprint(health_bp, url_prefix="/health")
    app.register_blueprint(cli_bp)


def _register_error_handlers(app: Flask) -> None:
    from flask import jsonify, redirect, request, url_for, flash
    from flask_limiter.errors import RateLimitExceeded

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(error):
        if request.is_json:
            return jsonify({"error": "Забагато запитів. Спробуйте пізніше."}), 429
        flash("Забагато спроб. Зачекайте і спробуйте знову.", "warning")
        return redirect(url_for("auth.login"))


def _register_context_processors(app: Flask) -> None:
    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        unread_notifications = 0
        profile_completeness = 0
        if current_user.is_authenticated:
            from models import Notification
            unread_key = f"unread_notifications:{current_user.id}"
            cached_unread = cache.get(unread_key)
            if cached_unread is None:
                cached_unread = Notification.query.filter_by(
                    user_id=current_user.id, is_read=False
                ).count()
                cache.set(unread_key, cached_unread, timeout=20)
            unread_notifications = cached_unread
            profile_completeness = _calc_completeness(current_user)
        return {
            "unread_notifications": unread_notifications,
            "profile_completeness": profile_completeness,
            "realtime_enabled": bool(app.config.get("ENABLE_REALTIME")),
        }


def _register_request_hooks(app: Flask) -> None:
    from flask import render_template, request, redirect, url_for
    from flask_login import current_user

    @app.before_request
    def check_ban_and_onboarding():
        if not current_user.is_authenticated:
            return None
        if any(request.path.startswith(p) for p in ("/static/", "/auth/logout")):
            return None
        if current_user.is_banned:
            ban = current_user.ban_record
            return render_template("auth/banned.html", title="Акаунт заблоковано", ban=ban), 403

        email_allowed_prefixes = (
            "/auth/check-email",
            "/auth/resend-verification",
            "/auth/verify-email",
            "/auth/logout",
            "/auth/forgot-password",
            "/auth/reset-password",
        )
        if not current_user.email_verified:
            if any(request.path.startswith(p) for p in email_allowed_prefixes):
                return None
            return redirect(url_for("auth.check_email"))

        allowed_prefixes = (
            "/onboarding/profile",
            "/onboarding/skills",
            "/auth/forgot-password",
            "/auth/reset-password",
        )
        if any(request.path.startswith(p) for p in allowed_prefixes):
            return None
        if request.path.startswith("/2fa/"):
            return None

        profile_filled = bool(
            current_user.full_name and current_user.age and current_user.gender
            and current_user.city and current_user.available_from and current_user.available_to
        )
        has_offer = bool(current_user.get_skills_offer())
        has_want = bool(current_user.get_skills_want())
        if not profile_filled:
            return redirect(url_for("onboarding.profile"))
        if not (has_offer and has_want):
            return redirect(url_for("onboarding.skills_setup"))
        if not current_user.onboarding_done:
            current_user.onboarding_done = True
            db.session.commit()
        return None

    @app.after_request
    def add_static_cache_headers(response):
        if request.path.startswith("/static/"):
            response.headers.setdefault("Cache-Control", "public, max-age=2592000, immutable")
        return response


def _register_template_helpers(app: Flask) -> None:
    app.jinja_env.globals["enumerate"] = enumerate


def _bootstrap_database() -> None:
    db.create_all()
    _seed_badges()
    _seed_rbac()

    try:
        _add_session_lifecycle_columns()
    except Exception as error:
        print(f"[DB INIT] Session lifecycle columns were not added: {error}")

    try:
        _add_message_attachment_columns()
    except Exception as error:
        print(f"[DB INIT] Message attachment columns were not added: {error}")


def _calc_completeness(user) -> int:
    fields = [
        bool(user.full_name),
        bool(user.bio),
        bool(user.city),
        bool(user.age),
        bool(user.gender),
        bool(user.avatar_url),
        bool(user.available_from),
        bool(user.get_skills_offer()),
        bool(user.get_skills_want()),
    ]
    return int(sum(fields) / len(fields) * 100)


def _seed_badges() -> None:
    from models import Badge

    for badge_definition in Badge.DEFINITIONS:
        if not Badge.query.filter_by(slug=badge_definition["slug"]).first():
            db.session.add(Badge(**badge_definition))
    db.session.commit()


def _seed_rbac() -> None:
    from models import Permission, Role

    for slug, name in Permission.DEFINITIONS:
        if not Permission.query.filter_by(slug=slug).first():
            db.session.add(Permission(slug=slug, name=name))
    db.session.commit()

    for role_definition in Role.DEFINITIONS:
        role = Role.query.filter_by(slug=role_definition["slug"]).first()
        if not role:
            role = Role(
                slug=role_definition["slug"],
                name=role_definition["name"],
                priority=role_definition["priority"],
            )
            db.session.add(role)
            db.session.commit()
        for permission_slug in role_definition["permissions"]:
            permission = Permission.query.filter_by(slug=permission_slug).first()
            if permission and role.permissions.filter_by(slug=permission_slug).count() == 0:
                role.permissions.append(permission)
    db.session.commit()


def _add_session_lifecycle_columns() -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if "session" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("session")}
    new_columns = {
        "status": "VARCHAR(20) DEFAULT 'proposed'",
        "proposer_confirmed_at": "TIMESTAMP",
        "receiver_confirmed_at": "TIMESTAMP",
        "proposer_completed_at": "TIMESTAMP",
        "receiver_completed_at": "TIMESTAMP",
        "proposer_marked_missed": "BOOLEAN DEFAULT FALSE",
        "receiver_marked_missed": "BOOLEAN DEFAULT FALSE",
        "reminder_sent_at": "TIMESTAMP",
    }

    with db.engine.connect() as connection:
        for column_name, column_type in new_columns.items():
            if column_name not in existing:
                connection.execute(
                    text(f'ALTER TABLE "session" ADD COLUMN {column_name} {column_type}')
                )
        connection.commit()


def _add_message_attachment_columns() -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if "message" not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns("message")}
    new_columns = {
        "attachment_url": "VARCHAR(512) DEFAULT ''",
        "attachment_filename": "VARCHAR(255) DEFAULT ''",
        "attachment_mime": "VARCHAR(120) DEFAULT ''",
    }

    with db.engine.connect() as connection:
        for column_name, column_type in new_columns.items():
            if column_name not in existing:
                connection.execute(
                    text(f'ALTER TABLE "message" ADD COLUMN {column_name} {column_type}')
                )
        connection.commit()


if __name__ == "__main__":
    application = create_app(os.environ.get("FLASK_ENV", "development"))
    socketio.run(application, debug=application.debug, host="0.0.0.0", port=5000)