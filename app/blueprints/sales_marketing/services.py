"""Query helpers, serialization, and access control for Sales & Marketing."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timedelta
from functools import wraps
from typing import Any, Dict, List, Optional, Sequence

from flask import abort, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app import db
from app.models import User

from app.blueprints.sales_marketing.models import (
    EmailCampaign,
    EmailCampaignRecipient,
    EmailTemplate,
    InterestOption,
    MarketingEvent,
    PublicSubmissionRateLimit,
    StakeholderLead,
    StakeholderLeadActivity,
    StakeholderLeadNote,
    StakeholderSavedView,
)

PRIVILEGE_NAME = "Sales & Marketing"
VALID_EVENT_STATUSES = ("active", "cancelled")
VALID_LEAD_STATUSES = ("new", "contacted", "qualified", "closed")
VALID_CONTACT = ("email", "phone", "whatsapp")
ROLE_CATEGORIES = ("Teacher", "Principal", "Parent", "Government", "NGO", "Other")
HEARD_ABOUT_OPTIONS = ("Social media", "Colleague", "Event stand", "Other")

ZIMBABWE_PROVINCES = [
    "Harare",
    "Bulawayo",
    "Manicaland",
    "Mashonaland Central",
    "Mashonaland East",
    "Mashonaland West",
    "Masvingo",
    "Matabeleland North",
    "Matabeleland South",
    "Midlands",
]

DEFAULT_INTEREST_OPTIONS = [
    "Need more information",
    "Request Akello training",
    "Request a demo",
    "Partnership enquiry",
    "Library / digital content interest",
    "Other",
]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RATE_LIMIT_PER_HOUR = 10


def can_access_sales_marketing() -> bool:
    if not current_user.is_authenticated:
        return False
    role = (getattr(current_user, "userRole", None) or "").strip()
    return role == "Admin" or current_user.has_privilege(PRIVILEGE_NAME)


def sales_marketing_required(f):
    @wraps(f)
    @login_required
    def wrapped(*args, **kwargs):
        if not can_access_sales_marketing():
            if request.accept_mimetypes.best_match(["application/json", "text/html"]) == "application/json":
                return jsonify({"error": "Unauthorized"}), 403
            return (
                render_template(
                    "sales_marketing/forbidden.html",
                    title="Sales & Marketing",
                    privilege_name=PRIVILEGE_NAME,
                ),
                403,
            )
        return f(*args, **kwargs)

    return wrapped


def user_label(u: User) -> str:
    return f"{(u.firstname or '').strip()} {(u.lastname or '').strip()}".strip() or u.username


def user_options() -> List[dict]:
    users = User.query.order_by(User.firstname, User.lastname, User.username).all()
    return [{"id": u.id, "label": user_label(u), "department": u.department or ""} for u in users]


def users_from_ids(ids: Optional[Sequence[Any]]) -> List[User]:
    if not ids:
        return []
    out = []
    for raw in ids:
        try:
            uid = int(raw)
        except (TypeError, ValueError):
            continue
        u = db.session.get(User, uid)
        if u:
            out.append(u)
    return out


def timeline_status(event: MarketingEvent, today: Optional[date] = None) -> str:
    today = today or date.today()
    if (event.status or "").lower() == "cancelled":
        return "cancelled"
    if event.end_date < today:
        return "past"
    if event.start_date <= today <= event.end_date:
        return "ongoing"
    return "upcoming"


def timeline_sort_key(event: MarketingEvent, today: Optional[date] = None) -> tuple:
    today = today or date.today()
    ts = timeline_status(event, today)
    order = {"ongoing": 0, "upcoming": 1, "past": 2, "cancelled": 3}
    if ts == "upcoming":
        return (order[ts], event.start_date.toordinal())
    if ts == "past":
        return (order[ts], -event.end_date.toordinal())
    return (order.get(ts, 9), event.start_date.toordinal())


def event_to_dict(event: MarketingEvent, *, include_lead_count: bool = True) -> dict:
    attendees = event.attendees or []
    data = {
        "id": event.id,
        "name": event.name,
        "start_date": event.start_date.isoformat() if event.start_date else None,
        "end_date": event.end_date.isoformat() if event.end_date else None,
        "location": event.location or "",
        "status": event.status,
        "notes": event.notes or "",
        "timeline_status": timeline_status(event),
        "attendee_ids": [u.id for u in attendees],
        "attendee_names": [user_label(u) for u in attendees],
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }
    if include_lead_count:
        data["lead_count"] = event.leads.count() if event.leads else 0
    data["connect_url"] = event_connect_url(event)
    data["slug"] = getattr(event, "slug", None) or ""
    data["banner_text"] = getattr(event, "banner_text", None) or ""
    data["cost_estimate"] = float(event.cost_estimate) if getattr(event, "cost_estimate", None) else None
    data["latitude"] = getattr(event, "latitude", None)
    data["longitude"] = getattr(event, "longitude", None)
    return data


def interest_option_to_dict(opt: InterestOption) -> dict:
    return {
        "id": opt.id,
        "label": opt.label,
        "sort_order": opt.sort_order,
        "is_active": opt.is_active,
    }


def lead_to_dict(lead: StakeholderLead) -> dict:
    ev = lead.event
    io = lead.interest_option
    return {
        "id": lead.id,
        "full_name": lead.full_name,
        "occupation": lead.occupation or "",
        "email": lead.email,
        "mobile": lead.mobile or "",
        "school_name": lead.school_name or "",
        "province": lead.province or "",
        "organization": lead.organization or "",
        "role_category": lead.role_category or "",
        "event_id": lead.event_id,
        "event_name": ev.name if ev else "",
        "interest_option_id": lead.interest_option_id,
        "interest_label": io.label if io else "",
        "preferred_contact": lead.preferred_contact or "",
        "consent_marketing": bool(lead.consent_marketing),
        "comments": lead.comments or "",
        "heard_about": lead.heard_about or "",
        "source": lead.source,
        "is_duplicate_flag": bool(lead.is_duplicate_flag),
        "duplicate_dismissed": bool(getattr(lead, "duplicate_dismissed", False)),
        "follow_up_status": getattr(lead, "follow_up_status", None) or "new",
        "lead_score": getattr(lead, "lead_score", None),
        "notes_count": lead.notes.count() if getattr(lead, "notes", None) else 0,
        "submitted_at": lead.submitted_at.isoformat() if lead.submitted_at else None,
        "created_by": lead.created_by,
    }


def campaign_recipient_to_dict(r: EmailCampaignRecipient) -> dict:
    return {
        "id": r.id,
        "email": r.email,
        "stakeholder_id": r.stakeholder_id,
        "status": r.status,
        "error_message": r.error_message or "",
        "sent_at": r.sent_at.isoformat() if r.sent_at else None,
    }


def note_to_dict(n: StakeholderLeadNote) -> dict:
    author = n.author
    return {
        "id": n.id,
        "body": n.body,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "user_id": n.user_id,
        "author_name": user_label(author) if author else "Staff",
    }


def stakeholders_stats() -> dict:
    today = date.today()
    week_ago = datetime.utcnow() - timedelta(days=7)
    total = StakeholderLead.query.count()
    week_count = StakeholderLead.query.filter(StakeholderLead.submitted_at >= week_ago).count()
    consent_count = StakeholderLead.query.filter(StakeholderLead.consent_marketing.is_(True)).count()
    dup_count = StakeholderLead.query.filter(
        StakeholderLead.is_duplicate_flag.is_(True),
        StakeholderLead.duplicate_dismissed.is_(False),
    ).count()
    active_events = MarketingEvent.query.filter(
        MarketingEvent.status == "active",
        MarketingEvent.start_date <= today,
        MarketingEvent.end_date >= today,
    ).count()
    upcoming = (
        MarketingEvent.query.filter(
            MarketingEvent.status == "active",
            MarketingEvent.start_date > today,
        )
        .order_by(MarketingEvent.start_date)
        .first()
    )
    next_event = None
    if upcoming:
        next_event = {"id": upcoming.id, "name": upcoming.name, "start_date": upcoming.start_date.isoformat()}
    by_status = dict(
        db.session.query(StakeholderLead.follow_up_status, func.count(StakeholderLead.id))
        .group_by(StakeholderLead.follow_up_status)
        .all()
    )
    return {
        "total_leads": total,
        "leads_this_week": week_count,
        "with_consent": consent_count,
        "duplicates_open": dup_count,
        "active_events": active_events,
        "next_event": next_event,
        "by_status": by_status,
    }


def campaign_to_dict(c: EmailCampaign, *, include_body: bool = False) -> dict:
    data = {
        "id": c.id,
        "subject": c.subject,
        "recipient_count": c.recipient_count,
        "status": c.status,
        "sent_at": c.sent_at.isoformat() if c.sent_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "filter_snapshot": c.filter_snapshot,
    }
    if include_body:
        data["body_html"] = c.body_html
    return data


def events_active_on_date(target: date) -> List[MarketingEvent]:
    return (
        MarketingEvent.query.options(joinedload(MarketingEvent.attendees))
        .filter(
            MarketingEvent.status == "active",
            MarketingEvent.start_date <= target,
            MarketingEvent.end_date >= target,
        )
        .order_by(MarketingEvent.name)
        .all()
    )


def events_query(
    *,
    timeline: Optional[str] = None,
    attendee_user_id: Optional[int] = None,
    location_q: Optional[str] = None,
    my_events: bool = False,
    current_user_id: Optional[int] = None,
) -> Any:
    today = date.today()
    q = MarketingEvent.query.options(joinedload(MarketingEvent.attendees))

    if my_events and current_user_id:
        q = q.filter(MarketingEvent.attendees.any(User.id == current_user_id))
    elif attendee_user_id:
        q = q.filter(MarketingEvent.attendees.any(User.id == attendee_user_id))

    if location_q and location_q.strip():
        q = q.filter(MarketingEvent.location.ilike(f"%{location_q.strip()}%"))

    events = q.all()
    if timeline and timeline != "all":
        events = [e for e in events if timeline_status(e, today) == timeline]
    events.sort(key=lambda e: timeline_sort_key(e, today))
    return events


def leads_query(
    *,
    event_id: Optional[int] = None,
    province: Optional[str] = None,
    interest_option_id: Optional[int] = None,
    consent_only: bool = False,
    search: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    attendee_user_id: Optional[int] = None,
    follow_up_status: Optional[str] = None,
    duplicates_only: bool = False,
    preferred_contact: Optional[str] = None,
):
    q = StakeholderLead.query.options(
        joinedload(StakeholderLead.event).joinedload(MarketingEvent.attendees),
        joinedload(StakeholderLead.interest_option),
    )

    if event_id:
        q = q.filter(StakeholderLead.event_id == event_id)
    if province and province.strip():
        q = q.filter(StakeholderLead.province == province.strip())
    if interest_option_id:
        q = q.filter(StakeholderLead.interest_option_id == interest_option_id)
    if consent_only:
        q = q.filter(StakeholderLead.consent_marketing.is_(True))
    if date_from:
        q = q.filter(StakeholderLead.submitted_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        q = q.filter(StakeholderLead.submitted_at <= datetime.combine(date_to, datetime.max.time()))
    if search and search.strip():
        term = f"%{search.strip()}%"
        q = q.filter(
            or_(
                StakeholderLead.full_name.ilike(term),
                StakeholderLead.email.ilike(term),
                StakeholderLead.school_name.ilike(term),
                StakeholderLead.mobile.ilike(term),
            )
        )
    if attendee_user_id:
        q = q.join(MarketingEvent, StakeholderLead.event_id == MarketingEvent.id).filter(
            MarketingEvent.attendees.any(User.id == attendee_user_id)
        )
    if follow_up_status and follow_up_status.strip():
        q = q.filter(StakeholderLead.follow_up_status == follow_up_status.strip())
    if duplicates_only:
        q = q.filter(
            StakeholderLead.is_duplicate_flag.is_(True),
            StakeholderLead.duplicate_dismissed.is_(False),
        )
    if preferred_contact and preferred_contact.strip():
        q = q.filter(StakeholderLead.preferred_contact == preferred_contact.strip())

    return q.order_by(StakeholderLead.submitted_at.desc())


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match(normalize_email(email)))


def ip_hash_from_request() -> str:
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
    if "," in ip:
        ip = ip.split(",")[0].strip()
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


def check_rate_limit() -> bool:
    """Return True if submission allowed."""
    ip_h = ip_hash_from_request()
    cutoff = datetime.utcnow() - timedelta(hours=1)
    PublicSubmissionRateLimit.query.filter(PublicSubmissionRateLimit.submitted_at < cutoff).delete(
        synchronize_session=False
    )
    count = PublicSubmissionRateLimit.query.filter(
        PublicSubmissionRateLimit.ip_hash == ip_h,
        PublicSubmissionRateLimit.submitted_at >= cutoff,
    ).count()
    return count < RATE_LIMIT_PER_HOUR


def record_rate_limit_hit() -> None:
    db.session.add(PublicSubmissionRateLimit(ip_hash=ip_hash_from_request()))


def check_duplicate_lead(email: str, event_id: Optional[int]) -> bool:
    if not email:
        return False
    cutoff = datetime.utcnow() - timedelta(hours=24)
    q = StakeholderLead.query.filter(
        StakeholderLead.email == normalize_email(email),
        StakeholderLead.submitted_at >= cutoff,
    )
    if event_id:
        q = q.filter(StakeholderLead.event_id == event_id)
    return q.first() is not None


def apply_event_attendees(event: MarketingEvent, attendee_ids: Optional[Sequence[Any]]) -> None:
    event.attendees = users_from_ids(attendee_ids or [])


def seed_interest_options_if_empty() -> None:
    if InterestOption.query.count() > 0:
        return
    for idx, label in enumerate(DEFAULT_INTEREST_OPTIONS):
        db.session.add(InterestOption(label=label, sort_order=idx, is_active=True))
    db.session.commit()


def slugify_event_name(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s[:100] or "event"


def ensure_unique_event_slug(base: str, exclude_id: Optional[int] = None) -> str:
    slug = base
    n = 1
    while True:
        q = MarketingEvent.query.filter_by(slug=slug)
        if exclude_id:
            q = q.filter(MarketingEvent.id != exclude_id)
        if not q.first():
            return slug
        n += 1
        slug = f"{base}-{n}"


def event_connect_url(event: MarketingEvent) -> str:
    base = request.url_root.rstrip("/") if request else ""
    if getattr(event, "slug", None):
        return f"{base}/connect/e/{event.slug}"
    return f"{base}/connect?event={event.id}"


def log_lead_activity(
    lead_id: int,
    activity_type: str,
    summary: str,
    actor_user_id: Optional[int] = None,
    details: Optional[dict] = None,
) -> StakeholderLeadActivity:
    act = StakeholderLeadActivity(
        lead_id=lead_id,
        actor_user_id=actor_user_id,
        activity_type=activity_type,
        summary=(summary or "")[:512],
        details_json=details,
    )
    db.session.add(act)
    return act


def activity_to_dict(a: StakeholderLeadActivity) -> dict:
    author = a.actor
    return {
        "id": a.id,
        "activity_type": a.activity_type,
        "summary": a.summary,
        "details_json": a.details_json,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "actor_name": user_label(author) if author else "System",
    }


def lead_timeline(lead_id: int, limit: int = 100) -> List[dict]:
    rows = (
        StakeholderLeadActivity.query.filter_by(lead_id=lead_id)
        .order_by(StakeholderLeadActivity.created_at.desc())
        .limit(limit)
        .all()
    )
    return [activity_to_dict(r) for r in rows]


def compute_lead_score(lead: StakeholderLead) -> int:
    score = 0
    if lead.consent_marketing:
        score += 20
    if (lead.role_category or "").lower() == "principal":
        score += 25
    elif (lead.role_category or "").lower() == "teacher":
        score += 10
    label = (lead.interest_option.label if lead.interest_option else "").lower()
    if "demo" in label:
        score += 25
    elif "training" in label:
        score += 15
    elif "partnership" in label:
        score += 10
    if lead.event_id:
        score += 10
    if lead.is_duplicate_flag and not lead.duplicate_dismissed:
        score -= 15
    if lead.submitted_at:
        days = (datetime.utcnow() - lead.submitted_at).days
        if days <= 3:
            score += 15
        elif days <= 7:
            score += 8
    return max(0, min(100, score))


def update_lead_score(lead: StakeholderLead) -> int:
    score = compute_lead_score(lead)
    lead.lead_score = score
    lead.score_updated_at = datetime.utcnow()
    return score


def suggested_action_for_lead(lead: StakeholderLead) -> str:
    score = lead.lead_score if lead.lead_score is not None else compute_lead_score(lead)
    status = lead.follow_up_status or "new"
    if status == "closed":
        return "Lead is closed — no action needed."
    if status == "new" and score >= 60:
        return "Schedule a demo call within 48 hours."
    if status == "new":
        return "Send introduction email and confirm interest."
    if status == "contacted":
        return "Follow up on last outreach; qualify needs."
    if status == "qualified":
        return "Propose next step: demo, training, or proposal."
    return "Review lead details and update status."


def replace_campaign_tokens(text: str, lead: StakeholderLead) -> str:
    if not text:
        return text
    first = (lead.full_name or "").split()[0] if lead.full_name else ""
    mapping = {
        "{{first_name}}": first,
        "{{full_name}}": lead.full_name or "",
        "{{event_name}}": lead.event.name if lead.event else "",
        "{{interest}}": lead.interest_option.label if lead.interest_option else "",
        "{{province}}": lead.province or "",
        "{{email}}": lead.email or "",
    }
    out = text
    for k, v in mapping.items():
        out = out.replace(k, v)
    return out


def stakeholders_by_province(period: str = "all") -> List[dict]:
    q = StakeholderLead.query.filter(
        StakeholderLead.province.isnot(None),
        StakeholderLead.province != "",
    )
    if period == "week":
        q = q.filter(StakeholderLead.submitted_at >= datetime.utcnow() - timedelta(days=7))
    elif period == "month":
        q = q.filter(StakeholderLead.submitted_at >= datetime.utcnow() - timedelta(days=30))
    leads = q.all()
    buckets: Dict[str, dict] = {}
    for lead in leads:
        prov = lead.province or "Unknown"
        if prov not in buckets:
            buckets[prov] = {"province": prov, "count": 0, "with_consent": 0}
        buckets[prov]["count"] += 1
        if lead.consent_marketing:
            buckets[prov]["with_consent"] += 1
    return list(buckets.values())


def funnel_analytics(period_days: int = 30) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=period_days)
    prev_cutoff = cutoff - timedelta(days=period_days)
    stages = list(VALID_LEAD_STATUSES)
    current = {}
    previous = {}
    for st in stages:
        current[st] = StakeholderLead.query.filter(
            StakeholderLead.submitted_at >= cutoff,
            StakeholderLead.follow_up_status == st,
        ).count()
        previous[st] = StakeholderLead.query.filter(
            StakeholderLead.submitted_at >= prev_cutoff,
            StakeholderLead.submitted_at < cutoff,
            StakeholderLead.follow_up_status == st,
        ).count()
    total = sum(current.values()) or 1
    conversions = {}
    for i, st in enumerate(stages[:-1]):
        next_st = stages[i + 1]
        base = current.get(st, 0) or 1
        conversions[f"{st}_to_{next_st}"] = round((current.get(next_st, 0) / base) * 100, 1)
    anomalies = []
    for prov in ZIMBABWE_PROVINCES:
        now_c = StakeholderLead.query.filter(
            StakeholderLead.province == prov,
            StakeholderLead.submitted_at >= cutoff,
        ).count()
        prev_c = StakeholderLead.query.filter(
            StakeholderLead.province == prov,
            StakeholderLead.submitted_at >= prev_cutoff,
            StakeholderLead.submitted_at < cutoff,
        ).count()
        if prev_c >= 5 and now_c < prev_c * 0.6:
            pct = round((1 - now_c / prev_c) * 100)
            anomalies.append({"province": prov, "message": f"{prov} down {pct}% vs prior period"})
    return {
        "period_days": period_days,
        "by_stage": current,
        "previous_by_stage": previous,
        "conversions": conversions,
        "anomalies": anomalies,
    }


def event_roi_stats(event_id: int) -> dict:
    event = db.session.get(MarketingEvent, event_id)
    if not event:
        return {}
    leads = StakeholderLead.query.filter_by(event_id=event_id).all()
    total = len(leads)
    consent = sum(1 for l in leads if l.consent_marketing)
    by_status = {}
    by_interest = {}
    for l in leads:
        st = l.follow_up_status or "new"
        by_status[st] = by_status.get(st, 0) + 1
        lbl = l.interest_option.label if l.interest_option else "Unknown"
        by_interest[lbl] = by_interest.get(lbl, 0) + 1
    cost = float(event.cost_estimate) if event.cost_estimate else None
    cpl = round(cost / total, 2) if cost and total else None
    attendees = len(event.attendees or [])
    return {
        "event": event_to_dict(event),
        "total_leads": total,
        "consent_count": consent,
        "consent_rate": round((consent / total) * 100, 1) if total else 0,
        "by_status": by_status,
        "by_interest": by_interest,
        "cost_estimate": cost,
        "cost_per_lead": cpl,
        "leads_per_attendee": round(total / attendees, 1) if attendees else None,
        "attendee_count": attendees,
    }


def template_to_dict(t: EmailTemplate) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "subject": t.subject,
        "body_html": t.body_html,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def saved_view_to_dict(v: StakeholderSavedView) -> dict:
    return {
        "id": v.id,
        "name": v.name,
        "filters_json": v.filters_json or {},
        "view_mode": v.view_mode,
        "is_default": v.is_default,
        "sort_order": v.sort_order,
    }


def normalize_whatsapp_mobile(mobile: str) -> str:
    digits = re.sub(r"\D", "", mobile or "")
    if digits.startswith("0"):
        digits = "263" + digits[1:]
    elif not digits.startswith("263"):
        digits = "263" + digits
    return digits


def whatsapp_url_for_lead(lead: StakeholderLead) -> str:
    mobile = normalize_whatsapp_mobile(lead.mobile)
    interest = lead.interest_option.label if lead.interest_option else "Akello"
    event = lead.event.name if lead.event else "our event"
    text = (
        f"Hello {lead.full_name.split()[0] if lead.full_name else ''}, "
        f"thank you for your interest in {interest} at {event}. "
        f"How can we assist you?"
    )
    from urllib.parse import quote
    return f"https://wa.me/{mobile}?text={quote(text)}"
