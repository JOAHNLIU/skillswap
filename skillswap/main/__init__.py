# filepath: skillswap/main/__init__.py
from flask import Blueprint

main_bp = Blueprint("main", __name__)

from skillswap.main import routes  # noqa: E402, F401
