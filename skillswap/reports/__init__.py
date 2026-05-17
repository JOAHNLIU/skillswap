# filepath: skillswap/reports/__init__.py
from flask import Blueprint

reports_bp = Blueprint("reports", __name__)

from skillswap.reports import routes  # noqa: E402, F401
