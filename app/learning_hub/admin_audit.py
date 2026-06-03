"""Staff audit logging for Learning Hub."""

from __future__ import annotations

from typing import Any, Optional

from flask import has_request_context, request

from app import db
from app.learning_hub.models import LearnAdminAuditLog


def log_staff_action(
    *,
    actor_staff_user_id: Optional[int],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    before: Optional[Any] = None,
    after: Optional[Any] = None,
) -> None:
    ip = None
    if has_request_context():
        ip = request.remote_addr or None
    row = LearnAdminAuditLog(
        actor_staff_user_id=actor_staff_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=before,
        after_json=after,
        ip=ip,
    )
    db.session.add(row)
