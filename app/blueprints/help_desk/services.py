"""Access control, serialization, SLA, and assignment helpers for Help Desk."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, List, Optional

from flask import abort, current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from app import db
from app.models import AppSetting, HelpDeskQuery, HelpDeskTeam, User

from app.blueprints.help_desk.models import (
    HelpDeskArticle,
    HelpDeskAttachment,
    HelpDeskMacro,
    HelpDeskMessage,
)

PRIVILEGE_AGENT = "Help Desk Agent"
PRIVILEGE_VIEWER = "Help Desk Viewer"
PRIVILEGE_ADMIN_QUERIES = "Admin Queries Access"

VALID_STATUSES = ("Not started", "Looking into it", "Resolved")
VALID_PRIORITIES = ("urgent", "high", "normal")
VALID_CATEGORIES = ("billing", "access", "technical", "general", "other")
VALID_SOURCES = ("internal", "email")

DEFAULT_SLA_POLICY = {
    "urgent": {"first_response_hours": 1, "resolve_hours": 4},
    "high": {"first_response_hours": 4, "resolve_hours": 24},
    "normal": {"first_response_hours": 8, "resolve_hours": 72},
}

MENTION_RE = re.compile(r"@([A-Za-z0-9_.-]+)")


def _role() -> str:
    return (getattr(current_user, "userRole", None) or "").strip()


def is_admin() -> bool:
    if not current_user.is_authenticated:
        return False
    return _role() == "Admin" or current_user.has_privilege(PRIVILEGE_ADMIN_QUERIES)


def is_agent() -> bool:
    if not current_user.is_authenticated:
        return False
    return is_admin() or current_user.has_privilege(PRIVILEGE_AGENT)


def is_viewer() -> bool:
    if not current_user.is_authenticated:
        return False
    return is_agent() or current_user.has_privilege(PRIVILEGE_VIEWER)


def can_view_inbox() -> bool:
    return is_viewer()


def can_mutate_tickets() -> bool:
    return is_agent()


def can_manage_settings() -> bool:
    return is_admin()


def agent_required(f):
    @wraps(f)
    @login_required
    def wrapped(*args, **kwargs):
        if not can_mutate_tickets():
            if _wants_json():
                return jsonify({"error": "Unauthorized"}), 403
            abort(403)
        return f(*args, **kwargs)

    return wrapped


def viewer_required(f):
    @wraps(f)
    @login_required
    def wrapped(*args, **kwargs):
        if not can_view_inbox():
            if _wants_json():
                return jsonify({"error": "Unauthorized"}), 403
            abort(403)
        return f(*args, **kwargs)

    return wrapped


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapped(*args, **kwargs):
        if not can_manage_settings():
            if _wants_json():
                return jsonify({"error": "Unauthorized"}), 403
            abort(403)
        return f(*args, **kwargs)

    return wrapped


def _wants_json() -> bool:
    return request.accept_mimetypes.best_match(["application/json", "text/html"]) == "application/json"


def get_sla_policy() -> Dict[str, Any]:
    raw = AppSetting.get_value("helpdesk_sla_policy", "")
    if not raw:
        return dict(DEFAULT_SLA_POLICY)
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            merged = dict(DEFAULT_SLA_POLICY)
            for key, val in data.items():
                if key in merged and isinstance(val, dict):
                    merged[key] = {**merged[key], **val}
            return merged
    except Exception:
        pass
    return dict(DEFAULT_SLA_POLICY)


def set_sla_policy(policy: Dict[str, Any], user_id: Optional[int] = None) -> None:
    AppSetting.set_value(
        "helpdesk_sla_policy",
        json.dumps(policy),
        user_id=user_id,
        description="Help desk SLA hours by priority",
    )


def apply_sla_deadlines(query: HelpDeskQuery, *, now: Optional[datetime] = None) -> None:
    now = now or datetime.utcnow()
    policy = get_sla_policy()
    priority = (query.priority or "normal").lower()
    if priority not in policy:
        priority = "normal"
    rules = policy[priority]
    fr_h = float(rules.get("first_response_hours", 8))
    res_h = float(rules.get("resolve_hours", 72))
    if not query.first_response_at:
        query.sla_first_response_due = now + timedelta(hours=fr_h)
    query.sla_resolve_due = now + timedelta(hours=res_h)
    query.sla_breached = False


def user_brief(u: User) -> Dict[str, Any]:
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "firstname": u.firstname,
        "lastname": u.lastname,
        "userRole": u.userRole,
        "display_name": f"{u.firstname or ''} {u.lastname or ''}".strip() or u.username,
    }


def serialize_attachment(att: HelpDeskAttachment) -> Dict[str, Any]:
    return {
        "id": att.id,
        "filename": att.filename,
        "path": att.path,
        "content_type": att.content_type,
        "message_id": att.message_id,
        "created_at": att.created_at.isoformat() + "Z" if att.created_at else None,
    }


def serialize_message(msg: HelpDeskMessage, *, include_internal: bool = True) -> Optional[Dict[str, Any]]:
    if msg.is_internal and not include_internal:
        return None
    author = None
    if msg.author:
        author = user_brief(msg.author)
    return {
        "id": msg.id,
        "query_id": msg.query_id,
        "author": author,
        "author_name": msg.author_name,
        "body": msg.body,
        "is_internal": msg.is_internal,
        "created_at": msg.created_at.isoformat() + "Z" if msg.created_at else None,
        "attachments": [serialize_attachment(a) for a in msg.attachments],
    }


def serialize_query(
    q: HelpDeskQuery,
    *,
    include_messages: bool = False,
    include_internal: bool = False,
) -> Dict[str, Any]:
    assignees = []
    try:
        assignees = [user_brief(u) for u in (q.assignees or [])]
    except Exception:
        assignees = []
    watchers = []
    try:
        watchers = [user_brief(u) for u in (q.watchers or [])]
    except Exception:
        watchers = []

    data: Dict[str, Any] = {
        "id": q.id,
        "title": q.query_title,
        "query_title": q.query_title,
        "description": q.query_description,
        "query_description": q.query_description,
        "status": q.status,
        "priority": getattr(q, "priority", None) or "normal",
        "category": getattr(q, "category", None) or "general",
        "source": getattr(q, "source", None) or "internal",
        "query_type": q.query_type,
        "created_by": q.created_by,
        "requester_email": getattr(q, "requester_email", None),
        "image_path": q.image_path,
        "timestamp": q.timestamp.isoformat() + "Z" if q.timestamp else None,
        "resolved_at": q.resolved_at.isoformat() + "Z" if q.resolved_at else None,
        "first_response_at": (
            q.first_response_at.isoformat() + "Z" if getattr(q, "first_response_at", None) else None
        ),
        "sla_first_response_due": (
            q.sla_first_response_due.isoformat() + "Z"
            if getattr(q, "sla_first_response_due", None)
            else None
        ),
        "sla_resolve_due": (
            q.sla_resolve_due.isoformat() + "Z" if getattr(q, "sla_resolve_due", None) else None
        ),
        "sla_breached": bool(getattr(q, "sla_breached", False)),
        "team_id": getattr(q, "team_id", None),
        "team_name": None,
        "assignees": assignees,
        "watchers": watchers,
        "message_id": getattr(q, "message_id", None),
    }
    try:
        data["team_name"] = q.team.name if q.team else None
    except Exception:
        data["team_name"] = None
    try:
        data["attachments"] = [serialize_attachment(a) for a in q.attachments]
    except Exception:
        data["attachments"] = []

    try:
        if getattr(q, "csat", None):
            data["csat"] = {"rating": q.csat.rating, "comment": q.csat.comment}
    except Exception:
        pass

    if include_messages:
        try:
            msgs = []
            for m in q.thread_messages.order_by(HelpDeskMessage.created_at.asc()).all():
                sm = serialize_message(m, include_internal=include_internal)
                if sm:
                    msgs.append(sm)
            data["messages"] = msgs
        except Exception:
            data["messages"] = []

    return data


def query_visible_to_user(q: HelpDeskQuery, user: User) -> bool:
    if is_viewer():
        return True
    if q.created_by == user.username:
        return True
    if q.created_by == "anonymous":
        return True
    try:
        if user in (q.assignees or []):
            return True
        if user in (q.watchers or []):
            return True
    except Exception:
        pass
    return False


def base_query_for_user():
    """SQLAlchemy query scoped by role."""
    q = HelpDeskQuery.query
    if can_view_inbox():
        return q
    return q.filter(
        or_(
            HelpDeskQuery.created_by == current_user.username,
            HelpDeskQuery.created_by == "anonymous",
        )
    )


def save_upload(file_storage) -> Optional[HelpDeskAttachment]:
    """Save an uploaded file; caller must set query_id / message_id and add to session."""
    if not file_storage or not getattr(file_storage, "filename", None):
        return None
    filename = secure_filename(
        f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{file_storage.filename}"
    )
    folder = current_app.config.get("HELP_DESK_UPLOAD_FOLDER", "static/uploads/helpdesk")
    os.makedirs(folder, exist_ok=True)
    save_path = os.path.join(folder, filename)
    file_storage.save(save_path)
    web_path = "/" + save_path.replace("\\", "/")
    return HelpDeskAttachment(
        filename=file_storage.filename,
        path=web_path,
        content_type=getattr(file_storage, "content_type", None),
    )


def create_ticket(
    *,
    title: str,
    description: str,
    query_type: str = "self",
    created_by: str,
    source: str = "internal",
    priority: str = "normal",
    category: str = "general",
    requester_email: Optional[str] = None,
    message_id: Optional[str] = None,
    team_id: Optional[int] = None,
    image_path: Optional[str] = None,
    auto_assign: bool = True,
) -> HelpDeskQuery:
    priority = (priority or "normal").lower()
    if priority not in VALID_PRIORITIES:
        priority = "normal"
    category = (category or "general").lower()
    if category not in VALID_CATEGORIES:
        category = "general"
    source = source if source in VALID_SOURCES else "internal"

    q = HelpDeskQuery(
        query_title=(title or "").strip()[:200] or "(No subject)",
        query_description=(description or "").strip() or "",
        query_type=query_type if query_type in ("anonymous", "self") else "self",
        created_by=created_by,
        image_path=image_path,
        status="Not started",
        source=source,
        priority=priority,
        category=category,
        requester_email=requester_email,
        message_id=message_id,
        team_id=team_id,
    )
    apply_sla_deadlines(q)
    db.session.add(q)
    db.session.flush()

    # Seed first public message from description
    db.session.add(
        HelpDeskMessage(
            query_id=q.id,
            author_id=None,
            author_name=created_by if created_by != "anonymous" else (requester_email or "Requester"),
            body=q.query_description,
            is_internal=False,
        )
    )

    if auto_assign and team_id:
        assignee = round_robin_assignee(team_id)
        if assignee:
            q.assignees.append(assignee)

    return q


def round_robin_assignee(team_id: int) -> Optional[User]:
    team = db.session.get(HelpDeskTeam, team_id)
    if not team or not team.members:
        return None
    members = list(team.members)
    if not members:
        return None
    key = f"helpdesk_rr_index_{team_id}"
    try:
        idx = int(AppSetting.get_value(key, "0") or "0")
    except Exception:
        idx = 0
    pick = members[idx % len(members)]
    AppSetting.set_value(key, str(idx + 1), description=f"Round-robin cursor for team {team_id}")
    return pick


def mark_first_response(query: HelpDeskQuery, *, actor: User) -> None:
    if query.first_response_at:
        return
    # Only agent replies count as first response
    if not is_agent() and actor.username == query.created_by:
        return
    query.first_response_at = datetime.utcnow()


def set_status(query: HelpDeskQuery, status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError("Invalid status")
    query.status = status
    if status == "Resolved":
        query.resolved_at = datetime.utcnow()
    else:
        query.resolved_at = None


def extract_mentions(body: str) -> List[User]:
    names = set(MENTION_RE.findall(body or ""))
    if not names:
        return []
    users = User.query.filter(User.username.in_(list(names))).all()
    return users


def slugify(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-") or "article"
    slug = base[:180]
    n = 1
    while HelpDeskArticle.query.filter_by(slug=slug).first():
        n += 1
        slug = f"{base[:160]}-{n}"
    return slug


def search_articles(q: str, *, published_only: bool = True, limit: int = 10) -> List[HelpDeskArticle]:
    query = HelpDeskArticle.query
    if published_only:
        query = query.filter_by(published=True)
    term = (q or "").strip()
    if term:
        like = f"%{term}%"
        query = query.filter(
            or_(
                HelpDeskArticle.title.ilike(like),
                HelpDeskArticle.body.ilike(like),
                HelpDeskArticle.tags.ilike(like),
            )
        )
    return query.order_by(HelpDeskArticle.updated_at.desc()).limit(limit).all()


def serialize_article(a: HelpDeskArticle) -> Dict[str, Any]:
    return {
        "id": a.id,
        "title": a.title,
        "slug": a.slug,
        "body": a.body,
        "tags": a.tags,
        "published": a.published,
        "created_at": a.created_at.isoformat() + "Z" if a.created_at else None,
        "updated_at": a.updated_at.isoformat() + "Z" if a.updated_at else None,
    }


def serialize_macro(m: HelpDeskMacro) -> Dict[str, Any]:
    return {
        "id": m.id,
        "title": m.title,
        "body": m.body,
        "category": m.category,
    }


def serialize_team(t: HelpDeskTeam) -> Dict[str, Any]:
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "members": [user_brief(u) for u in t.members],
    }


def check_sla_breaches() -> int:
    """Mark breached tickets and return count newly breached."""
    from app.blueprints.help_desk.notifications import notify_sla_breach

    now = datetime.utcnow()
    open_tickets = HelpDeskQuery.query.filter(HelpDeskQuery.status != "Resolved").all()
    newly = 0
    for q in open_tickets:
        breached = False
        if not q.first_response_at and q.sla_first_response_due and q.sla_first_response_due < now:
            breached = True
        if q.sla_resolve_due and q.sla_resolve_due < now:
            breached = True
        if breached and not q.sla_breached:
            q.sla_breached = True
            newly += 1
            notify_sla_breach(q)
        elif breached:
            q.sla_breached = True
    if newly:
        db.session.commit()
    else:
        db.session.commit()
    return newly
