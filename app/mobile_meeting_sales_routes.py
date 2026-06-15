"""Mobile API routes for Meeting Notes and Sales & Marketing.

These live on the main app (not blueprints) so they work on deployments where
/sales-marketing/* and /meeting-notes/* blueprint prefixes are not yet exposed.
"""

from __future__ import annotations

from flask import jsonify, request
from flask_login import current_user, login_required

from app import app


def _register_meeting_notes_routes() -> None:
    try:
        from app.blueprints.meeting_notes import routes as mn
        from app.blueprints.meeting_notes.models import MeetingActionItem
        from app.blueprints.meeting_notes.services import (
            action_items_query,
            hub_analytics_summary,
            hub_my_tasks_buckets,
            item_to_dict,
        )
        from sqlalchemy.orm import joinedload
    except Exception as exc:
        app.logger.warning("Meeting Notes mobile routes skipped: %s", exc)
        return

    @app.route("/api/mobile/meeting-notes/hub/analytics", methods=["GET"])
    @login_required
    def mobile_meeting_notes_hub_analytics():
        return jsonify(hub_analytics_summary())

    @app.route("/api/mobile/meeting-notes/hub/my-tasks", methods=["GET"])
    @login_required
    def mobile_meeting_notes_hub_my_tasks():
        return jsonify(hub_my_tasks_buckets(current_user.id))

    @app.route("/api/mobile/meeting-notes/my-tasks", methods=["GET"])
    @login_required
    def mobile_meeting_notes_my_tasks():
        q = action_items_query(assignee_user_id=current_user.id, status="all")
        items = q.order_by(MeetingActionItem.due_date.asc().nullslast()).limit(100).all()
        return jsonify({"items": [item_to_dict(i) for i in items]})

    @app.route(
        "/api/mobile/meeting-notes/action-items/<int:item_id>",
        methods=["PUT"],
    )
    @login_required
    def mobile_meeting_notes_update_item(item_id: int):
        return mn.api_mobile_update_item(item_id)

    @app.route(
        "/api/mobile/meeting-notes/subtasks/<int:subtask_id>",
        methods=["PUT"],
    )
    @login_required
    def mobile_meeting_notes_update_subtask(subtask_id: int):
        return mn.api_subtask(subtask_id)

    @app.route("/api/mobile/meeting-notes/meetings", methods=["GET"])
    @login_required
    def mobile_meeting_notes_meetings_list():
        from sqlalchemy import or_

        from app.blueprints.meeting_notes.models import MeetingNote
        from app.blueprints.meeting_notes.services import meetings_index_stats

        qterm = (request.args.get("q") or "").strip()
        limit = min(request.args.get("limit", default=50, type=int), 200)
        query = MeetingNote.query.order_by(MeetingNote.meeting_date.desc())
        if qterm:
            query = query.filter(or_(MeetingNote.title.ilike(f"%{qterm}%")))
        meetings = query.limit(limit).all()
        stats = meetings_index_stats([m.id for m in meetings])
        return jsonify(
            {
                "meetings": [
                    {
                        "id": m.id,
                        "title": m.title,
                        "meeting_date": m.meeting_date.isoformat()
                        if m.meeting_date
                        else None,
                        "stats": stats.get(
                            m.id,
                            {"open": 0, "in_progress": 0, "done": 0, "total": 0},
                        ),
                    }
                    for m in meetings
                ]
            }
        )

    @app.route("/api/mobile/meeting-notes/meetings/<int:meeting_id>", methods=["GET"])
    @login_required
    def mobile_meeting_notes_meeting_detail(meeting_id: int):
        from app.blueprints.meeting_notes.models import MeetingNote
        from app.blueprints.meeting_notes.services import meeting_to_dict

        mn = (
            MeetingNote.query.options(joinedload(MeetingNote.attendees))
            .filter_by(id=meeting_id)
            .first()
        )
        if not mn:
            return jsonify({"error": "Not found"}), 404
        return jsonify(meeting_to_dict(mn))

    @app.route(
        "/api/mobile/meeting-notes/meetings/<int:meeting_id>/action-items",
        methods=["GET"],
    )
    @login_required
    def mobile_meeting_notes_meeting_action_items(meeting_id: int):
        from app.blueprints.meeting_notes.models import (
            MeetingActionItem,
            MeetingFocusRow,
        )

        q = action_items_query(meeting_note_id=meeting_id, status="all")
        items = q.order_by(
            MeetingFocusRow.sort_order,
            MeetingActionItem.sort_order,
        ).all()
        return jsonify({"items": [item_to_dict(i) for i in items]})


def _register_sales_marketing_routes() -> None:
    try:
        from app.blueprints.sales_marketing import routes as sm
    except Exception as exc:
        app.logger.warning("Sales & Marketing mobile routes skipped: %s", exc)
        return

    @app.route("/api/mobile/sales-marketing/stakeholders", methods=["GET"])
    @login_required
    def mobile_sales_marketing_stakeholders_list():
        return sm.api_stakeholders_list()

    @app.route("/api/mobile/sales-marketing/stakeholders", methods=["POST"])
    @login_required
    def mobile_sales_marketing_stakeholders_create():
        return sm.api_stakeholders_create()

    @app.route(
        "/api/mobile/sales-marketing/stakeholders/<int:lead_id>",
        methods=["GET", "PUT", "DELETE"],
    )
    @login_required
    def mobile_sales_marketing_stakeholder_detail(lead_id: int):
        return sm.api_stakeholder_detail(lead_id)

    @app.route("/api/mobile/sales-marketing/events", methods=["GET", "POST"])
    @login_required
    def mobile_sales_marketing_events():
        return sm.api_events_list_create()

    @app.route(
        "/api/mobile/sales-marketing/events/<int:event_id>",
        methods=["GET", "PUT", "DELETE"],
    )
    @login_required
    def mobile_sales_marketing_event_detail(event_id: int):
        return sm.api_event_detail(event_id)

    @app.route("/api/mobile/sales-marketing/events/roadmap", methods=["GET"])
    @login_required
    def mobile_sales_marketing_events_roadmap():
        return sm.api_events_roadmap()

    @app.route("/api/mobile/sales-marketing/interest-options", methods=["GET", "POST"])
    @login_required
    def mobile_sales_marketing_interest_options():
        return sm.api_interest_options()


_register_meeting_notes_routes()
_register_sales_marketing_routes()
