from flask import Blueprint

bp = Blueprint("learn_guardian", __name__, url_prefix="/learn/guardian")

from app.blueprints.learn_guardian import routes  # noqa: E402,F401
