"""Sanitize client-facing errors: never ship stack traces; hide internals in production."""

from __future__ import annotations

import json
import logging
from typing import Any

try:
    from .cors_util import is_production_env
except ImportError:  # loaded as a standalone module in unit tests
    from cors_util import is_production_env

GENERIC_500 = 'An internal error occurred'
_TRACE_KEYS = ('trace', 'traceback', 'stack', 'stack_trace', 'exc_info', 'exception')
logger = logging.getLogger(__name__)


def client_error_payload(
    *,
    status: int = 500,
    exc: BaseException | None = None,
    public_message: str | None = None,
    production: bool | None = None,
) -> dict[str, str]:
    """JSON body safe to return to browsers."""
    if production is None:
        production = is_production_env()
    if status >= 500 and production:
        return {'error': GENERIC_500}
    if public_message:
        return {'error': public_message}
    if exc is not None and not (production and status >= 500):
        return {'error': str(exc)}
    if status >= 500:
        return {'error': GENERIC_500}
    return {'error': 'Request failed'}


def sanitize_json_error_payload(
    data: dict[str, Any],
    status_code: int,
    production: bool | None = None,
) -> tuple[dict[str, Any], bool]:
    """Strip trace fields always; generic-ize 5xx bodies in production."""
    if production is None:
        production = is_production_env()
    changed = False
    out = dict(data)
    for key in _TRACE_KEYS:
        if key in out:
            out.pop(key, None)
            changed = True
    if production and status_code >= 500:
        if out.get('error') != GENERIC_500:
            out['error'] = GENERIC_500
            changed = True
        if 'message' in out and out.get('success') is False:
            out['message'] = GENERIC_500
            changed = True
    return out, changed


def register_error_sanitizers(app) -> None:
    """Attach unhandled-exception + after-request sanitizers to a Flask app."""
    from flask import jsonify, request
    from werkzeug.exceptions import HTTPException

    @app.errorhandler(Exception)
    def _unhandled_exception(exc):
        if isinstance(exc, HTTPException):
            return exc
        app.logger.exception('Unhandled exception')
        accept = request.headers.get('Accept') or ''
        wants_json = (
            request.is_json
            or request.path.startswith('/api/')
            or 'application/json' in accept
        )
        production = is_production_env()
        if wants_json:
            payload = client_error_payload(status=500, exc=exc, production=production)
            return jsonify(payload), 500
        if app.debug and not production:
            raise exc
        return GENERIC_500, 500

    @app.after_request
    def _strip_trace_from_json(response):
        if response.mimetype != 'application/json':
            return response
        try:
            data = response.get_json(silent=True)
        except Exception:
            return response
        if not isinstance(data, dict):
            return response
        new_data, changed = sanitize_json_error_payload(
            data, response.status_code, is_production_env()
        )
        if not changed:
            return response
        response.set_data(json.dumps(new_data))
        response.content_type = 'application/json'
        return response


def log_and_payload(exc: BaseException, *, status: int = 500, public_message: str | None = None, log=None) -> dict[str, str]:
    (log or logger).exception(public_message or 'Request failed')
    return client_error_payload(status=status, exc=exc, public_message=public_message)
