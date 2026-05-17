from flask import Blueprint
agreements_bp = Blueprint("agreements", __name__)
from skillswap.agreements import routes  # noqa
