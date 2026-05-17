# filepath: skillswap/users/__init__.py
from flask import Blueprint

users_bp = Blueprint("users", __name__)

from skillswap.users import routes  # noqa: E402, F401
