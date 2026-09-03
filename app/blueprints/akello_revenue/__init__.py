from flask import Blueprint

bp = Blueprint("akello_revenue", __name__, url_prefix="/akello-revenue")

from app.blueprints.akello_revenue import routes  # noqa: E402,F401
