"""In-app notifications for meeting notes assignments and overdue items."""

from __future__ import annotations

from datetime import date
from typing import Iterable, Optional, Set

from flask import current_app

from app import db
from app.email_utils import send_html_email
from app.models import Notification, User

from app.blueprints.meeting_notes.models import MeetingActionItem


def _dedupe_notification(
    user_id: int,
    notification_type: str,
    action_item_id: Optional[int],
    message: str,
) -> None:
    existing = Notification.query.filter_by(
        user_id=user_id,
        notification_type=notification_type,
        action_item_id=action_item_id,
        read=False,
    ).first()
    if existing:
        existing.message = message[:2000]
        return
    db.session.add(
        Notification(
            user_id=user_id,
            action_item_id=action_item_id,
            meeting_note_id=None,
            message=message[:2000],
            notification_type=notification_type,
            read=False,
        )
    )


def notify_assignees(
    item: MeetingActionItem,
    meeting_note_id: Optional[int],
    assignee_ids: Iterable[int],
    actor_user_id: int,
) -> None:
    cta = (item.call_to_action or "").strip()[:120] or "Action item"
    for uid in assignee_ids:
        if uid == actor_user_id:
            continue
        _dedupe_notification(
            uid,
            "meeting_assignment",
            item.id,
            f"You were assigned: {cta}",
        )
        n = Notification.query.filter_by(
            user_id=uid,
            notification_type="meeting_assignment",
            action_item_id=item.id,
            read=False,
        ).first()
        if n:
            n.meeting_note_id = meeting_note_id


def notify_overdue_items() -> int:
    """Daily job: notify assignees of overdue open/in-progress items."""
    today = date.today()
    items = (
        MeetingActionItem.query.filter(
            MeetingActionItem.due_date.isnot(None),
            MeetingActionItem.due_date < today,
            MeetingActionItem.status.in_(("open", "in_progress")),
        )
        .all()
    )
    count = 0
    for item in items:
        fr = item.focus_row
        mid = fr.meeting_note_id if fr else None
        cta = (item.call_to_action or "").strip()[:120] or "Action item"
        due_str = item.due_date.isoformat() if item.due_date else ""
        app_base_url = (current_app.config.get("APP_BASE_URL") or "").rstrip("/")
        if not app_base_url:
            app_base_url = "http://localhost:5000"
        meeting_link = f"{app_base_url}/meeting-notes/{mid}" if mid else f"{app_base_url}/meeting-notes/"
        for u in item.assignees or []:
            _dedupe_notification(
                u.id,
                "meeting_overdue",
                item.id,
                f"Overdue task: {cta}",
            )
            n = Notification.query.filter_by(
                user_id=u.id,
                notification_type="meeting_overdue",
                action_item_id=item.id,
                read=False,
            ).first()
            if n:
                n.meeting_note_id = mid
            if getattr(u, "email", None):
                subject = f"Overdue task reminder: {cta}"
                html = (
                    "<p>Hello,</p>"
                    "<p>You have an overdue meeting-notes task.</p>"
                    f"<p><strong>Task:</strong> {cta}<br>"
                    f"<strong>Due date:</strong> {due_str or 'N/A'}<br>"
                    f"<strong>Status:</strong> {(item.status or 'open').replace('_', ' ')}</p>"
                    f"<p><a href=\"{meeting_link}\">Open meeting notes</a></p>"
                )
                send_html_email(
                    to_email=u.email,
                    subject=subject[:200],
                    html_body=html,
                    text_body=f"Overdue task: {cta}\nDue date: {due_str or 'N/A'}\nView: {meeting_link}",
                )
            count += 1
    db.session.commit()
    return count


def notify_mentioned_users(
    mentioned_user_ids: Set[int],
    item: MeetingActionItem,
    meeting_note_id: Optional[int],
    author: User,
    excerpt: str,
) -> None:
    author_name = f"{(author.firstname or '').strip()} {(author.lastname or '').strip()}".strip() or author.username
    msg = f"{author_name} mentioned you on: {(excerpt or item.call_to_action or '')[:100]}"
    for uid in mentioned_user_ids:
        if uid == author.id:
            continue
        _dedupe_notification(uid, "meeting_comment", item.id, msg)
        n = Notification.query.filter_by(
            user_id=uid,
            notification_type="meeting_comment",
            action_item_id=item.id,
            read=False,
        ).first()
        if n:
            n.meeting_note_id = meeting_note_id
