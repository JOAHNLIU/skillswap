# filepath: skillswap/totp/__init__.py
from flask import Blueprint

totp_bp = Blueprint("totp", __name__)

from skillswap.totp import routes  # noqa
