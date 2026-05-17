from flask import Blueprint
apiv1_bp = Blueprint("apiv1", __name__)
from skillswap.apiv1 import routes  # noqa
