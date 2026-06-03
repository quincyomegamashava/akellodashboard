from flask import Blueprint

bp = Blueprint("learn_portal", __name__, url_prefix="/learn")

from app.blueprints.learn_portal import routes  # noqa: E402,F401
