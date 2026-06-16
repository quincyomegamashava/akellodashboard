from flask import Blueprint

bp = Blueprint("sales_marketing", __name__, url_prefix="/sales-marketing")

from app.blueprints.sales_marketing import routes
from app.blueprints.sales_marketing import sm_roadmap_routes  # noqa: F401  # noqa: E402,F401
