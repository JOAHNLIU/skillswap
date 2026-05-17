# filepath: skillswap/reviews/__init__.py
from flask import Blueprint

reviews_bp = Blueprint("reviews", __name__)

from skillswap.reviews import routes  # noqa: E402, F401
