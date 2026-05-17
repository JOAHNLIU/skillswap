from flask import Blueprint
health_bp = Blueprint("health", __name__)
from skillswap.health import routes  # noqa
