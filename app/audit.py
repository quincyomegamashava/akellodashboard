"""Global deletion audit trail.

Hooks into the SQLAlchemy session so every ORM-level delete (including cascades
fired by ``cascade="all,delete-orphan"`` relationships) is recorded in the
``audit_logs`` table without having to instrument each delete site individually.
"""

import json
import logging

from sqlalchemy import event
from flask import has_request_context, request
from flask_login import current_user


# Tables we deliberately skip auditing.  ``audit_logs`` itself prevents
# infinite recursion; the rest are high-volume operational tables whose
# rows are not interesting from an audit perspective.
EXCLUDED_TABLES = {
    "audit_logs",
    "user_activities",
    "active_sessions",
    "page_analytics",
}


_logger = logging.getLogger(__name__)


def _json_safe(value):
    """Best-effort coercion of a column value into a JSON-serialisable form."""
    try:
        # Round-trip through JSON so datetimes/decimals/etc become concrete
        # JSON-safe primitives instead of non-serialisable Python objects.
        return json.loads(json.dumps(value, default=str))
    except Exception:
        try:
            return str(value)
        except Exception:
            return None


def _snapshot(obj):
    """Capture the column values of an ORM instance into a plain dict."""
    try:
        cols = obj.__table__.columns.keys()
    except Exception:
        return None
    out = {}
    for c in cols:
        try:
            out[c] = _json_safe(getattr(obj, c, None))
        except Exception:
            out[c] = None
    return out


def _request_context():
    """Return actor + request metadata when called inside a Flask request."""
    if not has_request_context():
        return {
            "actor_user_id": None,
            "actor_username": None,
            "ip_address": None,
            "endpoint": None,
            "http_method": None,
            "url_path": None,
            "user_agent": None,
        }

    actor_id = None
    actor_name = None
    try:
        if getattr(current_user, "is_authenticated", False):
            actor_id = getattr(current_user, "id", None)
            actor_name = getattr(current_user, "username", None)
    except Exception:
        pass

    ua = request.headers.get("User-Agent") or ""
    return {
        "actor_user_id": actor_id,
        "actor_username": actor_name,
        "ip_address": request.remote_addr,
        "endpoint": request.endpoint,
        "http_method": request.method,
        "url_path": request.path,
        "user_agent": ua[:500] if ua else None,
    }


def init_audit(app, db):
    """Register the deletion audit listener on ``db.session``."""

    # Imported lazily so models are fully defined when the listener fires.
    from app.models import AuditLog

    @event.listens_for(db.session, "before_flush")
    def _capture_deletes(session, flush_context, instances):  # noqa: ARG001
        if not session.deleted:
            return

        pending = []
        for obj in session.deleted:
            try:
                table_name = getattr(obj, "__tablename__", None)
            except Exception:
                table_name = None
            if not table_name or table_name in EXCLUDED_TABLES:
                continue
            if isinstance(obj, AuditLog):
                continue

            label = (
                getattr(obj, "title", None)
                or getattr(obj, "name", None)
                or getattr(obj, "original_name", None)
                or getattr(obj, "username", None)
                or getattr(obj, "email", None)
            )
            label_str = str(label)[:255] if label is not None else None

            pending.append({
                "entity_type": obj.__class__.__name__,
                "entity_id": str(getattr(obj, "id", "")),
                "entity_label": label_str,
                "snapshot": _snapshot(obj),
            })

        if not pending:
            return

        ctx = _request_context()

        for p in pending:
            try:
                session.add(AuditLog(
                    action="delete",
                    entity_type=p["entity_type"],
                    entity_id=p["entity_id"],
                    entity_label=p["entity_label"],
                    snapshot=p["snapshot"],
                    actor_user_id=ctx["actor_user_id"],
                    actor_username=ctx["actor_username"],
                    ip_address=ctx["ip_address"],
                    endpoint=ctx["endpoint"],
                    http_method=ctx["http_method"],
                    url_path=ctx["url_path"],
                    user_agent=ctx["user_agent"],
                ))
            except Exception:
                # Auditing must never break the originating operation.
                _logger.exception("Failed to record audit log entry for %s", p.get("entity_type"))
