# filepath: skillswap/exchanges/__init__.py
from flask import Blueprint

exchanges_bp = Blueprint("exchanges", __name__)

from skillswap.exchanges import routes  # noqa: E402, F401
from skillswap.exchanges import session_routes  # noqa
