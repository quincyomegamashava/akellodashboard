from flask import Blueprint

bp = Blueprint("learn_api", __name__, url_prefix="/api/v1/learn")

from app.blueprints.learn_api import routes  # noqa: E402,F401
