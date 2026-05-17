from flask import Blueprint
trust_bp = Blueprint("trust", __name__)
from skillswap.trust import routes  # noqa
