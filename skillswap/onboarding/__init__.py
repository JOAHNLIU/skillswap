# filepath: skillswap/onboarding/__init__.py
from flask import Blueprint

onboarding_bp = Blueprint("onboarding", __name__)

from skillswap.onboarding import routes  # noqa: E402, F401
