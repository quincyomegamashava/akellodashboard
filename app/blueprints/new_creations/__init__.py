from flask import Blueprint

bp = Blueprint("new_creations", __name__)

from app.blueprints.new_creations import routes  # noqa: E402,F401
