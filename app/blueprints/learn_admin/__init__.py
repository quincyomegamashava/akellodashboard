from flask import Blueprint

bp = Blueprint("learn_admin", __name__, url_prefix="/learn/admin")

from app.blueprints.learn_admin import routes  # noqa: E402,F401
