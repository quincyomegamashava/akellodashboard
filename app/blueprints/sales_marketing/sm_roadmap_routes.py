"""Additional Sales & Marketing routes for roadmap features."""

from __future__ import annotations

from datetime import datetime

from flask import jsonify, render_template, request
from flask_login import current_user
from sqlalchemy.orm import joinedload

from app import db

from app.blueprints.sales_marketing import bp
from app.blueprints.sales_marketing.models import (
    EmailTemplate,
    MarketingEvent,
    StakeholderLead,
    StakeholderLeadNote,
    StakeholderSavedView,
)
from app.blueprints.sales_marketing.notifications import (
    can_access_sales_marketing_for_user,
    notify_campaign_failed,
    notify_hot_lead,
    notify_new_lead,
)
from app.blueprints.sales_marketing.services import (
    VALID_LEAD_STATUSES,
    ZIMBABWE_PROVINCES,
    activity_to_dict,
    ensure_unique_event_slug,
    event_roi_stats,
    event_to_dict,
    funnel_analytics,
    lead_timeline,
    lead_to_dict,
    log_lead_activity,
    replace_campaign_tokens,
    saved_view_to_dict,
    sales_marketing_required,
    slugify_event_name,
    stakeholders_by_province,
    suggested_action_for_lead,
    template_to_dict,
    update_lead_score,
    whatsapp_url_for_lead,
)


@bp.route("/map")
@sales_marketing_required
def map_page():
    return render_template(
        "sales_marketing/map.html",
        title="Lead Map",
        provinces=ZIMBABWE_PROVINCES,
    )


@bp.route("/events/<int:event_id>/stand")
@sales_marketing_required
def stand_mode_page(event_id: int):
    event = db.session.get(MarketingEvent, event_id)
    if not event:
        return "Event not found", 404
    return render_template(
        "sales_marketing/stand_mode.html",
        title=f"Stand mode — {event.name}",
        event=event_to_dict(event),
        event_id=event_id,
    )


@bp.route("/events/<int:event_id>/dashboard")
@sales_marketing_required
def event_dashboard_page(event_id: int):
    event = db.session.get(MarketingEvent, event_id)
    if not event:
        return "Event not found", 404
    return render_template(
        "sales_marketing/event_dashboard.html",
        title=f"Event ROI — {event.name}",
        event_id=event_id,
    )


@bp.route("/api/stakeholders/<int:lead_id>/timeline")
@sales_marketing_required
def api_stakeholder_timeline(lead_id: int):
    lead = db.session.get(StakeholderLead, lead_id)
    if not lead:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"items": lead_timeline(lead_id)})


@bp.route("/api/stakeholders/<int:lead_id>/whatsapp-log", methods=["POST"])
@sales_marketing_required
def api_stakeholder_whatsapp_log(lead_id: int):
    lead = db.session.get(StakeholderLead, lead_id)
    if not lead:
        return jsonify({"error": "Not found"}), 404
    log_lead_activity(
        lead_id,
        "whatsapp_logged",
        "WhatsApp outreach logged",
        current_user.id,
    )
    db.session.commit()
    return jsonify({"ok": True, "whatsapp_url": whatsapp_url_for_lead(lead)})


@bp.route("/api/stakeholders/<int:lead_id>/suggested-action")
@sales_marketing_required
def api_stakeholder_suggested_action(lead_id: int):
    lead = db.session.get(StakeholderLead, lead_id)
    if not lead:
        return jsonify({"error": "Not found"}), 404
    if lead.lead_score is None:
        update_lead_score(lead)
        db.session.commit()
    return jsonify({
        "lead_score": lead.lead_score,
        "suggested_action": suggested_action_for_lead(lead),
        "whatsapp_url": whatsapp_url_for_lead(lead) if lead.mobile else None,
    })


@bp.route("/api/stakeholders/<int:lead_id>/duplicates")
@sales_marketing_required
def api_stakeholder_duplicates(lead_id: int):
    lead = db.session.get(StakeholderLead, lead_id)
    if not lead:
        return jsonify({"error": "Not found"}), 404
    dups = (
        StakeholderLead.query.filter(
            StakeholderLead.email == lead.email,
            StakeholderLead.id != lead.id,
        )
        .order_by(StakeholderLead.submitted_at.desc())
        .limit(20)
        .all()
    )
    return jsonify([lead_to_dict(d) for d in dups])


@bp.route("/api/stakeholders/merge", methods=["POST"])
@sales_marketing_required
def api_stakeholders_merge():
    payload = request.get_json(silent=True) or {}
    winner_id = int(payload.get("winner_id") or 0)
    loser_id = int(payload.get("loser_id") or 0)
    if not winner_id or not loser_id or winner_id == loser_id:
        return jsonify({"error": "winner_id and loser_id required"}), 400
    winner = db.session.get(StakeholderLead, winner_id)
    loser = db.session.get(StakeholderLead, loser_id)
    if not winner or not loser:
        return jsonify({"error": "Lead not found"}), 404
    fields = payload.get("fields") or {}
    for key in ("full_name", "mobile", "school_name", "province", "comments"):
        if key in fields and fields[key]:
            setattr(winner, key, fields[key])
    loser.follow_up_status = "closed"
    log_lead_activity(
        winner_id,
        "merge",
        f"Merged lead #{loser_id} into this record",
        current_user.id,
        {"loser_id": loser_id},
    )
    db.session.commit()
    return jsonify(lead_to_dict(winner))


@bp.route("/api/stakeholders/by-province")
@sales_marketing_required
def api_stakeholders_by_province():
    period = request.args.get("period") or "all"
    return jsonify(stakeholders_by_province(period))


@bp.route("/api/stakeholders/funnel")
@sales_marketing_required
def api_stakeholders_funnel():
    try:
        days = int(request.args.get("period") or "30")
    except (TypeError, ValueError):
        days = 30
    if str(request.args.get("period") or "").endswith("d"):
        days = int(str(request.args.get("period")).replace("d", "") or 30)
    return jsonify(funnel_analytics(days))


@bp.route("/api/events/<int:event_id>/roi")
@sales_marketing_required
def api_event_roi(event_id: int):
    data = event_roi_stats(event_id)
    if not data:
        return jsonify({"error": "Not found"}), 404
    return jsonify(data)


@bp.route("/api/saved-views", methods=["GET", "POST"])
@sales_marketing_required
def api_sm_saved_views():
    if request.method == "GET":
        views = (
            StakeholderSavedView.query.filter_by(user_id=current_user.id)
            .order_by(StakeholderSavedView.sort_order, StakeholderSavedView.id)
            .all()
        )
        return jsonify([saved_view_to_dict(v) for v in views])
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    if payload.get("is_default"):
        StakeholderSavedView.query.filter_by(user_id=current_user.id, is_default=True).update(
            {"is_default": False}
        )
    view = StakeholderSavedView(
        user_id=current_user.id,
        name=name[:120],
        filters_json=payload.get("filters_json") or {},
        view_mode=(payload.get("view_mode") or "table")[:32],
        is_default=bool(payload.get("is_default")),
        sort_order=int(payload.get("sort_order") or 0),
    )
    db.session.add(view)
    db.session.commit()
    return jsonify(saved_view_to_dict(view)), 201


@bp.route("/api/saved-views/<int:view_id>", methods=["PUT", "DELETE"])
@sales_marketing_required
def api_sm_saved_view_detail(view_id: int):
    view = StakeholderSavedView.query.filter_by(id=view_id, user_id=current_user.id).first()
    if not view:
        return jsonify({"error": "Not found"}), 404
    if request.method == "DELETE":
        db.session.delete(view)
        db.session.commit()
        return jsonify({"ok": True})
    payload = request.get_json(silent=True) or {}
    if "name" in payload:
        view.name = (payload.get("name") or "").strip()[:120]
    if "filters_json" in payload:
        view.filters_json = payload.get("filters_json") or {}
    if "view_mode" in payload:
        view.view_mode = (payload.get("view_mode") or "table")[:32]
    if "is_default" in payload and payload.get("is_default"):
        StakeholderSavedView.query.filter_by(user_id=current_user.id, is_default=True).update(
            {"is_default": False}
        )
        view.is_default = True
    db.session.commit()
    return jsonify(saved_view_to_dict(view))


@bp.route("/api/email-templates", methods=["GET", "POST"])
@sales_marketing_required
def api_email_templates():
    if request.method == "GET":
        templates = EmailTemplate.query.order_by(EmailTemplate.name).all()
        return jsonify([template_to_dict(t) for t in templates])
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    t = EmailTemplate(
        name=name[:120],
        subject=(payload.get("subject") or "")[:500],
        body_html=(payload.get("body_html") or ""),
        created_by=current_user.id,
    )
    db.session.add(t)
    db.session.commit()
    return jsonify(template_to_dict(t)), 201


@bp.route("/api/email-templates/<int:template_id>", methods=["PUT", "DELETE"])
@sales_marketing_required
def api_email_template_detail(template_id: int):
    t = db.session.get(EmailTemplate, template_id)
    if not t:
        return jsonify({"error": "Not found"}), 404
    if request.method == "DELETE":
        db.session.delete(t)
        db.session.commit()
        return jsonify({"ok": True})
    payload = request.get_json(silent=True) or {}
    if "name" in payload:
        t.name = (payload.get("name") or "").strip()[:120]
    if "subject" in payload:
        t.subject = (payload.get("subject") or "")[:500]
    if "body_html" in payload:
        t.body_html = payload.get("body_html") or ""
    db.session.commit()
    return jsonify(template_to_dict(t))


def connect_page_by_slug(slug: str):
    from app.blueprints.sales_marketing.routes import connect_page
    from app.blueprints.sales_marketing.services import seed_interest_options_if_empty
    from app.blueprints.sales_marketing.models import InterestOption

    seed_interest_options_if_empty()
    event = MarketingEvent.query.filter_by(slug=slug, status="active").first()
    if not event:
        return "Event not found", 404
    options = (
        InterestOption.query.filter_by(is_active=True)
        .order_by(InterestOption.sort_order, InterestOption.id)
        .all()
    )
    from datetime import date
    from app.blueprints.sales_marketing.services import HEARD_ABOUT_OPTIONS, ROLE_CATEGORIES

    return render_template(
        "sales_marketing/public_form.html",
        title=f"Connect — {event.name}",
        provinces=ZIMBABWE_PROVINCES,
        role_categories=ROLE_CATEGORIES,
        heard_about_options=HEARD_ABOUT_OPTIONS,
        interest_options=options,
        today=date.today().isoformat(),
        prefill_event_id=event.id,
        prefill_event={
            "id": event.id,
            "name": event.name,
            "location": event.location or "",
            "banner_text": getattr(event, "banner_text", None) or "",
        },
        form_step_mode=True,
    )
