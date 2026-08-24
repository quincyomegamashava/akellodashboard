from flask import Blueprint

bp = Blueprint("student_export", __name__, url_prefix="/student-export")

from app.blueprints.student_export import routes  # noqa: E402,F401
