"""In-app notifications for meeting notes assignments and overdue items."""

from __future__ import annotations

from datetime import date
from typing import Iterable, Optional, Set

from flask import current_app

from app import db
from app.email_utils import send_html_email
from app.models import Notification, User

from app.blueprints.meeting_notes.models import MeetingActionItem


def _meeting_deep_link(meeting_note_id: Optional[int], action_item_id: Optional[int] = None) -> str:
    app_base_url = (current_app.config.get("APP_BASE_URL") or "").rstrip("/")
    if not app_base_url:
        app_base_url = "http://localhost:5000"
    if not meeting_note_id:
        return f"{app_base_url}/meeting-notes/"
    link = f"{app_base_url}/meeting-notes/{meeting_note_id}?view=board"
    if action_item_id:
        link += f"&highlight={action_item_id}"
    return link


def _dedupe_notification(
    user_id: int,
    notification_type: str,
    action_item_id: Optional[int],
    message: str,
    meeting_note_id: Optional[int] = None,
) -> None:
    existing = Notification.query.filter_by(
        user_id=user_id,
        notification_type=notification_type,
        action_item_id=action_item_id,
        read=False,
    ).first()
    if existing:
        existing.message = message[:2000]
        if meeting_note_id is not None:
            existing.meeting_note_id = meeting_note_id
        return
    db.session.add(
        Notification(
            user_id=user_id,
            action_item_id=action_item_id,
            meeting_note_id=meeting_note_id,
            message=message[:2000],
            notification_type=notification_type,
            read=False,
        )
    )


def _email_user_task(
    user: User,
    *,
    subject: str,
    intro: str,
    cta: str,
    meeting_link: str,
    extra_html: str = "",
) -> None:
    if not getattr(user, "email", None):
        return
    html = (
        "<p>Hello,</p>"
        f"<p>{intro}</p>"
        f"<p><strong>Task:</strong> {cta}</p>"
        f"{extra_html}"
        f"<p><a href=\"{meeting_link}\">Open in meeting notes</a></p>"
    )
    send_html_email(
        to_email=user.email,
        subject=subject[:200],
        html_body=html,
        text_body=f"{intro}\nTask: {cta}\nView: {meeting_link}",
    )


def notify_assignees(
    item: MeetingActionItem,
    meeting_note_id: Optional[int],
    assignee_ids: Iterable[int],
    actor_user_id: int,
) -> None:
    cta = (item.call_to_action or "").strip()[:120] or "Action item"
    meeting_link = _meeting_deep_link(meeting_note_id, item.id)
    for uid in assignee_ids:
        if uid == actor_user_id:
            continue
        _dedupe_notification(
            uid,
            "meeting_assignment",
            item.id,
            f"You were assigned: {cta}",
            meeting_note_id=meeting_note_id,
        )
        u = db.session.get(User, uid)
        if u:
            _email_user_task(
                u,
                subject=f"Assigned: {cta}",
                intro="You were assigned a meeting-notes action item.",
                cta=cta,
                meeting_link=meeting_link,
            )


def notify_item_completed(
    item: MeetingActionItem,
    meeting_note_id: Optional[int],
    actor_user_id: int,
) -> None:
    cta = (item.call_to_action or "").strip()[:120] or "Action item"
    meeting_link = _meeting_deep_link(meeting_note_id, item.id)
    for u in item.assignees or []:
        if u.id == actor_user_id:
            continue
        _dedupe_notification(
            u.id,
            "meeting_completed",
            item.id,
            f"Completed: {cta}",
            meeting_note_id=meeting_note_id,
        )


def notify_repeat_carry(
    item: MeetingActionItem,
    meeting_note_id: Optional[int],
) -> None:
    cf = getattr(item, "carry_forward_count", 0) or 0
    if cf < 3:
        return
    cta = (item.call_to_action or "").strip()[:120] or "Action item"
    for u in item.assignees or []:
        _dedupe_notification(
            u.id,
            "meeting_repeat_carry",
            item.id,
            f"Repeatedly carried ({cf}x): {cta}",
            meeting_note_id=meeting_note_id,
        )


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
        meeting_link = _meeting_deep_link(mid, item.id)
        for u in item.assignees or []:
            _dedupe_notification(
                u.id,
                "meeting_overdue",
                item.id,
                f"Overdue task: {cta}",
                meeting_note_id=mid,
            )
            _email_user_task(
                u,
                subject=f"Overdue task reminder: {cta}",
                intro="You have an overdue meeting-notes task.",
                cta=cta,
                meeting_link=meeting_link,
                extra_html=(
                    f"<p><strong>Due date:</strong> {due_str or 'N/A'}<br>"
                    f"<strong>Status:</strong> {(item.status or 'open').replace('_', ' ')}</p>"
                ),
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
    cta = (item.call_to_action or "").strip()[:120] or "Action item"
    meeting_link = _meeting_deep_link(meeting_note_id, item.id)
    for uid in mentioned_user_ids:
        if uid == author.id:
            continue
        _dedupe_notification(
            uid,
            "meeting_comment",
            item.id,
            msg,
            meeting_note_id=meeting_note_id,
        )
        u = db.session.get(User, uid)
        if u:
            _email_user_task(
                u,
                subject=f"Mentioned on: {cta}",
                intro=f"{author_name} mentioned you on a meeting-notes task.",
                cta=cta,
                meeting_link=meeting_link,
                extra_html=f"<p><strong>Comment:</strong> {(excerpt or '')[:300]}</p>",
            )
