from flask import Blueprint
webhooks_bp = Blueprint("webhooks", __name__)
from skillswap.webhooks import routes  # noqa
