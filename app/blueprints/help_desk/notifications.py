"""In-app notifications for Help Desk assignments, mentions, and SLA breaches."""

from __future__ import annotations

from typing import Iterable, Optional

from flask import current_app

from app import db
from app.models import HelpDeskQuery, Notification, User


def _deep_link(query_id: int) -> str:
    app_base_url = (current_app.config.get("APP_BASE_URL") or "").rstrip("/")
    if not app_base_url:
        app_base_url = "http://localhost:5000"
    return f"{app_base_url}/help-desk/{query_id}"


def _dedupe(
    user_id: int,
    notification_type: str,
    query_id: int,
    message: str,
) -> None:
    existing = Notification.query.filter_by(
        user_id=user_id,
        notification_type=notification_type,
        query_id=query_id,
        read=False,
    ).first()
    if existing:
        existing.message = message[:2000]
        return
    db.session.add(
        Notification(
            user_id=user_id,
            query_id=query_id,
            message=message[:2000],
            notification_type=notification_type,
            read=False,
        )
    )


def notify_assignees(
    query: HelpDeskQuery,
    assignee_ids: Iterable[int],
    actor_user_id: int,
) -> None:
    title = (query.query_title or "Ticket")[:120]
    for uid in assignee_ids:
        if uid == actor_user_id:
            continue
        _dedupe(uid, "assignment", query.id, f"You were assigned: {title}")


def notify_resolution(query: HelpDeskQuery, actor_user_id: int) -> None:
    title = (query.query_title or "Ticket")[:120]
    # Notify creator if they are a user
    creator = User.query.filter_by(username=query.created_by).first()
    if creator and creator.id != actor_user_id:
        _dedupe(creator.id, "resolution", query.id, f"Resolved: {title}")
    for u in list(query.assignees or []) + list(query.watchers or []):
        if u.id == actor_user_id:
            continue
        _dedupe(u.id, "resolution", query.id, f"Resolved: {title}")


def notify_mentions(
    query: HelpDeskQuery,
    mentioned_users: Iterable[User],
    actor_user_id: int,
) -> None:
    title = (query.query_title or "Ticket")[:80]
    for u in mentioned_users:
        if u.id == actor_user_id:
            continue
        _dedupe(u.id, "helpdesk_mention", query.id, f"You were mentioned on: {title}")


def notify_watchers_reply(
    query: HelpDeskQuery,
    actor_user_id: int,
    *,
    is_internal: bool,
) -> None:
    title = (query.query_title or "Ticket")[:80]
    kind = "internal note" if is_internal else "reply"
    targets = set()
    for u in list(query.assignees or []) + list(query.watchers or []):
        targets.add(u.id)
    for uid in targets:
        if uid == actor_user_id:
            continue
        _dedupe(uid, "helpdesk_reply", query.id, f"New {kind} on: {title}")


def notify_sla_breach(query: HelpDeskQuery) -> None:
    title = (query.query_title or "Ticket")[:80]
    msg = f"SLA breached: {title}"
    targets = set()
    for u in list(query.assignees or []) + list(query.watchers or []):
        targets.add(u.id)
    # Also notify agents on the team
    if query.team:
        for u in query.team.members:
            targets.add(u.id)
    for uid in targets:
        _dedupe(uid, "helpdesk_sla_breach", query.id, msg)
