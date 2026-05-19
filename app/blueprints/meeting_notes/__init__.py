from flask import Blueprint

bp = Blueprint("meeting_notes", __name__, url_prefix="/meeting-notes")

from app.blueprints.meeting_notes import routes  # noqa: E402,F401
