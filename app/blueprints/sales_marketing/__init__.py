from flask import Blueprint

bp = Blueprint("sales_marketing", __name__, url_prefix="/sales-marketing")

from app.blueprints.sales_marketing import routes  # noqa: E402,F401
