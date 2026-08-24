from flask import Blueprint

bp = Blueprint("help_desk", __name__, url_prefix="/help-desk")

from app.blueprints.help_desk import models  # noqa: E402,F401
from app.blueprints.help_desk import routes  # noqa: E402,F401
