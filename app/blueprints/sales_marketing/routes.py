"""Sales & Marketing routes: public stakeholder form + staff hub."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Any, List, Optional

from flask import (
    Response,
    jsonify,
    render_template,
    request,
    stream_with_context,
)
from flask_login import current_user
from sqlalchemy.orm import joinedload

from app import db
from app.email_utils import send_bulk_html_emails

from app.blueprints.sales_marketing import bp
from app.blueprints.sales_marketing.models import (
    EmailCampaign,
    EmailCampaignRecipient,
    InterestOption,
    MarketingEvent,
    StakeholderLead,
    StakeholderLeadNote,
)
from app.blueprints.sales_marketing.services import (
    HEARD_ABOUT_OPTIONS,
    ROLE_CATEGORIES,
    VALID_LEAD_STATUSES,
    ZIMBABWE_PROVINCES,
    apply_event_attendees,
    campaign_recipient_to_dict,
    campaign_to_dict,
    can_access_sales_marketing,
    check_duplicate_lead,
    check_rate_limit,
    event_to_dict,
    events_active_on_date,
    events_query,
    interest_option_to_dict,
    lead_to_dict,
    leads_query,
    normalize_email,
    note_to_dict,
    record_rate_limit_hit,
    sales_marketing_required,
    seed_interest_options_if_empty,
    stakeholder_db_guard,
    stakeholders_stats,
    user_options,
    validate_email,
)


def _parse_date(val: Optional[str]) -> Optional[date]:
    if not val:
        return None
    try:
        return date.fromisoformat(str(val)[:10])
    except (TypeError, ValueError):
        return None


def _lead_filters_from_request():
    return dict(
        event_id=int(request.args["event_id"]) if request.args.get("event_id") else None,
        province=request.args.get("province"),
        interest_option_id=int(request.args["interest_option_id"])
        if request.args.get("interest_option_id")
        else None,
        consent_only=request.args.get("consent_only") == "1",
        search=request.args.get("search"),
        date_from=_parse_date(request.args.get("date_from")),
        date_to=_parse_date(request.args.get("date_to")),
        attendee_user_id=int(request.args["attendee_user_id"])
        if request.args.get("attendee_user_id")
        else None,
        follow_up_status=request.args.get("status"),
        duplicates_only=request.args.get("duplicates_only") == "1",
    )


def _wants_json() -> bool:
    return (
        request.accept_mimetypes.best_match(["application/json", "text/html"]) == "application/json"
        or request.path.startswith("/api/")
    )


# --- Public routes ---


def connect_page():
    seed_interest_options_if_empty()
    options = (
        InterestOption.query.filter_by(is_active=True)
        .order_by(InterestOption.sort_order, InterestOption.id)
        .all()
    )
    today = date.today().isoformat()
    prefill_event_id = None
    prefill_event = None
    raw_event = request.args.get("event")
    if raw_event:
        try:
            eid = int(raw_event)
            ev = db.session.get(MarketingEvent, eid)
            if ev and ev.status == "active":
                prefill_event_id = ev.id
                prefill_event = {"id": ev.id, "name": ev.name, "location": ev.location or "", "banner_text": getattr(ev, "banner_text", None) or ""}
        except (TypeError, ValueError):
            pass
    return render_template(
        "sales_marketing/public_form.html",
        title="Connect with Akello",
        provinces=ZIMBABWE_PROVINCES,
        role_categories=ROLE_CATEGORIES,
        heard_about_options=HEARD_ABOUT_OPTIONS,
        interest_options=options,
        today=today,
        prefill_event_id=prefill_event_id,
        prefill_event=prefill_event,
    )


def api_public_marketing_events():
    d = _parse_date(request.args.get("date")) or date.today()
    events = events_active_on_date(d)
    return jsonify([{"id": e.id, "name": e.name, "location": e.location or ""} for e in events])


def api_public_interest_options():
    seed_interest_options_if_empty()
    opts = (
        InterestOption.query.filter_by(is_active=True)
        .order_by(InterestOption.sort_order, InterestOption.id)
        .all()
    )
    return jsonify([interest_option_to_dict(o) for o in opts])


def api_public_submit_lead():
    payload = request.get_json(silent=True) or request.form.to_dict()

    if (payload.get("website") or "").strip():
        return jsonify({"ok": True})

    if not check_rate_limit():
        return jsonify({"error": "Too many submissions. Please try again later."}), 429

    full_name = (payload.get("full_name") or "").strip()
    email = normalize_email(payload.get("email") or "")
    mobile = (payload.get("mobile") or "").strip()
    occupation = (payload.get("occupation") or "").strip()

    if not full_name or not email or not mobile or not occupation:
        return jsonify({"error": "Full name, occupation, email, and mobile are required."}), 400
    if not validate_email(email):
        return jsonify({"error": "Invalid email address."}), 400
    if not payload.get("consent_marketing"):
        return jsonify({"error": "Consent is required to submit."}), 400

    try:
        interest_id = int(payload.get("interest_option_id") or 0)
    except (TypeError, ValueError):
        interest_id = 0
    if not interest_id or not db.session.get(InterestOption, interest_id):
        return jsonify({"error": "Please select an interest option."}), 400

    event_id = None
    raw_event = payload.get("event_id")
    if raw_event not in (None, "", "0", 0):
        try:
            event_id = int(raw_event)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid event."}), 400
        ev = db.session.get(MarketingEvent, event_id)
        if not ev or ev.status != "active":
            return jsonify({"error": "Invalid event."}), 400

    is_dup = check_duplicate_lead(email, event_id)
    lead = StakeholderLead(
        full_name=full_name[:255],
        occupation=occupation[:255],
        email=email[:255],
        mobile=mobile[:64],
        school_name=(payload.get("school_name") or "").strip()[:255] or None,
        province=(payload.get("province") or "").strip()[:120] or None,
        organization=(payload.get("organization") or "").strip()[:255] or None,
        role_category=(payload.get("role_category") or "").strip()[:64] or None,
        event_id=event_id,
        interest_option_id=interest_id,
        preferred_contact=(payload.get("preferred_contact") or "email").strip()[:32],
        consent_marketing=True,
        comments=(payload.get("comments") or "").strip() or None,
        heard_about=(payload.get("heard_about") or "").strip()[:120] or None,
        source="public_form",
        is_duplicate_flag=is_dup,
        submitted_at=datetime.utcnow(),
    )
    db.session.add(lead)
    record_rate_limit_hit()
    db.session.flush()
    from app.blueprints.sales_marketing.services import log_lead_activity, update_lead_score
    from app.blueprints.sales_marketing.notifications import notify_hot_lead, notify_new_lead

    log_lead_activity(lead.id, "form_submit", f"Submitted via public form: {full_name}")
    update_lead_score(lead)
    db.session.commit()
    notify_new_lead(lead)
    io = db.session.get(InterestOption, interest_id)
    if (lead.role_category or "").lower() == "principal" and io and "demo" in (io.label or "").lower():
        notify_hot_lead(lead)
    return jsonify({"ok": True, "duplicate_warning": is_dup}), 201


# --- Staff HTML pages ---


@bp.route("/")
@sales_marketing_required
def index():
    seed_interest_options_if_empty()
    return render_template(
        "sales_marketing/stakeholders.html",
        title="Sales & Marketing",
        provinces=ZIMBABWE_PROVINCES,
        user_opts=user_options(),
    )


@bp.route("/events")
@sales_marketing_required
def events_page():
    return render_template(
        "sales_marketing/events.html",
        title="Marketing Events",
        user_opts=user_options(),
    )


@bp.route("/events/roadmap")
@sales_marketing_required
def events_roadmap_page():
    return render_template("sales_marketing/roadmap.html", title="Events Roadmap")


@bp.route("/settings")
@sales_marketing_required
def settings_page():
    return render_template("sales_marketing/settings.html", title="Interest Options")


@bp.route("/campaigns")
@sales_marketing_required
def campaigns_page():
    return render_template("sales_marketing/campaigns.html", title="Email Campaigns")


# --- Staff JSON APIs ---


@bp.route("/api/users")
@sales_marketing_required
def api_users():
    q = (request.args.get("q") or "").strip().lower()
    users = user_options()
    if q:
        users = [u for u in users if q in u["label"].lower() or q in (u.get("department") or "").lower()]
    return jsonify(users[:100])


@bp.route("/api/events", methods=["GET", "POST"])
@sales_marketing_required
def api_events_list_create():
    if request.method == "GET":
        timeline = request.args.get("timeline") or "all"
        my_events = request.args.get("my_events") == "1"
        events = events_query(
            timeline=timeline,
            location_q=request.args.get("location"),
            my_events=my_events,
            current_user_id=current_user.id if my_events else None,
        )
        return jsonify([event_to_dict(e) for e in events])

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    start_d = _parse_date(payload.get("start_date"))
    end_d = _parse_date(payload.get("end_date"))
    if not name or not start_d or not end_d:
        return jsonify({"error": "name, start_date, end_date required"}), 400
    if end_d < start_d:
        return jsonify({"error": "end_date must be on or after start_date"}), 400

    event = MarketingEvent(
        name=name[:255],
        start_date=start_d,
        end_date=end_d,
        location=(payload.get("location") or "").strip()[:255] or None,
        status=(payload.get("status") or "active").strip()[:32],
        notes=(payload.get("notes") or "").strip() or None,
        created_by=current_user.id,
    )
    from app.blueprints.sales_marketing.services import ensure_unique_event_slug, slugify_event_name

    base_slug = slugify_event_name(name)
    event.slug = ensure_unique_event_slug(base_slug)
    if payload.get("banner_text"):
        event.banner_text = (payload.get("banner_text") or "").strip() or None
    if payload.get("cost_estimate") is not None:
        try:
            event.cost_estimate = float(payload.get("cost_estimate"))
        except (TypeError, ValueError):
            pass
    db.session.add(event)
    db.session.flush()
    apply_event_attendees(event, payload.get("attendee_ids"))
    db.session.commit()
    db.session.refresh(event)
    return jsonify(event_to_dict(event)), 201


@bp.route("/api/events/roadmap")
@sales_marketing_required
def api_events_roadmap():
    timeline = request.args.get("timeline") or "all"
    my_events = request.args.get("my_events") == "1"
    events = events_query(
        timeline=timeline,
        location_q=request.args.get("location"),
        my_events=my_events,
        current_user_id=current_user.id if my_events else None,
    )
    grouped = {"ongoing": [], "upcoming": [], "past": [], "cancelled": []}
    for e in events:
        d = event_to_dict(e)
        bucket = d["timeline_status"]
        if bucket not in grouped:
            bucket = "past"
        grouped[bucket].append(d)
    return jsonify(grouped)


@bp.route("/api/events/<int:event_id>", methods=["GET", "PUT", "DELETE"])
@sales_marketing_required
def api_event_detail(event_id: int):
    event = (
        MarketingEvent.query.options(joinedload(MarketingEvent.attendees))
        .filter_by(id=event_id)
        .first()
    )
    if not event:
        return jsonify({"error": "Not found"}), 404

    if request.method == "GET":
        return jsonify(event_to_dict(event))

    if request.method == "DELETE":
        db.session.delete(event)
        db.session.commit()
        return jsonify({"ok": True})

    payload = request.get_json(silent=True) or {}
    if "name" in payload:
        event.name = (payload.get("name") or "").strip()[:255]
    if "start_date" in payload:
        sd = _parse_date(payload.get("start_date"))
        if sd:
            event.start_date = sd
    if "end_date" in payload:
        ed = _parse_date(payload.get("end_date"))
        if ed:
            event.end_date = ed
    if event.end_date < event.start_date:
        return jsonify({"error": "end_date must be on or after start_date"}), 400
    if "location" in payload:
        event.location = (payload.get("location") or "").strip()[:255] or None
    if "status" in payload:
        event.status = (payload.get("status") or "active").strip()[:32]
    if "notes" in payload:
        event.notes = (payload.get("notes") or "").strip() or None
    if "banner_text" in payload:
        event.banner_text = (payload.get("banner_text") or "").strip() or None
    if "cost_estimate" in payload:
        try:
            event.cost_estimate = float(payload.get("cost_estimate")) if payload.get("cost_estimate") not in (None, "") else None
        except (TypeError, ValueError):
            pass
    if "latitude" in payload:
        try:
            event.latitude = float(payload.get("latitude")) if payload.get("latitude") not in (None, "") else None
        except (TypeError, ValueError):
            pass
    if "longitude" in payload:
        try:
            event.longitude = float(payload.get("longitude")) if payload.get("longitude") not in (None, "") else None
        except (TypeError, ValueError):
            pass
    if "slug" in payload and (payload.get("slug") or "").strip():
        from app.blueprints.sales_marketing.services import ensure_unique_event_slug, slugify_event_name
        event.slug = ensure_unique_event_slug(slugify_event_name(payload.get("slug")), exclude_id=event.id)
    elif "name" in payload and not getattr(event, "slug", None):
        from app.blueprints.sales_marketing.services import ensure_unique_event_slug, slugify_event_name
        event.slug = ensure_unique_event_slug(slugify_event_name(event.name), exclude_id=event.id)
    if "attendee_ids" in payload:
        apply_event_attendees(event, payload.get("attendee_ids"))
    event.updated_at = datetime.utcnow()
    db.session.commit()
    db.session.refresh(event)
    return jsonify(event_to_dict(event))


@bp.route("/api/stakeholders/stats")
@sales_marketing_required
@stakeholder_db_guard
def api_stakeholders_stats():
    base = stakeholders_stats()
    event_id = request.args.get("event_id")
    if event_id:
        try:
            eid = int(event_id)
            base["total_leads"] = StakeholderLead.query.filter_by(event_id=eid).count()
            base["event_id"] = eid
            latest = (
                StakeholderLead.query.filter_by(event_id=eid)
                .order_by(StakeholderLead.submitted_at.desc())
                .limit(5)
                .all()
            )
            base["latest_leads"] = [lead_to_dict(l) for l in latest]
        except (TypeError, ValueError):
            pass
    return jsonify(base)


@bp.route("/api/stakeholders/preview-count")
@sales_marketing_required
def api_stakeholders_preview_count():
    f = _lead_filters_from_request()
    f["consent_only"] = True
    count = leads_query(**f).count()
    return jsonify({"count": count, "consent_only": True})


@bp.route("/api/stakeholders")
@sales_marketing_required
@stakeholder_db_guard
def api_stakeholders_list():
    page = max(1, int(request.args.get("page") or 1))
    per_page = min(100, max(10, int(request.args.get("per_page") or 25)))
    q = leads_query(**_lead_filters_from_request())
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "items": [lead_to_dict(i) for i in pagination.items],
            "page": pagination.page,
            "pages": pagination.pages,
            "total": pagination.total,
        }
    )


@bp.route("/api/stakeholders/export")
@sales_marketing_required
def api_stakeholders_export():
    q = leads_query(**_lead_filters_from_request())
    leads = q.limit(5000).all()

    def generate():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Name",
                "Email",
                "Mobile",
                "Occupation",
                "School",
                "Province",
                "Organization",
                "Event",
                "Interest",
                "Status",
                "Consent",
                "Source",
                "Heard about",
                "Duplicate",
                "Comments",
                "Submitted",
            ]
        )
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
        for lead in leads:
            d = lead_to_dict(lead)
            writer.writerow(
                [
                    d["full_name"],
                    d["email"],
                    d["mobile"],
                    d["occupation"],
                    d["school_name"],
                    d["province"],
                    d.get("organization", ""),
                    d["event_name"],
                    d["interest_label"],
                    d.get("follow_up_status", "new"),
                    "yes" if d["consent_marketing"] else "no",
                    d.get("source", ""),
                    d.get("heard_about", ""),
                    "yes" if d.get("is_duplicate_flag") else "no",
                    d.get("comments", ""),
                    d["submitted_at"],
                ]
            )
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return Response(
        stream_with_context(generate()),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=stakeholder_leads.csv"},
    )


@bp.route("/api/stakeholders", methods=["POST"])
@sales_marketing_required
def api_stakeholders_create():
    payload = request.get_json(silent=True) or {}
    email = normalize_email(payload.get("email") or "")
    if not (payload.get("full_name") or "").strip() or not validate_email(email):
        return jsonify({"error": "full_name and valid email required"}), 400

    lead = StakeholderLead(
        full_name=(payload.get("full_name") or "").strip()[:255],
        occupation=(payload.get("occupation") or "").strip()[:255],
        email=email[:255],
        mobile=(payload.get("mobile") or "").strip()[:64],
        school_name=(payload.get("school_name") or "").strip()[:255] or None,
        province=(payload.get("province") or "").strip()[:120] or None,
        organization=(payload.get("organization") or "").strip()[:255] or None,
        role_category=(payload.get("role_category") or "").strip()[:64] or None,
        event_id=int(payload["event_id"]) if payload.get("event_id") else None,
        interest_option_id=int(payload["interest_option_id"])
        if payload.get("interest_option_id")
        else None,
        preferred_contact=(payload.get("preferred_contact") or "email")[:32],
        consent_marketing=bool(payload.get("consent_marketing")),
        comments=(payload.get("comments") or "").strip() or None,
        heard_about=(payload.get("heard_about") or "").strip()[:120] or None,
        source="manual_entry",
        follow_up_status=(payload.get("follow_up_status") or "new").strip()[:32],
        created_by=current_user.id,
        submitted_at=datetime.utcnow(),
    )
    db.session.add(lead)
    db.session.commit()
    return jsonify(lead_to_dict(lead)), 201


@bp.route("/api/stakeholders/<int:lead_id>", methods=["GET", "PUT", "DELETE"])
@sales_marketing_required
def api_stakeholder_detail(lead_id: int):
    lead = (
        StakeholderLead.query.options(
            joinedload(StakeholderLead.event),
            joinedload(StakeholderLead.interest_option),
        )
        .filter_by(id=lead_id)
        .first()
    )
    if not lead:
        return jsonify({"error": "Not found"}), 404

    if request.method == "GET":
        data = lead_to_dict(lead)
        notes = (
            StakeholderLeadNote.query.filter_by(lead_id=lead.id)
            .order_by(StakeholderLeadNote.created_at.desc())
            .limit(50)
            .all()
        )
        data["notes"] = [note_to_dict(n) for n in notes]
        return jsonify(data)

    if request.method == "DELETE":
        db.session.delete(lead)
        db.session.commit()
        return jsonify({"ok": True})

    payload = request.get_json(silent=True) or {}
    for field, key in [
        ("full_name", "full_name"),
        ("occupation", "occupation"),
        ("mobile", "mobile"),
        ("school_name", "school_name"),
        ("province", "province"),
        ("organization", "organization"),
        ("role_category", "role_category"),
        ("comments", "comments"),
        ("heard_about", "heard_about"),
        ("preferred_contact", "preferred_contact"),
    ]:
        if key in payload:
            setattr(lead, field, (payload.get(key) or "").strip() or None)
    if "email" in payload:
        email = normalize_email(payload.get("email") or "")
        if not validate_email(email):
            return jsonify({"error": "Invalid email"}), 400
        lead.email = email
    if "event_id" in payload:
        lead.event_id = int(payload["event_id"]) if payload.get("event_id") else None
    if "interest_option_id" in payload:
        lead.interest_option_id = (
            int(payload["interest_option_id"]) if payload.get("interest_option_id") else None
        )
    if "consent_marketing" in payload:
        lead.consent_marketing = bool(payload.get("consent_marketing"))
    if "follow_up_status" in payload:
        st = (payload.get("follow_up_status") or "new").strip()
        if st in VALID_LEAD_STATUSES:
            old_st = lead.follow_up_status
            lead.follow_up_status = st
            if old_st != st:
                from app.blueprints.sales_marketing.services import log_lead_activity, update_lead_score
                log_lead_activity(
                    lead.id,
                    "status_change",
                    f"Status changed from {old_st} to {st}",
                    current_user.id,
                )
    from app.blueprints.sales_marketing.services import update_lead_score
    update_lead_score(lead)
    db.session.commit()
    return jsonify(lead_to_dict(lead))


@bp.route("/api/stakeholders/bulk-status", methods=["POST"])
@sales_marketing_required
def api_stakeholders_bulk_status():
    payload = request.get_json(silent=True) or {}
    ids = payload.get("stakeholder_ids") or []
    status = (payload.get("follow_up_status") or "").strip()
    if status not in VALID_LEAD_STATUSES:
        return jsonify({"error": "Invalid status"}), 400
    if not ids:
        return jsonify({"error": "stakeholder_ids required"}), 400
    updated = (
        StakeholderLead.query.filter(StakeholderLead.id.in_(ids))
        .update({StakeholderLead.follow_up_status: status}, synchronize_session=False)
    )
    from app.blueprints.sales_marketing.services import log_lead_activity
    for lid in ids:
        log_lead_activity(lid, "status_change", f"Bulk status set to {status}", current_user.id)
    db.session.commit()
    return jsonify({"ok": True, "updated": updated})


@bp.route("/api/stakeholders/<int:lead_id>/dismiss-duplicate", methods=["POST"])
@sales_marketing_required
def api_stakeholder_dismiss_duplicate(lead_id: int):
    lead = db.session.get(StakeholderLead, lead_id)
    if not lead:
        return jsonify({"error": "Not found"}), 404
    lead.duplicate_dismissed = True
    db.session.commit()
    return jsonify(lead_to_dict(lead))


@bp.route("/api/stakeholders/<int:lead_id>/notes", methods=["GET", "POST"])
@sales_marketing_required
def api_stakeholder_notes(lead_id: int):
    lead = db.session.get(StakeholderLead, lead_id)
    if not lead:
        return jsonify({"error": "Not found"}), 404
    if request.method == "GET":
        notes = (
            StakeholderLeadNote.query.filter_by(lead_id=lead_id)
            .order_by(StakeholderLeadNote.created_at.desc())
            .all()
        )
        return jsonify([note_to_dict(n) for n in notes])
    payload = request.get_json(silent=True) or {}
    body = (payload.get("body") or "").strip()
    if not body:
        return jsonify({"error": "body required"}), 400
    note = StakeholderLeadNote(lead_id=lead_id, user_id=current_user.id, body=body[:5000])
    db.session.add(note)
    db.session.flush()
    from app.blueprints.sales_marketing.services import log_lead_activity
    log_lead_activity(lead_id, "note_added", body[:512], current_user.id, {"note_id": note.id})
    db.session.commit()
    return jsonify(note_to_dict(note)), 201


@bp.route("/api/interest-options", methods=["GET", "POST"])
@sales_marketing_required
def api_interest_options():
    if request.method == "GET":
        opts = InterestOption.query.order_by(InterestOption.sort_order, InterestOption.id).all()
        return jsonify([interest_option_to_dict(o) for o in opts])

    payload = request.get_json(silent=True) or {}
    label = (payload.get("label") or "").strip()
    if not label:
        return jsonify({"error": "label required"}), 400
    max_order = db.session.query(db.func.max(InterestOption.sort_order)).scalar() or 0
    opt = InterestOption(label=label[:255], sort_order=max_order + 1, is_active=True)
    db.session.add(opt)
    db.session.commit()
    return jsonify(interest_option_to_dict(opt)), 201


@bp.route("/api/interest-options/<int:opt_id>", methods=["PUT", "DELETE"])
@sales_marketing_required
def api_interest_option_detail(opt_id: int):
    opt = db.session.get(InterestOption, opt_id)
    if not opt:
        return jsonify({"error": "Not found"}), 404
    if request.method == "DELETE":
        db.session.delete(opt)
        db.session.commit()
        return jsonify({"ok": True})
    payload = request.get_json(silent=True) or {}
    if "label" in payload:
        opt.label = (payload.get("label") or "").strip()[:255]
    if "sort_order" in payload:
        opt.sort_order = int(payload.get("sort_order") or 0)
    if "is_active" in payload:
        opt.is_active = bool(payload.get("is_active"))
    db.session.commit()
    return jsonify(interest_option_to_dict(opt))


@bp.route("/api/campaigns")
@sales_marketing_required
def api_campaigns_list():
    campaigns = EmailCampaign.query.order_by(EmailCampaign.created_at.desc()).limit(100).all()
    return jsonify([campaign_to_dict(c) for c in campaigns])


@bp.route("/api/campaigns/<int:campaign_id>")
@sales_marketing_required
def api_campaign_detail(campaign_id: int):
    campaign = db.session.get(EmailCampaign, campaign_id)
    if not campaign:
        return jsonify({"error": "Not found"}), 404
    data = campaign_to_dict(campaign, include_body=True)
    recipients = (
        EmailCampaignRecipient.query.filter_by(campaign_id=campaign_id)
        .order_by(EmailCampaignRecipient.id)
        .all()
    )
    data["recipients"] = [campaign_recipient_to_dict(r) for r in recipients]
    return jsonify(data)


@bp.route("/api/campaigns/send", methods=["POST"])
@sales_marketing_required
def api_campaigns_send():
    payload = request.get_json(silent=True) or {}
    subject = (payload.get("subject") or "").strip()
    body_html = (payload.get("body_html") or "").strip()
    if not subject or not body_html:
        return jsonify({"error": "subject and body_html required"}), 400

    stakeholder_ids: List[int] = payload.get("stakeholder_ids") or []
    leads: List[StakeholderLead] = []

    if stakeholder_ids:
        leads = (
            StakeholderLead.query.filter(StakeholderLead.id.in_(stakeholder_ids))
            .filter(StakeholderLead.consent_marketing.is_(True))
            .all()
        )
    elif payload.get("filters"):
        f = payload["filters"]
        q = leads_query(
            event_id=f.get("event_id"),
            province=f.get("province"),
            interest_option_id=f.get("interest_option_id"),
            consent_only=True,
            search=f.get("search"),
            date_from=_parse_date(f.get("date_from")),
            date_to=_parse_date(f.get("date_to")),
            follow_up_status=f.get("status"),
            duplicates_only=f.get("duplicates_only") is True,
        )
        leads = q.limit(500).all()

    if not leads:
        return jsonify({"error": "No consented recipients found"}), 400

    campaign = EmailCampaign(
        subject=subject[:500],
        body_html=body_html,
        body_text=(payload.get("body_text") or "").strip() or None,
        filter_snapshot=payload.get("filters") or {"stakeholder_ids": stakeholder_ids},
        recipient_count=len(leads),
        status="sending",
        created_by=current_user.id,
    )
    db.session.add(campaign)
    db.session.flush()

    emails = []
    per_lead_bodies = {}
    for lead in leads:
        if not lead.email or not lead.consent_marketing:
            continue
        em = normalize_email(lead.email)
        emails.append(em)
        per_lead_bodies[em] = replace_campaign_tokens(body_html, lead)
    emails = list(dict.fromkeys(emails))
    reply_to = (getattr(current_user, "email", "") or "").strip() or None
    results = []
    for em in emails:
        html = per_lead_bodies.get(em, body_html)
        batch = send_bulk_html_emails(
            recipients=[em],
            subject=subject,
            html_body=html,
            text_body=(payload.get("body_text") or "").strip() or None,
            reply_to=reply_to,
        )
        results.extend(batch)

    result_by_email = {r["email"]: r for r in results}
    sent_count = 0
    for lead in leads:
        em = normalize_email(lead.email)
        r = result_by_email.get(em, {"status": "failed", "error": "not_sent"})
        rec = EmailCampaignRecipient(
            campaign_id=campaign.id,
            stakeholder_id=lead.id,
            email=em,
            status=r.get("status", "failed"),
            error_message=r.get("error"),
            sent_at=datetime.utcnow() if r.get("status") == "sent" else None,
        )
        db.session.add(rec)
        if r.get("status") == "sent":
            sent_count += 1
            from app.blueprints.sales_marketing.services import log_lead_activity
            log_lead_activity(lead.id, "email_sent", f"Campaign: {subject[:120]}", current_user.id)

    campaign.status = "sent" if sent_count else "failed"
    campaign.sent_at = datetime.utcnow()
    db.session.commit()
    failed = [r for r in results if r.get("status") != "sent"]
    if failed:
        from app.blueprints.sales_marketing.notifications import notify_campaign_failed
        notify_campaign_failed(subject, len(failed))
        db.session.commit()
    return jsonify(
        {
            "ok": True,
            "campaign_id": campaign.id,
            "sent": sent_count,
            "total": len(leads),
            "failed": len(failed),
            "failures": failed[:20],
        }
    )
