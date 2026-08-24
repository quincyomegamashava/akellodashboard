"""Help Desk support hub pages and JSON APIs."""

from __future__ import annotations

from datetime import datetime, timedelta

from flask import jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app import db
from app.models import HelpDeskQuery, HelpDeskTeam, Ticket, User

from app.blueprints.help_desk import bp
from app.blueprints.help_desk.models import (
    HelpDeskArticle,
    HelpDeskCSAT,
    HelpDeskMacro,
    HelpDeskMessage,
)
from app.blueprints.help_desk import notifications as hd_notify
from app.blueprints.help_desk.schema import ensure_helpdesk_hub_schema
from app.blueprints.help_desk.services import (
    VALID_CATEGORIES,
    VALID_PRIORITIES,
    VALID_STATUSES,
    admin_required,
    agent_required,
    apply_sla_deadlines,
    base_query_for_user,
    can_manage_settings,
    can_view_inbox,
    create_ticket,
    extract_mentions,
    get_sla_policy,
    is_agent,
    is_viewer,
    mark_first_response,
    query_visible_to_user,
    save_upload,
    search_articles,
    serialize_article,
    serialize_macro,
    serialize_query,
    serialize_team,
    set_sla_policy,
    set_status,
    slugify,
    user_brief,
    viewer_required,
)


def _ctx(**extra):
    ensure_helpdesk_hub_schema()
    data = {
        "title": "Help desk",
        "hd_is_agent": is_agent(),
        "hd_is_viewer": is_viewer(),
        "hd_is_admin": can_manage_settings(),
        "hd_priorities": VALID_PRIORITIES,
        "hd_categories": VALID_CATEGORIES,
        "hd_statuses": VALID_STATUSES,
    }
    data.update(extra)
    return data


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


@bp.route("/")
@login_required
def index():
    """Unified inbox (agents/viewers) or redirect to my tickets."""
    qid = request.args.get("query", type=int)
    if qid:
        return redirect(url_for("help_desk.detail", query_id=qid))
    if not can_view_inbox():
        return redirect(url_for("help_desk.my_tickets"))
    return render_template("help_desk/index.html", **_ctx(hd_active="inbox"))


@bp.route("/my")
@login_required
def my_tickets():
    return render_template("help_desk/my_tickets.html", **_ctx(hd_active="my"))


@bp.route("/email")
@login_required
@viewer_required
def email_page():
    return render_template("help_desk/email.html", **_ctx(hd_active="email"))


@bp.route("/kb")
@login_required
def kb_page():
    return render_template("help_desk/kb.html", **_ctx(hd_active="kb"))


@bp.route("/kb/<slug>")
@login_required
def kb_detail(slug):
    article = HelpDeskArticle.query.filter_by(slug=slug).first_or_404()
    if not article.published and not is_agent():
        return redirect(url_for("help_desk.kb_page"))
    return render_template(
        "help_desk/kb_detail.html",
        article=article,
        **_ctx(hd_active="kb"),
    )


@bp.route("/reports")
@login_required
@viewer_required
def reports_page():
    return render_template("help_desk/reports.html", **_ctx(hd_active="reports"))


@bp.route("/settings")
@login_required
@admin_required
def settings_page():
    return render_template("help_desk/settings.html", **_ctx(hd_active="settings"))


@bp.route("/<int:query_id>")
@login_required
def detail(query_id):
    q = HelpDeskQuery.query.get_or_404(query_id)
    if not query_visible_to_user(q, current_user):
        return redirect(url_for("help_desk.my_tickets"))
    return render_template(
        "help_desk/detail.html",
        query=q,
        **_ctx(hd_active="inbox" if can_view_inbox() else "my"),
    )


@bp.route("/csat/<int:query_id>", methods=["GET", "POST"])
@login_required
def csat_page(query_id):
    q = HelpDeskQuery.query.get_or_404(query_id)
    if q.status != "Resolved":
        return redirect(url_for("help_desk.detail", query_id=query_id))
    if request.method == "POST":
        if request.is_json:
            rating = request.json.get("rating")
            comment = request.json.get("comment")
        else:
            rating = request.form.get("rating", type=int)
            comment = request.form.get("comment")
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            rating = None
        if not rating or rating < 1 or rating > 5:
            if request.is_json:
                return jsonify({"error": "Rating 1-5 required"}), 400
            return render_template("help_desk/csat.html", query=q, error="Pick a rating 1–5", **_ctx())
        existing = db.session.query(HelpDeskCSAT).filter_by(query_id=q.id).first()
        if existing:
            existing.rating = rating
            existing.comment = comment
        else:
            db.session.add(HelpDeskCSAT(query_id=q.id, rating=rating, comment=comment))
        db.session.commit()
        if request.is_json:
            return jsonify({"ok": True})
        return render_template("help_desk/csat.html", query=q, done=True, **_ctx())
    return render_template("help_desk/csat.html", query=q, **_ctx())


# ---------------------------------------------------------------------------
# Ticket list / CRUD APIs
# ---------------------------------------------------------------------------


@bp.route("/api/tickets")
@login_required
def api_tickets():
    ensure_helpdesk_hub_schema()
    q = base_query_for_user()
    status = request.args.get("status")
    priority = request.args.get("priority")
    category = request.args.get("category")
    source = request.args.get("source")
    assignee_id = request.args.get("assignee_id", type=int)
    team_id = request.args.get("team_id", type=int)
    mine = request.args.get("mine") in ("1", "true", "yes")
    search = (request.args.get("q") or "").strip()

    if status:
        q = q.filter(HelpDeskQuery.status == status)
    if priority:
        q = q.filter(HelpDeskQuery.priority == priority)
    if category:
        q = q.filter(HelpDeskQuery.category == category)
    if source:
        q = q.filter(HelpDeskQuery.source == source)
    if team_id:
        q = q.filter(HelpDeskQuery.team_id == team_id)
    if mine:
        q = q.filter(HelpDeskQuery.created_by == current_user.username)
    if assignee_id:
        q = q.filter(HelpDeskQuery.assignees.any(User.id == assignee_id))
    if search:
        like = f"%{search}%"
        q = q.filter(
            or_(
                HelpDeskQuery.query_title.ilike(like),
                HelpDeskQuery.query_description.ilike(like),
                HelpDeskQuery.requester_email.ilike(like),
            )
        )

    tickets = (
        q.options(joinedload(HelpDeskQuery.assignees))
        .order_by(HelpDeskQuery.timestamp.desc())
        .limit(200)
        .all()
    )
    return jsonify({"tickets": [serialize_query(t) for t in tickets]})


@bp.route("/api/tickets", methods=["POST"])
@login_required
def api_create_ticket():
    ensure_helpdesk_hub_schema()
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or data.get("query_title") or "").strip()
    description = (data.get("description") or data.get("query_description") or "").strip()
    if not title or not description:
        return jsonify({"error": "Title and description required"}), 400

    qtype = data.get("query_type") or "self"
    created_by = "anonymous" if qtype == "anonymous" else current_user.username
    priority = data.get("priority") or "normal"
    category = data.get("category") or "general"
    team_id = data.get("team_id")

    ticket = create_ticket(
        title=title,
        description=description,
        query_type=qtype,
        created_by=created_by,
        source="internal",
        priority=priority,
        category=category,
        team_id=team_id,
        auto_assign=bool(team_id),
    )

    # Multi-file from multipart alternative
    files = request.files.getlist("files") if request.files else []
    for f in files:
        att = save_upload(f)
        if att:
            att.query_id = ticket.id
            db.session.add(att)
            if not ticket.image_path:
                ticket.image_path = att.path

    db.session.commit()

    if ticket.assignees:
        hd_notify.notify_assignees(ticket, [u.id for u in ticket.assignees], current_user.id)
        db.session.commit()

    return jsonify({"ticket": serialize_query(ticket, include_messages=True, include_internal=is_agent())}), 201


@bp.route("/api/tickets/<int:query_id>")
@login_required
def api_ticket_detail(query_id):
    ensure_helpdesk_hub_schema()
    q = HelpDeskQuery.query.get_or_404(query_id)
    if not query_visible_to_user(q, current_user):
        return jsonify({"error": "Forbidden"}), 403
    return jsonify(
        {
            "ticket": serialize_query(
                q,
                include_messages=True,
                include_internal=is_agent(),
            )
        }
    )


@bp.route("/api/tickets/<int:query_id>", methods=["PATCH"])
@login_required
@agent_required
def api_update_ticket(query_id):
    q = HelpDeskQuery.query.get_or_404(query_id)
    data = request.get_json(silent=True) or {}

    if "status" in data:
        set_status(q, data["status"])
        if data["status"] == "Resolved":
            hd_notify.notify_resolution(q, current_user.id)

    if "priority" in data and data["priority"] in VALID_PRIORITIES:
        q.priority = data["priority"]
        apply_sla_deadlines(q)

    if "category" in data and data["category"] in VALID_CATEGORIES:
        q.category = data["category"]

    if "title" in data or "query_title" in data:
        q.query_title = (data.get("title") or data.get("query_title") or q.query_title)[:200]

    if "team_id" in data:
        q.team_id = data["team_id"] or None

    if "assignee_ids" in data:
        ids = data["assignee_ids"] or []
        users = User.query.filter(User.id.in_(ids)).all() if ids else []
        old_ids = {u.id for u in q.assignees}
        q.assignees = users
        new_ids = {u.id for u in users} - old_ids
        if new_ids:
            hd_notify.notify_assignees(q, new_ids, current_user.id)

    if "watcher_ids" in data:
        ids = data["watcher_ids"] or []
        users = User.query.filter(User.id.in_(ids)).all() if ids else []
        q.watchers = users

    db.session.commit()
    return jsonify({"ticket": serialize_query(q, include_messages=True, include_internal=True)})


@bp.route("/api/tickets/<int:query_id>", methods=["DELETE"])
@login_required
@admin_required
def api_delete_ticket(query_id):
    q = HelpDeskQuery.query.get_or_404(query_id)
    db.session.delete(q)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/tickets/<int:query_id>/messages", methods=["POST"])
@login_required
def api_add_message(query_id):
    q = HelpDeskQuery.query.get_or_404(query_id)
    if not query_visible_to_user(q, current_user):
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    if not body and not request.files:
        return jsonify({"error": "Message body required"}), 400

    is_internal = bool(data.get("is_internal"))
    if is_internal and not is_agent():
        return jsonify({"error": "Only agents can leave internal notes"}), 403

    # Requesters can only post public replies on their own tickets
    if not is_agent() and q.created_by not in (current_user.username, "anonymous"):
        return jsonify({"error": "Forbidden"}), 403

    msg = HelpDeskMessage(
        query_id=q.id,
        author_id=current_user.id,
        author_name=f"{current_user.firstname} {current_user.lastname}".strip() or current_user.username,
        body=body or "(attachment)",
        is_internal=is_internal,
    )
    db.session.add(msg)
    db.session.flush()

    if is_agent() and not is_internal:
        mark_first_response(q, actor=current_user)
        if q.status == "Not started":
            q.status = "Looking into it"

    files = request.files.getlist("files") if request.files else []
    for f in files:
        att = save_upload(f)
        if att:
            att.query_id = q.id
            att.message_id = msg.id
            db.session.add(att)

    mentioned = extract_mentions(body)
    if mentioned:
        hd_notify.notify_mentions(q, mentioned, current_user.id)
        for u in mentioned:
            if u not in q.watchers:
                q.watchers.append(u)

    hd_notify.notify_watchers_reply(q, current_user.id, is_internal=is_internal)
    db.session.commit()
    return jsonify(
        {
            "message": {
                "id": msg.id,
                "body": msg.body,
                "is_internal": msg.is_internal,
                "created_at": msg.created_at.isoformat() + "Z",
                "author": user_brief(current_user),
            },
            "ticket": serialize_query(q, include_messages=True, include_internal=is_agent()),
        }
    ), 201


@bp.route("/api/tickets/<int:query_id>/attachments", methods=["POST"])
@login_required
def api_add_attachments(query_id):
    q = HelpDeskQuery.query.get_or_404(query_id)
    if not query_visible_to_user(q, current_user):
        return jsonify({"error": "Forbidden"}), 403
    files = request.files.getlist("files")
    saved = []
    for f in files:
        att = save_upload(f)
        if att:
            att.query_id = q.id
            db.session.add(att)
            saved.append(att)
            if not q.image_path:
                q.image_path = att.path
    db.session.commit()
    return jsonify({"attachments": [{"id": a.id, "filename": a.filename, "path": a.path} for a in saved]})


# ---------------------------------------------------------------------------
# Email sync
# ---------------------------------------------------------------------------


@bp.route("/api/email/sync", methods=["POST"])
@login_required
@agent_required
def api_email_sync():
    from flask import current_app
    from app.blueprints.help_desk.email_ingest import fetch_emails_into_queries

    count, err = fetch_emails_into_queries(current_app._get_current_object())
    if err and count == 0:
        return jsonify({"ok": False, "error": err, "created": 0}), 400
    return jsonify({"ok": True, "created": count, "warning": err})


@bp.route("/api/email/migrate-legacy", methods=["POST"])
@login_required
@admin_required
def api_migrate_legacy_tickets():
    from app.blueprints.help_desk.email_ingest import migrate_legacy_ticket

    tickets = Ticket.query.order_by(Ticket.created_at.desc()).limit(500).all()
    created = 0
    for t in tickets:
        before = HelpDeskQuery.query.filter_by(message_id=t.message_id).first() if t.message_id else None
        q = migrate_legacy_ticket(t)
        if q and not before:
            created += 1
    return jsonify({"ok": True, "migrated": created})


# ---------------------------------------------------------------------------
# Macros
# ---------------------------------------------------------------------------


@bp.route("/api/macros")
@login_required
@agent_required
def api_macros():
    macros = HelpDeskMacro.query.order_by(HelpDeskMacro.title.asc()).all()
    return jsonify({"macros": [serialize_macro(m) for m in macros]})


@bp.route("/api/macros", methods=["POST"])
@login_required
@admin_required
def api_create_macro():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    if not title or not body:
        return jsonify({"error": "Title and body required"}), 400
    m = HelpDeskMacro(
        title=title,
        body=body,
        category=data.get("category"),
        created_by=current_user.id,
    )
    db.session.add(m)
    db.session.commit()
    return jsonify({"macro": serialize_macro(m)}), 201


@bp.route("/api/macros/<int:macro_id>", methods=["PUT", "DELETE"])
@login_required
@admin_required
def api_macro_detail(macro_id):
    m = HelpDeskMacro.query.get_or_404(macro_id)
    if request.method == "DELETE":
        db.session.delete(m)
        db.session.commit()
        return jsonify({"ok": True})
    data = request.get_json(silent=True) or {}
    if "title" in data:
        m.title = data["title"]
    if "body" in data:
        m.body = data["body"]
    if "category" in data:
        m.category = data["category"]
    db.session.commit()
    return jsonify({"macro": serialize_macro(m)})


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------


@bp.route("/api/articles")
@login_required
def api_articles():
    q = (request.args.get("q") or "").strip()
    published_only = not is_agent() or request.args.get("all") not in ("1", "true")
    if is_agent() and request.args.get("all") in ("1", "true"):
        published_only = False
    articles = search_articles(q, published_only=published_only, limit=50)
    return jsonify({"articles": [serialize_article(a) for a in articles]})


@bp.route("/api/articles", methods=["POST"])
@login_required
@agent_required
def api_create_article():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    if not title or not body:
        return jsonify({"error": "Title and body required"}), 400
    a = HelpDeskArticle(
        title=title,
        slug=slugify(title),
        body=body,
        tags=data.get("tags"),
        published=bool(data.get("published")),
        created_by=current_user.id,
    )
    db.session.add(a)
    db.session.commit()
    return jsonify({"article": serialize_article(a)}), 201


@bp.route("/api/articles/<int:article_id>", methods=["PUT", "DELETE"])
@login_required
@agent_required
def api_article_detail(article_id):
    a = HelpDeskArticle.query.get_or_404(article_id)
    if request.method == "DELETE":
        if not can_manage_settings():
            return jsonify({"error": "Forbidden"}), 403
        db.session.delete(a)
        db.session.commit()
        return jsonify({"ok": True})
    data = request.get_json(silent=True) or {}
    if "title" in data:
        a.title = data["title"]
    if "body" in data:
        a.body = data["body"]
    if "tags" in data:
        a.tags = data["tags"]
    if "published" in data:
        a.published = bool(data["published"])
    db.session.commit()
    return jsonify({"article": serialize_article(a)})


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------


@bp.route("/api/teams")
@login_required
@viewer_required
def api_teams():
    teams = HelpDeskTeam.query.order_by(HelpDeskTeam.name.asc()).all()
    return jsonify({"teams": [serialize_team(t) for t in teams]})


@bp.route("/api/teams", methods=["POST"])
@login_required
@admin_required
def api_create_team():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    t = HelpDeskTeam(name=name, description=data.get("description"))
    member_ids = data.get("member_ids") or []
    if member_ids:
        t.members = User.query.filter(User.id.in_(member_ids)).all()
    db.session.add(t)
    db.session.commit()
    return jsonify({"team": serialize_team(t)}), 201


@bp.route("/api/teams/<int:team_id>", methods=["PUT", "DELETE"])
@login_required
@admin_required
def api_team_detail(team_id):
    t = HelpDeskTeam.query.get_or_404(team_id)
    if request.method == "DELETE":
        db.session.delete(t)
        db.session.commit()
        return jsonify({"ok": True})
    data = request.get_json(silent=True) or {}
    if "name" in data:
        t.name = data["name"]
    if "description" in data:
        t.description = data["description"]
    if "member_ids" in data:
        ids = data["member_ids"] or []
        t.members = User.query.filter(User.id.in_(ids)).all() if ids else []
    db.session.commit()
    return jsonify({"team": serialize_team(t)})


# ---------------------------------------------------------------------------
# Settings / SLA / reports / users
# ---------------------------------------------------------------------------


@bp.route("/api/sla", methods=["GET", "PUT"])
@login_required
def api_sla():
    if request.method == "GET":
        return jsonify({"policy": get_sla_policy()})
    if not can_manage_settings():
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json(silent=True) or {}
    policy = data.get("policy") or data
    set_sla_policy(policy, user_id=current_user.id)
    return jsonify({"policy": get_sla_policy()})


@bp.route("/api/stats")
@login_required
@viewer_required
def api_stats():
    total = HelpDeskQuery.query.count()
    resolved = HelpDeskQuery.query.filter_by(status="Resolved").count()
    not_started = HelpDeskQuery.query.filter_by(status="Not started").count()
    looking = HelpDeskQuery.query.filter_by(status="Looking into it").count()
    breached = HelpDeskQuery.query.filter_by(sla_breached=True).filter(HelpDeskQuery.status != "Resolved").count()

    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    volume = []
    for i in range(6, -1, -1):
        day = (datetime.utcnow() - timedelta(days=i)).date()
        day_start = datetime.combine(day, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        count = HelpDeskQuery.query.filter(
            HelpDeskQuery.timestamp >= day_start,
            HelpDeskQuery.timestamp < day_end,
        ).count()
        volume.append({"date": day.isoformat(), "count": count})

    # Avg resolution hours
    resolved_rows = HelpDeskQuery.query.filter(
        HelpDeskQuery.status == "Resolved",
        HelpDeskQuery.resolved_at.isnot(None),
        HelpDeskQuery.timestamp.isnot(None),
    ).all()
    hours = []
    for r in resolved_rows:
        try:
            delta = (r.resolved_at - r.timestamp).total_seconds() / 3600.0
            if delta >= 0:
                hours.append(delta)
        except Exception:
            pass
    avg_resolution = round(sum(hours) / len(hours), 1) if hours else None

    # SLA % among resolved with deadline
    with_sla = [r for r in resolved_rows if r.sla_resolve_due]
    sla_met = sum(1 for r in with_sla if r.resolved_at and r.resolved_at <= r.sla_resolve_due)
    sla_pct = round(100.0 * sla_met / len(with_sla), 1) if with_sla else None

    # By category
    by_category = (
        db.session.query(HelpDeskQuery.category, func.count(HelpDeskQuery.id))
        .group_by(HelpDeskQuery.category)
        .all()
    )
    # By priority
    by_priority = (
        db.session.query(HelpDeskQuery.priority, func.count(HelpDeskQuery.id))
        .group_by(HelpDeskQuery.priority)
        .all()
    )

    csat_avg = db.session.query(func.avg(HelpDeskCSAT.rating)).scalar()
    csat_count = db.session.query(HelpDeskCSAT).count()

    return jsonify(
        {
            "total": total,
            "resolved": resolved,
            "unresolved": total - resolved,
            "not_started": not_started,
            "looking_into": looking,
            "success_rate": round(100.0 * resolved / total, 1) if total else 0,
            "sla_breached_open": breached,
            "avg_resolution_hours": avg_resolution,
            "sla_met_percent": sla_pct,
            "volume_7d": volume,
            "by_category": [{"category": c or "general", "count": n} for c, n in by_category],
            "by_priority": [{"priority": p or "normal", "count": n} for p, n in by_priority],
            "csat_average": round(float(csat_avg), 2) if csat_avg is not None else None,
            "csat_count": csat_count,
            "email_count": HelpDeskQuery.query.filter_by(source="email").count(),
            "internal_count": HelpDeskQuery.query.filter_by(source="internal").count(),
        }
    )


@bp.route("/api/users")
@login_required
@agent_required
def api_users():
    q = (request.args.get("q") or "").strip()
    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                User.username.ilike(like),
                User.email.ilike(like),
                User.firstname.ilike(like),
                User.lastname.ilike(like),
            )
        )
    users = query.order_by(User.firstname.asc()).limit(40).all()
    return jsonify({"users": [user_brief(u) for u in users]})


@bp.route("/api/me")
@login_required
def api_me():
    return jsonify(
        {
            "user": user_brief(current_user),
            "is_agent": is_agent(),
            "is_viewer": is_viewer(),
            "is_admin": can_manage_settings(),
            "can_view_inbox": can_view_inbox(),
        }
    )
