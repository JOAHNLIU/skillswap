# filepath: skillswap/auth/__init__.py
from flask import Blueprint

auth_bp = Blueprint("auth", __name__)

from skillswap.auth import routes  # noqa: E402, F401
