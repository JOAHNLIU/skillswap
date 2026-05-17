"""SkillSwap — Application Configuration."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Base configuration shared by local and cloud deployments."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = _bool_env("WTF_CSRF_ENABLED", True)
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))

    UPLOAD_FOLDER = str(
        BASE_DIR / os.environ.get("UPLOAD_FOLDER", "skillswap/static/uploads/avatars")
    )
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "pdf", "doc", "docx", "txt", "zip"}

    # Lightweight cache suitable for Render Free. Redis can be added later.
    CACHE_TYPE = os.environ.get("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", "300"))

    # Static files: browser cache. During active development use hard refresh if needed.
    SEND_FILE_MAX_AGE_DEFAULT = int(os.environ.get("SEND_FILE_MAX_AGE_DEFAULT", "2592000"))

    # Compression for HTML/CSS/JS responses.
    COMPRESS_MIMETYPES = [
        "text/html",
        "text/css",
        "text/xml",
        "application/json",
        "application/javascript",
        "application/x-javascript",
        "image/svg+xml",
    ]
    COMPRESS_LEVEL = int(os.environ.get("COMPRESS_LEVEL", "6"))
    COMPRESS_MIN_SIZE = int(os.environ.get("COMPRESS_MIN_SIZE", "500"))

    # Email / SMTP settings. For Gmail use App Password, not normal password.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = _bool_env("MAIL_USE_TLS", True)
    MAIL_USE_SSL = _bool_env("MAIL_USE_SSL", False)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "").strip()
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "").strip()
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER") or MAIL_USERNAME or "noreply@skillswap.local"

    # Render Free switches.
    LIGHTWEIGHT_LANDING = _bool_env("LIGHTWEIGHT_LANDING", True)
    AUTO_DB_INIT = _bool_env("AUTO_DB_INIT", False)
    ENABLE_REALTIME = _bool_env("ENABLE_REALTIME", False)
    FAST_DASHBOARD = _bool_env("FAST_DASHBOARD", True)

    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    @staticmethod
    def get_db_url() -> str:
        url = os.environ.get("DATABASE_URL", "").strip()
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url or f"sqlite:///{BASE_DIR / 'skillswap.db'}"

    SQLALCHEMY_DATABASE_URI = get_db_url()
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": int(os.environ.get("DB_POOL_SIZE", "1")),
        "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "1")),
        "pool_timeout": int(os.environ.get("DB_POOL_TIMEOUT", "15")),
    }


class DevelopmentConfig(Config):
    DEBUG = True
    AUTO_DB_INIT = _bool_env("AUTO_DB_INIT", True)


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
