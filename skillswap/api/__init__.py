# filepath: skillswap/api/__init__.py
from flask import Blueprint

api_bp = Blueprint("api", __name__)

from skillswap.api import routes  # noqa: E402, F401
