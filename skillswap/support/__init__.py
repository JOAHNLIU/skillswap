# filepath: skillswap/support/__init__.py
from flask import Blueprint

support_bp = Blueprint("support", __name__)

from skillswap.support import routes  # noqa
