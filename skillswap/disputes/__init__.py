from flask import Blueprint
disputes_bp = Blueprint("disputes", __name__)
from skillswap.disputes import routes  # noqa
