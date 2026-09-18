"""Staff auth/upload/lesson-generate routes (incremental extract from routes.py)."""

from flask import Blueprint

bp = Blueprint('staff_security', __name__)

from app.blueprints.staff_security import routes  # noqa: E402,F401


def init_app(app):
    """Attach routes with stable endpoint names (url_for('logout'), etc.)."""
    routes.init_app(app)
