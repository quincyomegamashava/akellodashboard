"""Manual CSRF check for blueprints when ``WTF_CSRF_CHECK_DEFAULT`` is false.

Flask-WTF 1.2.x ``validate_csrf`` requires the signed token as the first argument
(see ``CSRFProtect._get_csrf_token`` / ``protect``).
"""

from __future__ import annotations

from flask import abort, current_app, request
from wtforms import ValidationError


def _csrf_token_from_request() -> str | None:
    field_name = current_app.config.get("WTF_CSRF_FIELD_NAME", "csrf_token")
    token = request.form.get(field_name)
    if token:
        return token
    for key in request.form:
        if key.endswith(field_name):
            val = request.form.get(key)
            if val:
                return val
    for header_name in current_app.config.get(
        "WTF_CSRF_HEADERS",
        ["X-CSRFToken", "X-CSRF-Token"],
    ):
        val = request.headers.get(header_name)
        if val:
            return val
    return None


def require_csrf_on_post() -> None:
    if request.method != "POST":
        return
    if not current_app.config.get("WTF_CSRF_ENABLED", True):
        return

    from flask_wtf.csrf import validate_csrf

    try:
        validate_csrf(_csrf_token_from_request())
    except ValidationError:
        abort(400)
