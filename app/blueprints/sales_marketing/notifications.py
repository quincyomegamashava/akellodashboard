"""In-app notifications for Sales & Marketing leads and campaigns."""

from __future__ import annotations

from typing import Optional

from app import db
from app.models import Notification, User

from app.blueprints.sales_marketing.models import StakeholderLead

_SM_STAFF_CACHE_KEY = "sm_staff_user_ids"
_SM_STAFF_CACHE_TTL = 300


def can_access_sales_marketing_for_user(user: User) -> bool:
    role = (getattr(user, "userRole", None) or "").strip()
    return role == "Admin" or user.has_privilege("Sales & Marketing")


def _sm_staff_user_ids() -> list[int]:
    """Return SM staff user IDs (Admins + Sales & Marketing privilege), cached briefly."""
    try:
        from app.routes import cache

        cached = cache.get(_SM_STAFF_CACHE_KEY)
        if cached is not None:
            return list(cached)
    except Exception:
        cache = None

    ids: list[int] = []
    seen: set[int] = set()

    for user in User.query.filter(User.userRole == "Admin").all():
        if user.id not in seen:
            seen.add(user.id)
            ids.append(user.id)

    candidates = User.query.filter(
        User.userRole != "Admin",
        User.privileges.isnot(None),
    ).all()
    for user in candidates:
        if can_access_sales_marketing_for_user(user) and user.id not in seen:
            seen.add(user.id)
            ids.append(user.id)

    if cache is not None:
        try:
            cache.set(_SM_STAFF_CACHE_KEY, ids, timeout=_SM_STAFF_CACHE_TTL)
        except Exception:
            pass
    return ids


def _dedupe_sm_notification(
    user_id: int,
    notification_type: str,
    stakeholder_lead_id: Optional[int],
    message: str,
) -> None:
    existing = Notification.query.filter_by(
        user_id=user_id,
        notification_type=notification_type,
        stakeholder_lead_id=stakeholder_lead_id,
        read=False,
    ).first()
    if existing:
        existing.message = message[:2000]
        return
    db.session.add(
        Notification(
            user_id=user_id,
            stakeholder_lead_id=stakeholder_lead_id,
            message=message[:2000],
            notification_type=notification_type,
            read=False,
        )
    )


def notify_sm_staff(
    notification_type: str,
    message: str,
    stakeholder_lead_id: Optional[int] = None,
    exclude_user_id: Optional[int] = None,
) -> int:
    count = 0
    for uid in _sm_staff_user_ids():
        if exclude_user_id and uid == exclude_user_id:
            continue
        _dedupe_sm_notification(uid, notification_type, stakeholder_lead_id, message)
        count += 1
    return count


def notify_new_lead(lead: StakeholderLead) -> int:
    msg = f"New lead: {lead.full_name} ({lead.email})"
    return notify_sm_staff("sm_new_lead", msg, lead.id)


def notify_hot_lead(lead: StakeholderLead) -> int:
    msg = f"Hot lead: {lead.full_name} — {lead.role_category or 'Contact'}"
    return notify_sm_staff("sm_hot_lead", msg, lead.id)


def notify_campaign_failed(campaign_subject: str, failed_count: int) -> int:
    msg = f'Campaign "{campaign_subject[:80]}" had {failed_count} failed sends'
    return notify_sm_staff("sm_campaign_failed", msg, None)
