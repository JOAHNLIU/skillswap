# filepath: skillswap/skills/__init__.py
from flask import Blueprint

skills_bp = Blueprint("skills", __name__)

from skillswap.skills import routes  # noqa: E402, F401
