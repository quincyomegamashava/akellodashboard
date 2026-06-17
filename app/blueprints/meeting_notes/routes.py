"""Routes and JSON API for weekly meeting notes."""

import base64
from datetime import date, datetime
from typing import Any, List, Optional, Sequence

import requests
from flask import abort, jsonify, render_template, request
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from flask_login import current_user, login_required

from app import db
from app.email_utils import send_html_email_detailed
from app.models import User

from app.blueprints.meeting_notes import bp
from app.blueprints.meeting_notes.ai import (
    extract_tasks_from_notes,
    semantic_duplicate_flags,
    summarize_notes,
)
from app.blueprints.meeting_notes.models import (
    MeetingActionItem,
    MeetingActionSubtask,
    MeetingFocusRow,
    MeetingItemComment,
    MeetingLabel,
    MeetingNote,
    MeetingNotesActivityLog,
    MeetingSavedView,
    MeetingTemplate,
    VALID_PRIORITIES,
)
from app.blueprints.meeting_notes.notifications import (
    notify_assignees,
    notify_mentioned_users,
)
from app.blueprints.meeting_notes.email_reports import (
    normalize_recipients,
    send_meeting_report_email,
)
from app.blueprints.meeting_notes.services import (
    VALID_STATUSES,
    action_items_query,
    agenda_item_notes_to_text,
    attendees_for_meeting,
    apply_subtask_parent_rollup,
    carry_forward_preview,
    coalesce_activity_rows,
    comment_to_dict,
    copy_subtasks_to_item,
    distinct_platforms,
    existing_cta_keys_for_meeting,
    guest_names_to_text,
    hub_analytics_summary,
    hub_my_tasks_buckets,
    item_to_dict,
    items_to_fc_events,
    items_to_gantt_tasks,
    label_to_dict,
    meeting_to_dict,
    meetings_index_stats,
    normalize_bullet_text,
    normalize_cta_key,
    overdue_items_count,
    parse_guest_names,
    parse_mention_user_ids,
    parse_agenda_item_notes,
    saved_view_to_dict,
    subtask_to_dict,
    template_to_dict,
    user_display_name,
    validate_subtask_assignee,
)


def _is_admin() -> bool:
    role = (getattr(current_user, "userRole", None) or "").strip()
    return role == "Admin"


def _can_view_activity(meeting_id: int) -> bool:
    if _is_admin():
        return True
    mn = db.session.get(MeetingNote, meeting_id)
    return bool(mn and mn.created_by == current_user.id)


def _payload_silent(payload: dict) -> bool:
    return bool(payload.get("silent"))


def _serialize_activity_logs(logs: Sequence[MeetingNotesActivityLog]) -> List[dict]:
    out = []
    for r in logs:
        actor = r.actor
        aname = (
            f"{(actor.firstname or '').strip()} {(actor.lastname or '').strip()}".strip()
            if actor
            else ""
        ) or (actor.username if actor else "?")
        out.append(
            {
                "id": r.id,
                "occurred_at": r.occurred_at.isoformat() if r.occurred_at else None,
                "action": r.action,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "summary": r.summary,
                "actor": aname,
            }
        )
    return out


def _activity_rows_for_meeting(
    meeting_id: int,
    limit: int = 30,
    action_filter: Optional[str] = None,
    coalesce: bool = True,
) -> List[dict]:
    q = MeetingNotesActivityLog.query.filter_by(meeting_note_id=meeting_id).order_by(
        MeetingNotesActivityLog.occurred_at.desc()
    )
    if action_filter and action_filter.strip().lower() not in ("", "all"):
        q = q.filter(MeetingNotesActivityLog.action == action_filter.strip().lower())
    rows = _serialize_activity_logs(q.limit(limit * 3 if coalesce else limit).all())
    if coalesce:
        rows = coalesce_activity_rows(rows)
    return rows[:limit]


def _parse_date(val: Any) -> Optional[date]:
    if not val:
        return None
    try:
        s = str(val).strip()[:10]
        return date.fromisoformat(s)
    except ValueError:
        return None


def _parse_date_json(payload: dict, key: str) -> Optional[date]:
    return _parse_date(payload.get(key))


def _log_activity(
    meeting_note_id: Optional[int],
    action: str,
    entity_type: str,
    entity_id: Optional[int],
    summary: str,
    details: Optional[dict] = None,
) -> None:
    row = MeetingNotesActivityLog(
        meeting_note_id=meeting_note_id,
        actor_user_id=current_user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary[:512],
        details_json=details,
    )
    db.session.add(row)


def _user_options() -> List[dict]:
    users = User.query.order_by(User.firstname, User.lastname, User.username).all()
    return [
        {
            "id": u.id,
            "label": f"{(u.firstname or '').strip()} {(u.lastname or '').strip()}".strip() or u.username,
            "username": u.username or "",
        }
        for u in users
    ]


def _assignees_from_ids(ids: Optional[List[Any]]) -> List[User]:
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


# --- HTML pages ---


@bp.route("/")
@login_required
def index():
    search = (request.args.get("q") or "").strip()
    q = MeetingNote.query.order_by(MeetingNote.meeting_date.desc())
    if search:
        q = q.filter(or_(MeetingNote.title.ilike(f"%{search}%")))
    meetings = q.limit(200).all()
    stats = meetings_index_stats([m.id for m in meetings])
    overdue_count = overdue_items_count(
        assignee_user_id=current_user.id if not _is_admin() else None
    )
    return render_template(
        "meeting_notes/index.html",
        title="Meeting notes",
        meetings=meetings,
        meeting_stats=stats,
        search_q=search,
        overdue_count=overdue_count,
        is_admin=_is_admin(),
        current_user_id=current_user.id,
        user_opts=_user_options(),
    )


@bp.route("/all-items")
@login_required
def all_items():
    user_opts = _user_options()
    platforms = distinct_platforms(None)
    my_only = request.args.get("mine") == "1"
    overdue_count = overdue_items_count(assignee_user_id=current_user.id)
    return render_template(
        "meeting_notes/all_items.html",
        title="All action items",
        user_opts=user_opts,
        platforms=platforms,
        meeting_note_id=None,
        is_admin=_is_admin(),
        overdue_count=overdue_count,
        default_assignee_id=current_user.id if my_only else None,
    )


@bp.route("/<int:meeting_id>")
@login_required
def detail(meeting_id: int):
    mn = (
        MeetingNote.query.options(joinedload(MeetingNote.attendees))
        .filter_by(id=meeting_id)
        .first()
    )
    if not mn:
        abort(404)
    user_opts = _user_options()
    platforms = distinct_platforms(meeting_id)
    focus_rows = (
        MeetingFocusRow.query.filter_by(meeting_note_id=meeting_id)
        .order_by(MeetingFocusRow.sort_order, MeetingFocusRow.id)
        .all()
    )
    focus_row_opts = [
        {
            "id": r.id,
            "platform": r.platform,
            "focus_area": r.focus_area,
            "discussion_notes": r.discussion_notes or "",
        }
        for r in focus_rows
    ]
    agenda_item_notes = parse_agenda_item_notes(mn.agenda_item_notes)
    attendee_ids = [u.id for u in (mn.attendees or [])]
    guest_names = parse_guest_names(mn.guest_attendees)
    is_admin = _is_admin()
    can_view_activity = _can_view_activity(meeting_id)
    activity_rows = _activity_rows_for_meeting(meeting_id) if can_view_activity else []
    prev_meeting = (
        MeetingNote.query.filter(
            MeetingNote.id != meeting_id,
            MeetingNote.meeting_date < mn.meeting_date,
        )
        .order_by(MeetingNote.meeting_date.desc())
        .first()
    )
    carry_forward_sources = (
        MeetingNote.query.filter(MeetingNote.id != meeting_id)
        .order_by(MeetingNote.meeting_date.desc())
        .limit(50)
        .all()
    )
    return render_template(
        "meeting_notes/detail.html",
        title=mn.title or "Meeting notes",
        meeting=mn,
        focus_rows=focus_rows,
        focus_row_opts=focus_row_opts,
        user_opts=user_opts,
        platforms=platforms,
        meeting_note_id=meeting_id,
        attendee_ids=attendee_ids,
        guest_names=guest_names,
        is_admin=is_admin,
        can_view_activity=can_view_activity,
        activity_rows=activity_rows,
        prev_meeting_id=prev_meeting.id if prev_meeting else None,
        carry_forward_sources=carry_forward_sources,
        meeting_summary=mn.summary or "",
        agenda_item_notes=agenda_item_notes,
        minutes_taken_by=user_display_name(mn.creator) if mn.creator else "",
    )


# --- Read APIs ---


def _filter_args_from_request():
    meeting_note_id = request.args.get("meeting_note_id", type=int)
    platform = request.args.get("platform", type=str)
    assignee_user_id = request.args.get("assignee_user_id", type=int)
    status = request.args.get("status", type=str)
    due_preset = request.args.get("due_preset", type=str)
    due_start = _parse_date(request.args.get("due_start"))
    due_end = _parse_date(request.args.get("due_end"))
    priority = request.args.get("priority", type=str)
    label_id = request.args.get("label_id", type=int)
    search_q = request.args.get("q", type=str)
    stakeholder_lead_id = request.args.get("stakeholder_lead_id", type=int)
    marketing_event_id = request.args.get("marketing_event_id", type=int) or request.args.get("event_id", type=int)
    return (
        meeting_note_id,
        platform,
        assignee_user_id,
        status,
        due_preset,
        due_start,
        due_end,
        priority,
        label_id,
        search_q,
        stakeholder_lead_id,
        marketing_event_id,
    )


def _labels_from_ids(ids: Optional[List[Any]]) -> List[MeetingLabel]:
    if not ids:
        return []
    out = []
    for raw in ids:
        try:
            lid = int(raw)
        except (TypeError, ValueError):
            continue
        lb = db.session.get(MeetingLabel, lid)
        if lb:
            out.append(lb)
    return out


@bp.route("/api/users")
@login_required
def api_users():
    users = User.query.order_by(User.firstname, User.lastname, User.username).all()
    return jsonify(
        [
            {
                "id": u.id,
                "label": f"{(u.firstname or '').strip()} {(u.lastname or '').strip()}".strip()
                or u.username,
                "username": u.username,
            }
            for u in users
        ]
    )


@bp.route("/api/action-items")
@login_required
def api_action_items():
    (
        meeting_note_id,
        platform,
        assignee_user_id,
        status,
        due_preset,
        due_start,
        due_end,
        priority,
        label_id,
        search_q,
        stakeholder_lead_id,
        marketing_event_id,
    ) = _filter_args_from_request()
    q = action_items_query(
        meeting_note_id=meeting_note_id,
        platform=platform,
        assignee_user_id=assignee_user_id,
        status=status,
        due_preset=due_preset,
        due_start=due_start,
        due_end=due_end,
        priority=priority,
        label_id=label_id,
        search_q=search_q,
        stakeholder_lead_id=stakeholder_lead_id,
        marketing_event_id=marketing_event_id,
    )
    items = q.order_by(MeetingNote.meeting_date.desc(), MeetingFocusRow.sort_order, MeetingActionItem.sort_order).all()
    include_threads = request.args.get("include_comment_threads") == "1"
    if not include_threads:
        return jsonify({"items": [item_to_dict(i) for i in items]})
    comments_by_item: dict[int, list] = {}
    item_ids = [i.id for i in items]
    if item_ids:
        rows = (
            MeetingItemComment.query.filter(MeetingItemComment.action_item_id.in_(item_ids))
            .order_by(MeetingItemComment.created_at.asc())
            .all()
        )
        for c in rows:
            comments_by_item.setdefault(c.action_item_id, []).append(c)
    return jsonify({
        "items": [
            item_to_dict(i, comment_threads=comments_by_item.get(i.id, []))
            for i in items
        ]
    })


@bp.route("/api/calendar-events")
@login_required
def api_calendar_events():
    (
        meeting_note_id,
        platform,
        assignee_user_id,
        status,
        due_preset,
        due_start,
        due_end,
        priority,
        label_id,
        search_q,
        _stakeholder_lead_id,
        _marketing_event_id,
    ) = _filter_args_from_request()
    q = action_items_query(
        meeting_note_id=meeting_note_id,
        platform=platform,
        assignee_user_id=assignee_user_id,
        status=status,
        due_preset=due_preset,
        due_start=due_start,
        due_end=due_end,
        priority=priority,
        label_id=label_id,
        search_q=search_q,
        stakeholder_lead_id=_stakeholder_lead_id,
        marketing_event_id=_marketing_event_id,
    )
    items = q.all()
    return jsonify(items_to_fc_events(items))


@bp.route("/api/gantt-tasks")
@login_required
def api_gantt_tasks():
    (
        meeting_note_id,
        platform,
        assignee_user_id,
        status,
        due_preset,
        due_start,
        due_end,
        priority,
        label_id,
        search_q,
        _stakeholder_lead_id,
        _marketing_event_id,
    ) = _filter_args_from_request()
    q = action_items_query(
        meeting_note_id=meeting_note_id,
        platform=platform,
        assignee_user_id=assignee_user_id,
        status=status,
        due_preset=due_preset,
        due_start=due_start,
        due_end=due_end,
        priority=priority,
        label_id=label_id,
        search_q=search_q,
        stakeholder_lead_id=_stakeholder_lead_id,
        marketing_event_id=_marketing_event_id,
    )
    items = q.all()
    return jsonify({"tasks": items_to_gantt_tasks(items)})


@bp.route("/api/meetings/<int:meeting_id>/activity")
@login_required
def api_activity_log(meeting_id: int):
    if not _can_view_activity(meeting_id):
        return jsonify({"error": "Forbidden"}), 403
    per_page = min(request.args.get("per_page", default=50, type=int), 200)
    action_filter = request.args.get("action")
    coalesce = request.args.get("coalesce", "1") != "0"
    rows = _activity_rows_for_meeting(
        meeting_id,
        limit=per_page,
        action_filter=action_filter,
        coalesce=coalesce,
    )
    total = MeetingNotesActivityLog.query.filter_by(meeting_note_id=meeting_id).count()
    return jsonify({"items": rows, "page": 1, "pages": 1, "total": total})


@bp.route("/api/meetings/<int:meeting_id>/duplicate", methods=["POST"])
@login_required
def api_duplicate_meeting(meeting_id: int):
    src = db.session.get(MeetingNote, meeting_id)
    if not src:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip() or f"{src.title} (copy)"
    meeting_date = _parse_date_json(payload, "meeting_date") or date.today()
    copy_items = payload.get("copy_items", True)
    copy_open_only = payload.get("copy_open_only", False)
    mn = MeetingNote(
        title=title,
        meeting_date=meeting_date,
        summary=src.summary,
        guest_attendees=src.guest_attendees,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.session.add(mn)
    db.session.flush()
    mn.attendees = list(src.attendees or [])
    if copy_items:
        for fr in src.focus_rows.order_by(MeetingFocusRow.sort_order, MeetingFocusRow.id):
            new_fr = MeetingFocusRow(
                meeting_note_id=mn.id,
                platform=fr.platform,
                focus_area=fr.focus_area,
                sort_order=fr.sort_order,
            )
            db.session.add(new_fr)
            db.session.flush()
            for it in fr.action_items.order_by(MeetingActionItem.sort_order, MeetingActionItem.id):
                if copy_open_only and it.status == "done":
                    continue
                new_it = MeetingActionItem(
                    focus_row_id=new_fr.id,
                    call_to_action=it.call_to_action,
                    expected_impact=it.expected_impact,
                    challenges=it.challenges,
                    comments=it.comments,
                    status="open" if copy_open_only else it.status,
                    priority=getattr(it, "priority", None) or "medium",
                    due_date=it.due_date,
                    start_date=it.start_date,
                    sort_order=it.sort_order,
                    source_excerpt=getattr(it, "source_excerpt", None),
                    ai_extracted=bool(getattr(it, "ai_extracted", False)),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.session.add(new_it)
                db.session.flush()
                new_it.assignees = list(it.assignees or [])
                new_it.labels = list(it.labels or [])
                copy_subtasks_to_item(it, new_it)
    _log_activity(mn.id, "create", "meeting_note", mn.id, f"Duplicated meeting from #{meeting_id}: {title}")
    db.session.commit()
    return jsonify({"id": mn.id, "title": mn.title, "meeting_date": mn.meeting_date.isoformat()}), 201


@bp.route("/api/meetings/<int:meeting_id>/carry-forward/preview", methods=["GET"])
@login_required
def api_carry_forward_preview(meeting_id: int):
    if not db.session.get(MeetingNote, meeting_id):
        return jsonify({"error": "Not found"}), 404
    source_id = request.args.get("from_meeting_id", type=int)
    if not source_id:
        return jsonify({"error": "from_meeting_id required"}), 400
    if source_id == meeting_id:
        return jsonify({"error": "Cannot carry forward from the same meeting"}), 400
    data = carry_forward_preview(source_id, meeting_id)
    if data.get("error"):
        return jsonify(data), 404
    return jsonify(data)


@bp.route("/api/meetings/<int:meeting_id>/carry-forward", methods=["POST"])
@login_required
def api_carry_forward(meeting_id: int):
    target = db.session.get(MeetingNote, meeting_id)
    if not target:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    source_id = payload.get("from_meeting_id")
    if not source_id:
        prev = (
            MeetingNote.query.filter(
                MeetingNote.id != meeting_id,
                MeetingNote.meeting_date < target.meeting_date,
            )
            .order_by(MeetingNote.meeting_date.desc())
            .first()
        )
        source_id = prev.id if prev else None
    if not source_id:
        return jsonify({"error": "No previous meeting to carry forward from"}), 400
    if int(source_id) == meeting_id:
        return jsonify({"error": "Cannot carry forward from the same meeting"}), 400
    src = db.session.get(MeetingNote, int(source_id))
    if not src:
        return jsonify({"error": "Source meeting not found"}), 404
    mark_source_done = bool(payload.get("mark_source_done"))
    existing = existing_cta_keys_for_meeting(meeting_id)
    created = 0
    skipped = 0
    copied_source_ids: List[int] = []
    for fr in src.focus_rows.order_by(MeetingFocusRow.sort_order, MeetingFocusRow.id):
        open_items = (
            fr.action_items.filter(MeetingActionItem.status != "done")
            .order_by(MeetingActionItem.sort_order, MeetingActionItem.id)
            .all()
        )
        items_to_copy = []
        for it in open_items:
            key = normalize_cta_key(it.call_to_action)
            if not key:
                skipped += 1
                continue
            if key in existing:
                skipped += 1
                continue
            items_to_copy.append(it)
            existing.add(key)
        if not items_to_copy:
            continue
        new_fr = MeetingFocusRow(
            meeting_note_id=meeting_id,
            platform=fr.platform,
            focus_area=fr.focus_area,
            sort_order=fr.sort_order,
        )
        db.session.add(new_fr)
        db.session.flush()
        for it in items_to_copy:
            cta = (it.call_to_action or "").strip()
            if cta:
                cta = f"[Carried forward] {cta}"
            new_it = MeetingActionItem(
                focus_row_id=new_fr.id,
                call_to_action=cta,
                expected_impact=it.expected_impact,
                challenges=it.challenges,
                comments=it.comments,
                status=it.status,
                priority=getattr(it, "priority", None) or "medium",
                due_date=it.due_date,
                start_date=it.start_date,
                sort_order=it.sort_order,
                carry_forward_count=(getattr(it, "carry_forward_count", 0) or 0) + 1,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.session.add(new_it)
            db.session.flush()
            new_it.assignees = list(it.assignees or [])
            new_it.labels = list(it.labels or [])
            copy_subtasks_to_item(it, new_it)
            created += 1
            copied_source_ids.append(it.id)
    if mark_source_done and copied_source_ids:
        for it in MeetingActionItem.query.filter(
            MeetingActionItem.id.in_(copied_source_ids)
        ):
            if it.status != "done":
                it.status = "done"
                it.updated_at = datetime.utcnow()
    summary = f"Carried forward {created} open items from meeting #{source_id}"
    if skipped:
        summary += f" ({skipped} skipped as duplicates or empty)"
    if mark_source_done and copied_source_ids:
        summary += "; marked source items done"
    _log_activity(meeting_id, "create", "meeting_note", meeting_id, summary)
    db.session.commit()
    return jsonify({
        "created": created,
        "skipped": skipped,
        "from_meeting_id": int(source_id),
        "marked_source_done": len(copied_source_ids) if mark_source_done else 0,
    })


@bp.route("/api/action-items/bulk", methods=["POST"])
@login_required
def api_bulk_action_items():
    payload = request.get_json(silent=True) or {}
    ids = payload.get("item_ids") or []
    if not ids:
        return jsonify({"error": "No items selected"}), 400
    updated = 0
    mid = None
    for raw_id in ids:
        try:
            item_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        item = (
            MeetingActionItem.query.options(joinedload(MeetingActionItem.focus_row))
            .filter_by(id=item_id)
            .first()
        )
        if not item:
            continue
        if "status" in payload:
            st = (payload.get("status") or "").strip().lower()
            if st in VALID_STATUSES:
                item.status = st
        if "assignee_ids" in payload:
            item.assignees = _assignees_from_ids(payload.get("assignee_ids"))
        if "priority" in payload:
            pr = (payload.get("priority") or "").strip().lower()
            if pr in VALID_PRIORITIES:
                item.priority = pr
        if "label_ids" in payload:
            item.labels = _labels_from_ids(payload.get("label_ids"))
        item.updated_at = datetime.utcnow()
        if item.focus_row:
            mid = item.focus_row.meeting_note_id
        updated += 1
    if updated and mid:
        _log_activity(mid, "update", "action_item", None, f"Bulk updated {updated} action items")
    db.session.commit()
    return jsonify({"updated": updated})


# --- Mutations: meetings ---


@bp.route("/api/meetings", methods=["POST"])
@login_required
def api_create_meeting():
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip() or "Untitled meeting"
    meeting_date = _parse_date_json(payload, "meeting_date") or date.today()
    summary = (payload.get("summary") or "").strip() or None
    mn = MeetingNote(
        title=title,
        meeting_date=meeting_date,
        summary=summary,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.session.add(mn)
    db.session.flush()
    _log_activity(mn.id, "create", "meeting_note", mn.id, f"Created meeting: {title}")
    db.session.commit()
    return jsonify({"id": mn.id, "title": mn.title, "meeting_date": mn.meeting_date.isoformat()}), 201


@bp.route("/api/meetings/<int:meeting_id>", methods=["PUT", "DELETE"])
@login_required
def api_meeting(meeting_id: int):
    mn = db.session.get(MeetingNote, meeting_id)
    if not mn:
        return jsonify({"error": "Not found"}), 404
    if request.method == "DELETE":
        title = mn.title
        _log_activity(mn.id, "delete", "meeting_note", mn.id, f"Deleted meeting: {title}")
        db.session.delete(mn)
        db.session.commit()
        return jsonify({"ok": True})
    payload = request.get_json(silent=True) or {}
    if "title" in payload:
        mn.title = (payload.get("title") or "").strip() or mn.title
    if "meeting_date" in payload:
        d = _parse_date_json(payload, "meeting_date")
        if d:
            mn.meeting_date = d
    if "summary" in payload:
        mn.summary = (payload.get("summary") or "").strip() or None
    if "location" in payload:
        mn.location = (payload.get("location") or "").strip() or None
    if "meeting_time" in payload:
        mn.meeting_time = (payload.get("meeting_time") or "").strip() or None
    if "agenda" in payload:
        mn.agenda = (payload.get("agenda") or "").strip() or None
    agenda_notes_updated = False
    if "agenda_item_notes" in payload:
        incoming = payload.get("agenda_item_notes")
        if isinstance(incoming, dict):
            mn.agenda_item_notes = agenda_item_notes_to_text(incoming)
            agenda_notes_updated = True
    attendees_updated = False
    if "attendee_ids" in payload:
        mn.attendees = _assignees_from_ids(payload.get("attendee_ids"))
        attendees_updated = True
    if "guest_names" in payload:
        raw_guests = payload.get("guest_names")
        if isinstance(raw_guests, list):
            mn.guest_attendees = guest_names_to_text(raw_guests)
        else:
            mn.guest_attendees = guest_names_to_text(parse_guest_names(raw_guests))
        attendees_updated = True
    mn.updated_at = datetime.utcnow()
    silent = _payload_silent(payload)
    if attendees_updated:
        n_users = len(mn.attendees or [])
        n_guests = len(parse_guest_names(mn.guest_attendees))
        _log_activity(
            mn.id,
            "update",
            "meeting_note",
            mn.id,
            f"Updated attendees ({n_users} users, {n_guests} guests)",
        )
    elif not silent:
        _log_activity(mn.id, "update", "meeting_note", mn.id, f"Updated meeting: {mn.title}")
    db.session.commit()
    db.session.refresh(mn)
    if "agenda" in payload or agenda_notes_updated:
        try:
            from app.socketio_handlers import emit_meeting_item_event

            emit_meeting_item_event(
                mn.id,
                "agenda_updated",
                {"meeting_id": mn.id, "agenda_item_notes": parse_agenda_item_notes(mn.agenda_item_notes)},
            )
        except Exception:
            pass
    return jsonify(meeting_to_dict(mn))


@bp.route("/api/meetings/<int:meeting_id>/agenda/from-focus-rows", methods=["POST"])
@login_required
def api_agenda_from_focus_rows(meeting_id: int):
    mn = db.session.get(MeetingNote, meeting_id)
    if not mn:
        return jsonify({"error": "Not found"}), 404
    rows = (
        MeetingFocusRow.query.filter_by(meeting_note_id=meeting_id)
        .order_by(MeetingFocusRow.sort_order, MeetingFocusRow.id)
        .all()
    )
    seen = set()
    lines = []
    for r in rows:
        area = normalize_bullet_text(r.focus_area).split("\n")[0].strip() if r.focus_area else ""
        if not area:
            area = (r.platform or "").strip() or "General discussion"
        key = area.lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(area)
    agenda = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(lines))
    return jsonify({"agenda": agenda, "lines": lines})


# --- Focus rows ---


@bp.route("/api/meetings/<int:meeting_id>/focus-rows", methods=["GET", "POST"])
@login_required
def api_meeting_focus_rows(meeting_id: int):
    mn = db.session.get(MeetingNote, meeting_id)
    if not mn:
        return jsonify({"error": "Not found"}), 404
    if request.method == "GET":
        rows = (
            MeetingFocusRow.query.filter_by(meeting_note_id=meeting_id)
            .order_by(MeetingFocusRow.sort_order, MeetingFocusRow.id)
            .all()
        )
        return jsonify(
            [
                {
                    "id": r.id,
                    "platform": r.platform,
                    "focus_area": r.focus_area,
                    "sort_order": r.sort_order,
                    "discussion_notes": r.discussion_notes or "",
                }
                for r in rows
            ]
        )
    payload = request.get_json(silent=True) or {}
    fr = MeetingFocusRow(
        meeting_note_id=meeting_id,
        platform=(payload.get("platform") or "").strip(),
        focus_area=normalize_bullet_text(payload.get("focus_area")) or "",
        sort_order=int(payload.get("sort_order") or 0),
    )
    db.session.add(fr)
    db.session.flush()
    _log_activity(
        meeting_id,
        "create",
        "focus_row",
        fr.id,
        f"Added focus row: {fr.platform} / {fr.focus_area}",
    )
    db.session.commit()
    return jsonify({"id": fr.id, "platform": fr.platform, "focus_area": fr.focus_area}), 201


@bp.route("/api/focus-rows/<int:row_id>", methods=["PUT", "DELETE"])
@login_required
def api_focus_row(row_id: int):
    fr = db.session.get(MeetingFocusRow, row_id)
    if not fr:
        return jsonify({"error": "Not found"}), 404
    mid = fr.meeting_note_id
    if request.method == "DELETE":
        _log_activity(mid, "delete", "focus_row", fr.id, f"Removed focus row: {fr.platform} / {fr.focus_area}")
        db.session.delete(fr)
        db.session.commit()
        return jsonify({"ok": True})
    payload = request.get_json(silent=True) or {}
    if "platform" in payload:
        fr.platform = (payload.get("platform") or "").strip()
    if "focus_area" in payload:
        fr.focus_area = normalize_bullet_text(payload.get("focus_area")) or ""
    if "discussion_notes" in payload:
        fr.discussion_notes = (payload.get("discussion_notes") or "").strip() or None
    if "sort_order" in payload:
        fr.sort_order = int(payload.get("sort_order") or 0)
    if not _payload_silent(payload):
        _log_activity(mid, "update", "focus_row", fr.id, f"Updated focus row: {fr.platform} / {fr.focus_area}")
    db.session.commit()
    try:
        from app.socketio_handlers import emit_meeting_item_event

        emit_meeting_item_event(mid, "focus_row_updated", {"focus_row_id": fr.id, "meeting_id": mid})
    except Exception:
        pass
    return jsonify(
        {
            "id": fr.id,
            "platform": fr.platform,
            "focus_area": fr.focus_area,
            "discussion_notes": fr.discussion_notes or "",
        }
    )


# --- Action items ---


def _apply_action_item_fields(item: MeetingActionItem, payload: dict) -> None:
    if "call_to_action" in payload:
        item.call_to_action = normalize_bullet_text(payload.get("call_to_action")) or ""
    if "expected_impact" in payload:
        item.expected_impact = normalize_bullet_text(payload.get("expected_impact"))
    if "challenges" in payload:
        item.challenges = normalize_bullet_text(payload.get("challenges"))
    if "comments" in payload:
        item.comments = normalize_bullet_text(payload.get("comments"))
    if "status" in payload:
        st = (payload.get("status") or "").strip().lower()
        if st in VALID_STATUSES:
            item.status = st
    if "due_date" in payload:
        item.due_date = _parse_date_json(payload, "due_date")
    if "start_date" in payload:
        item.start_date = _parse_date_json(payload, "start_date")
    if "sort_order" in payload:
        item.sort_order = int(payload.get("sort_order") or 0)
    if "assignee_ids" in payload:
        item.assignees = _assignees_from_ids(payload.get("assignee_ids"))
    if "priority" in payload:
        pr = (payload.get("priority") or "").strip().lower()
        if pr in VALID_PRIORITIES:
            item.priority = pr
    if "label_ids" in payload:
        item.labels = _labels_from_ids(payload.get("label_ids"))
    if "source_excerpt" in payload:
        item.source_excerpt = (payload.get("source_excerpt") or "").strip() or None
    if "ai_extracted" in payload:
        item.ai_extracted = bool(payload.get("ai_extracted"))
    item.updated_at = datetime.utcnow()


@bp.route("/api/focus-rows/<int:row_id>/action-items", methods=["POST"])
@login_required
def api_create_action_item(row_id: int):
    fr = db.session.get(MeetingFocusRow, row_id)
    if not fr:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    item = MeetingActionItem(
        focus_row_id=row_id,
        call_to_action=normalize_bullet_text(payload.get("call_to_action")) or "",
        expected_impact=normalize_bullet_text(payload.get("expected_impact")),
        challenges=normalize_bullet_text(payload.get("challenges")),
        comments=normalize_bullet_text(payload.get("comments")),
        status=(payload.get("status") or "open").strip().lower()
        if (payload.get("status") or "").strip().lower() in VALID_STATUSES
        else "open",
        priority=(payload.get("priority") or "medium").strip().lower()
        if (payload.get("priority") or "medium").strip().lower() in VALID_PRIORITIES
        else "medium",
        due_date=_parse_date_json(payload, "due_date"),
        start_date=_parse_date_json(payload, "start_date"),
        source_excerpt=(payload.get("source_excerpt") or "").strip() or None,
        ai_extracted=bool(payload.get("ai_extracted")),
        sort_order=int(payload.get("sort_order") or 0),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.session.add(item)
    db.session.flush()
    if payload.get("assignee_ids"):
        item.assignees = _assignees_from_ids(payload.get("assignee_ids"))
    if payload.get("label_ids"):
        item.labels = _labels_from_ids(payload.get("label_ids"))
    _log_activity(
        fr.meeting_note_id,
        "create",
        "action_item",
        item.id,
        f"Added action item: {item.call_to_action[:120]}",
    )
    db.session.commit()
    db.session.refresh(item)
    return jsonify(item_to_dict(item)), 201


@bp.route("/api/action-items/<int:item_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def api_action_item(item_id: int):
    item = (
        MeetingActionItem.query.options(
            joinedload(MeetingActionItem.focus_row)
            .joinedload(MeetingFocusRow.meeting_note)
            .joinedload(MeetingNote.attendees),
            joinedload(MeetingActionItem.subtasks).joinedload(MeetingActionSubtask.assignee),
            joinedload(MeetingActionItem.assignees),
            joinedload(MeetingActionItem.labels),
        )
        .filter_by(id=item_id)
        .first()
    )
    if not item:
        return jsonify({"error": "Not found"}), 404
    fr = item.focus_row
    mid = fr.meeting_note_id if fr else None
    if request.method == "GET":
        return jsonify(item_to_dict(item))
    if request.method == "DELETE":
        preview = (item.call_to_action or "")[:120]
        _log_activity(mid, "delete", "action_item", item.id, f"Deleted action item: {preview}")
        db.session.delete(item)
        db.session.commit()
        return jsonify({"ok": True})
    payload = request.get_json(silent=True) or {}
    prev_status = item.status
    prev_assignees = {u.id for u in (item.assignees or [])}
    _apply_action_item_fields(item, payload)
    if not _payload_silent(payload):
        new_assignees = {u.id for u in (item.assignees or [])}
        if prev_status != item.status:
            _log_activity(
                mid,
                "update",
                "action_item",
                item.id,
                f"Status → {item.status}: {(item.call_to_action or '')[:80]}",
            )
        elif prev_assignees != new_assignees:
            _log_activity(
                mid,
                "update",
                "action_item",
                item.id,
                f"Assignees updated: {(item.call_to_action or '')[:80]}",
            )
            notify_assignees(item, mid, new_assignees, current_user.id)
        elif payload.get("log_text_edit"):
            _log_activity(
                mid,
                "update",
                "action_item",
                item.id,
                f"Updated action item: {(item.call_to_action or '')[:120]}",
            )
    db.session.commit()
    db.session.refresh(item)
    if mid:
        try:
            from app.socketio_handlers import emit_meeting_item_event
            emit_meeting_item_event(mid, "item_updated", {"id": item.id})
        except Exception:
            pass
    return jsonify(item_to_dict(item))


def _action_item_with_subtasks(item_id: int) -> Optional[MeetingActionItem]:
    return (
        MeetingActionItem.query.options(
            joinedload(MeetingActionItem.assignees),
            joinedload(MeetingActionItem.subtasks).joinedload(MeetingActionSubtask.assignee),
            joinedload(MeetingActionItem.focus_row).joinedload(MeetingFocusRow.meeting_note),
        )
        .filter_by(id=item_id)
        .first()
    )


def _meeting_id_for_action_item(item: MeetingActionItem) -> Optional[int]:
    fr = item.focus_row
    return fr.meeting_note_id if fr else None


@bp.route("/api/action-items/<int:item_id>/subtasks", methods=["GET", "POST"])
@login_required
def api_action_item_subtasks(item_id: int):
    item = _action_item_with_subtasks(item_id)
    if not item:
        return jsonify({"error": "Not found"}), 404
    if request.method == "GET":
        subtasks = sorted(item.subtasks or [], key=lambda s: (s.sort_order, s.id))
        return jsonify([subtask_to_dict(s) for s in subtasks])
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title required"}), 400
    mid = _meeting_id_for_action_item(item)
    assignee_uid = payload.get("assignee_user_id")
    if assignee_uid is not None and assignee_uid != "":
        try:
            assignee_uid = int(assignee_uid)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid assignee_user_id"}), 400
    else:
        assignee_uid = None
    err = validate_subtask_assignee(assignee_uid, mid, item)
    if err:
        return jsonify({"error": err}), 400
    max_order = max((s.sort_order for s in (item.subtasks or [])), default=-1)
    st = MeetingActionSubtask(
        action_item_id=item_id,
        title=title[:500],
        is_done=False,
        sort_order=max_order + 1,
        assignee_user_id=assignee_uid,
    )
    db.session.add(st)
    db.session.flush()
    if not _payload_silent(payload):
        _log_activity(
            mid,
            "create",
            "subtask",
            st.id,
            f"Added sub-task: {title[:120]}",
        )
    status_changed = apply_subtask_parent_rollup(item)
    if status_changed and not _payload_silent(payload):
        _log_activity(
            mid,
            "update",
            "action_item",
            item.id,
            f"Status → {item.status} (sub-tasks): {(item.call_to_action or '')[:80]}",
        )
    db.session.commit()
    st = (
        MeetingActionSubtask.query.options(joinedload(MeetingActionSubtask.assignee))
        .filter_by(id=st.id)
        .first()
    )
    return jsonify(subtask_to_dict(st)), 201


@bp.route("/api/subtasks/<int:subtask_id>", methods=["PUT", "DELETE"])
@login_required
def api_subtask(subtask_id: int):
    st = db.session.get(MeetingActionSubtask, subtask_id)
    if not st:
        return jsonify({"error": "Not found"}), 404
    item = _action_item_with_subtasks(st.action_item_id)
    if not item:
        return jsonify({"error": "Not found"}), 404
    mid = _meeting_id_for_action_item(item)
    silent = _payload_silent(request.get_json(silent=True) or {})
    if request.method == "DELETE":
        preview = (st.title or "")[:120]
        if not silent:
            _log_activity(mid, "delete", "subtask", st.id, f"Deleted sub-task: {preview}")
        db.session.delete(st)
        status_changed = apply_subtask_parent_rollup(item)
        if status_changed and not silent:
            _log_activity(
                mid,
                "update",
                "action_item",
                item.id,
                f"Status → {item.status} (sub-tasks): {(item.call_to_action or '')[:80]}",
            )
        db.session.commit()
        return jsonify({"ok": True})
    payload = request.get_json(silent=True) or {}
    prev_done = st.is_done
    if "title" in payload:
        st.title = (payload.get("title") or "").strip()[:500]
    if "is_done" in payload:
        st.is_done = bool(payload.get("is_done"))
    if "sort_order" in payload:
        st.sort_order = int(payload.get("sort_order") or 0)
    if "assignee_user_id" in payload:
        raw = payload.get("assignee_user_id")
        if raw is None or raw == "":
            st.assignee_user_id = None
        else:
            try:
                assignee_uid = int(raw)
            except (TypeError, ValueError):
                return jsonify({"error": "invalid assignee_user_id"}), 400
            err = validate_subtask_assignee(assignee_uid, mid, item)
            if err:
                return jsonify({"error": err}), 400
            st.assignee_user_id = assignee_uid
    if not silent:
        if prev_done != st.is_done:
            state = "completed" if st.is_done else "reopened"
            _log_activity(
                mid,
                "update",
                "subtask",
                st.id,
                f"Sub-task {state}: {(st.title or '')[:120]}",
            )
        elif "title" in payload:
            _log_activity(
                mid,
                "update",
                "subtask",
                st.id,
                f"Updated sub-task: {(st.title or '')[:120]}",
            )
    status_changed = apply_subtask_parent_rollup(item)
    if status_changed and not silent:
        _log_activity(
            mid,
            "update",
            "action_item",
            item.id,
            f"Status → {item.status} (sub-tasks): {(item.call_to_action or '')[:80]}",
        )
    item.updated_at = datetime.utcnow()
    db.session.commit()
    st = (
        MeetingActionSubtask.query.options(joinedload(MeetingActionSubtask.assignee))
        .filter_by(id=st.id)
        .first()
    )
    return jsonify(subtask_to_dict(st))


@bp.route("/api/action-items/<int:item_id>/subtasks/reorder", methods=["POST"])
@login_required
def api_reorder_subtasks(item_id: int):
    item = _action_item_with_subtasks(item_id)
    if not item:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    ordered_ids = payload.get("ordered_ids") or []
    if not isinstance(ordered_ids, list):
        return jsonify({"error": "ordered_ids must be a list"}), 400
    by_id = {s.id: s for s in (item.subtasks or [])}
    for idx, sid in enumerate(ordered_ids):
        try:
            sid_int = int(sid)
        except (TypeError, ValueError):
            continue
        st = by_id.get(sid_int)
        if st:
            st.sort_order = idx
    if not _payload_silent(payload):
        mid = _meeting_id_for_action_item(item)
        _log_activity(mid, "update", "subtask", item.id, "Reordered sub-tasks")
    db.session.commit()
    subtasks = sorted(item.subtasks or [], key=lambda s: (s.sort_order, s.id))
    return jsonify([subtask_to_dict(s) for s in subtasks])


@bp.route("/api/action-items/reorder", methods=["POST"])
@login_required
def api_reorder_action_items():
    payload = request.get_json(silent=True) or {}
    ordered_ids = payload.get("ordered_ids") or []
    if not isinstance(ordered_ids, list):
        return jsonify({"error": "ordered_ids must be a list"}), 400
    for idx, raw_id in enumerate(ordered_ids):
        try:
            item_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        item = db.session.get(MeetingActionItem, item_id)
        if item:
            item.sort_order = idx
            item.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/focus-rows/reorder", methods=["POST"])
@login_required
def api_reorder_focus_rows():
    payload = request.get_json(silent=True) or {}
    ordered_ids = payload.get("ordered_ids") or []
    meeting_id = payload.get("meeting_note_id")
    if not isinstance(ordered_ids, list):
        return jsonify({"error": "ordered_ids must be a list"}), 400
    for idx, raw_id in enumerate(ordered_ids):
        try:
            row_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        fr = db.session.get(MeetingFocusRow, row_id)
        if fr and (meeting_id is None or fr.meeting_note_id == int(meeting_id)):
            fr.sort_order = idx
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/labels", methods=["GET", "POST"])
@login_required
def api_labels():
    if request.method == "GET":
        rows = MeetingLabel.query.order_by(MeetingLabel.name.asc()).all()
        return jsonify([label_to_dict(lb) for lb in rows])
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    existing = MeetingLabel.query.filter_by(name=name).first()
    if existing:
        return jsonify(label_to_dict(existing))
    color = (payload.get("color") or "#64748b").strip()
    lb = MeetingLabel(name=name, color=color, created_by=current_user.id)
    db.session.add(lb)
    db.session.commit()
    return jsonify(label_to_dict(lb)), 201


@bp.route("/api/labels/<int:label_id>", methods=["PUT", "DELETE"])
@login_required
def api_label(label_id: int):
    lb = db.session.get(MeetingLabel, label_id)
    if not lb:
        return jsonify({"error": "Not found"}), 404
    if request.method == "DELETE":
        db.session.delete(lb)
        db.session.commit()
        return jsonify({"ok": True})
    payload = request.get_json(silent=True) or {}
    if "name" in payload:
        lb.name = (payload.get("name") or lb.name).strip()
    if "color" in payload:
        lb.color = (payload.get("color") or lb.color).strip()
    db.session.commit()
    return jsonify(label_to_dict(lb))


@bp.route("/api/saved-views", methods=["GET", "POST"])
@login_required
def api_saved_views():
    if request.method == "GET":
        rows = (
            MeetingSavedView.query.filter_by(user_id=current_user.id)
            .order_by(MeetingSavedView.sort_order, MeetingSavedView.id)
            .all()
        )
        return jsonify([saved_view_to_dict(v) for v in rows])
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    if payload.get("is_default"):
        MeetingSavedView.query.filter_by(user_id=current_user.id, is_default=True).update(
            {"is_default": False}
        )
    view = MeetingSavedView(
        user_id=current_user.id,
        name=name,
        filters_json=payload.get("filters_json") or {},
        view_mode=(payload.get("view_mode") or "board").strip() or "board",
        is_default=bool(payload.get("is_default")),
        sort_order=int(payload.get("sort_order") or 0),
    )
    db.session.add(view)
    db.session.commit()
    return jsonify(saved_view_to_dict(view)), 201


@bp.route("/api/saved-views/<int:view_id>", methods=["PUT", "DELETE"])
@login_required
def api_saved_view(view_id: int):
    view = MeetingSavedView.query.filter_by(id=view_id, user_id=current_user.id).first()
    if not view:
        return jsonify({"error": "Not found"}), 404
    if request.method == "DELETE":
        db.session.delete(view)
        db.session.commit()
        return jsonify({"ok": True})
    payload = request.get_json(silent=True) or {}
    if "name" in payload:
        view.name = (payload.get("name") or view.name).strip()
    if "filters_json" in payload:
        view.filters_json = payload.get("filters_json") or {}
    if "view_mode" in payload:
        view.view_mode = (payload.get("view_mode") or view.view_mode).strip()
    if "is_default" in payload and payload.get("is_default"):
        MeetingSavedView.query.filter_by(user_id=current_user.id, is_default=True).update(
            {"is_default": False}
        )
        view.is_default = True
    if "sort_order" in payload:
        view.sort_order = int(payload.get("sort_order") or 0)
    db.session.commit()
    return jsonify(saved_view_to_dict(view))


@bp.route("/api/meetings/search")
@login_required
def api_meetings_search():
    qterm = (request.args.get("q") or "").strip()
    limit = min(request.args.get("limit", default=20, type=int), 50)
    q = MeetingNote.query.order_by(MeetingNote.meeting_date.desc())
    if qterm:
        q = q.filter(or_(MeetingNote.title.ilike(f"%{qterm}%")))
    meetings = q.limit(limit).all()
    return jsonify(
        [
            {
                "id": m.id,
                "title": m.title,
                "meeting_date": m.meeting_date.isoformat() if m.meeting_date else None,
            }
            for m in meetings
        ]
    )


@bp.route("/api/hub/analytics")
@login_required
def api_hub_analytics():
    return jsonify(hub_analytics_summary())


@bp.route("/api/hub/my-tasks")
@login_required
def api_hub_my_tasks():
    return jsonify(hub_my_tasks_buckets(current_user.id))


@bp.route("/api/meetings/<int:meeting_id>/ai/extract-tasks", methods=["POST"])
@login_required
def api_ai_extract_tasks(meeting_id: int):
    payload = request.get_json(silent=True) or {}
    data, err = extract_tasks_from_notes(meeting_id, payload.get("notes_text"))
    if err:
        return jsonify({"error": err}), 400
    existing = [
        r[0]
        for r in (
            db.session.query(MeetingActionItem.call_to_action)
            .join(MeetingFocusRow, MeetingActionItem.focus_row_id == MeetingFocusRow.id)
            .filter(MeetingFocusRow.meeting_note_id == meeting_id)
            .all()
        )
    ]
    titles = [row.get("title") or "" for row in (data or {}).get("action_items") or []]
    dup_flags = semantic_duplicate_flags(titles, existing)
    return jsonify({"preview": data, "duplicate_flags": dup_flags})


@bp.route("/api/meetings/<int:meeting_id>/ai/apply-tasks", methods=["POST"])
@login_required
def api_ai_apply_tasks(meeting_id: int):
    mn = db.session.get(MeetingNote, meeting_id)
    if not mn:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    focus_row_id = payload.get("focus_row_id")
    items = payload.get("items") or []
    decisions = payload.get("decisions") or []
    fr = None
    if items:
        if not focus_row_id:
            return jsonify({"error": "focus_row_id required"}), 400
        fr = db.session.get(MeetingFocusRow, int(focus_row_id))
        if not fr or fr.meeting_note_id != meeting_id:
            return jsonify({"error": "Invalid focus row"}), 400
    elif not decisions:
        return jsonify({"error": "No items or decisions to apply"}), 400
    created = []
    for row in items:
        if not isinstance(row, dict):
            continue
        title = (row.get("title") or "").strip()
        if not title:
            continue
        item = MeetingActionItem(
            focus_row_id=fr.id,
            call_to_action=title,
            status="open",
            priority=(row.get("priority") or "medium").strip().lower()
            if (row.get("priority") or "medium").strip().lower() in VALID_PRIORITIES
            else "medium",
            due_date=_parse_date(row.get("due_date")),
            source_excerpt=(row.get("source_excerpt") or title)[:500],
            ai_extracted=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.session.add(item)
        db.session.flush()
        if row.get("assignee_id"):
            u = db.session.get(User, int(row.get("assignee_id")))
            if u:
                item.assignees = [u]
                notify_assignees(item, meeting_id, [u.id], current_user.id)
        for sub_title in row.get("subtasks") or []:
            st = (sub_title or "").strip()
            if st:
                db.session.add(
                    MeetingActionSubtask(
                        action_item_id=item.id,
                        title=st[:500],
                        is_done=False,
                        sort_order=len(item.subtasks or []),
                    )
                )
        created.append(item_to_dict(item))
    if payload.get("apply_summary"):
        summary = (payload.get("apply_summary") or "").strip()
        if summary:
            mn.summary = summary
            mn.updated_at = datetime.utcnow()
    from app.blueprints.meeting_notes.models import MeetingDecision
    decisions_created = 0
    for idx, dec in enumerate(decisions):
        if not isinstance(dec, dict):
            continue
        body = (dec.get("body") or dec if isinstance(dec, str) else "").strip()
        if isinstance(dec, dict):
            body = (dec.get("body") or "").strip()
        if not body:
            continue
        db.session.add(
            MeetingDecision(
                meeting_note_id=meeting_id,
                body=body,
                source_excerpt=(dec.get("source_excerpt") if isinstance(dec, dict) else body)[:500],
                decided_at=mn.meeting_date,
                sort_order=idx,
            )
        )
        decisions_created += 1
    _log_activity(meeting_id, "create", "action_item", None, f"AI applied {len(created)} action items")
    db.session.commit()
    if decisions_created:
        try:
            from app.socketio_handlers import emit_meeting_item_event

            emit_meeting_item_event(meeting_id, "decision_updated", {"meeting_id": meeting_id})
        except Exception:
            pass
    return jsonify({"created": created, "count": len(created), "decisions_created": decisions_created})


@bp.route("/api/meetings/<int:meeting_id>/ai/summarize", methods=["POST"])
@login_required
def api_ai_summarize(meeting_id: int):
    payload = request.get_json(silent=True) or {}
    text, err = summarize_notes(meeting_id, payload.get("notes_text"))
    if err:
        return jsonify({"error": err}), 400
    return jsonify({"summary": text})


@bp.route("/api/meetings/<int:meeting_id>/transcript", methods=["POST"])
@login_required
def api_meeting_transcript(meeting_id: int):
    mn = db.session.get(MeetingNote, meeting_id)
    if not mn:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    transcript = (payload.get("transcript") or "").strip()
    if not transcript:
        return jsonify({"error": "transcript required"}), 400
    existing = (mn.summary or "").strip()
    block = f"## Transcript\n{transcript}"
    mn.summary = f"{existing}\n\n{block}".strip() if existing else block
    mn.updated_at = datetime.utcnow()
    db.session.commit()
    data, err = extract_tasks_from_notes(meeting_id, mn.summary)
    if err:
        return jsonify({"summary_updated": True, "extract_error": err})
    return jsonify({"summary_updated": True, "preview": data})


@bp.route("/api/meetings/<int:meeting_id>/email-report", methods=["POST"])
@login_required
def api_email_meeting_report(meeting_id: int):
    meeting = db.session.get(MeetingNote, meeting_id)
    if not meeting:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    recipients = normalize_recipients(payload.get("recipients") or "")
    if not recipients:
        return jsonify({"error": "At least one valid recipient email is required"}), 400
    subject = (payload.get("subject") or "").strip() or None
    body_html = (payload.get("body_html") or "").strip() or None
    body_text = (payload.get("body_text") or "").strip() or None
    attachment_bytes = None
    attachment_filename = None
    attachment_mimetype = None
    if payload.get("attachment_base64"):
        try:
            attachment_bytes = base64.b64decode(str(payload.get("attachment_base64")), validate=True)
            attachment_filename = (payload.get("attachment_filename") or "").strip() or None
            attachment_mimetype = (payload.get("attachment_mime") or "").strip() or None
        except Exception:
            return jsonify({"error": "Invalid attachment_base64 payload"}), 400
    if payload.get("pdf_base64"):
        try:
            attachment_bytes = base64.b64decode(str(payload.get("pdf_base64")), validate=True)
            attachment_filename = (payload.get("pdf_filename") or "").strip() or None
            attachment_mimetype = "application/pdf"
        except Exception:
            return jsonify({"error": "Invalid pdf_base64 payload"}), 400
    result = send_meeting_report_email(
        meeting=meeting,
        recipients=recipients,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        attachment_bytes=attachment_bytes,
        attachment_filename=attachment_filename,
        attachment_mimetype=attachment_mimetype,
        pdf_format=(payload.get("pdf_format") or "minutes").strip().lower(),
    )
    _log_activity(
        meeting_id,
        "create",
        "meeting_note",
        meeting_id,
        f"Emailed meeting report to {result.get('sent', 0)} recipient(s)",
    )
    db.session.commit()
    if result.get("sent", 0) <= 0:
        failed_details = [r for r in (result.get("results") or []) if r.get("status") != "sent"]
        return jsonify({"error": "No emails were sent. Please check SMTP configuration.", "details": failed_details, **result}), 502
    return jsonify({"ok": True, **result})


@bp.route("/api/pdf-logo")
@login_required
def api_pdf_logo():
    url = (request.args.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url required"}), 400
    if not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"error": "Only http(s) urls allowed"}), 400
    try:
        resp = requests.get(url, timeout=12)
        if not resp.ok:
            return jsonify({"error": f"logo fetch failed ({resp.status_code})"}), 400
        content_type = (resp.headers.get("Content-Type") or "image/png").split(";")[0].strip().lower()
        if not content_type.startswith("image/"):
            return jsonify({"error": "url did not return an image"}), 400
        data_b64 = base64.b64encode(resp.content).decode("ascii")
        return jsonify({"data_url": f"data:{content_type};base64,{data_b64}"})
    except Exception as exc:
        return jsonify({"error": str(exc)[:200]}), 500


@bp.route("/api/email/diagnostics", methods=["POST"])
@login_required
def api_email_diagnostics():
    payload = request.get_json(silent=True) or {}
    to_email = (payload.get("to_email") or getattr(current_user, "email", "") or "").strip()
    if not to_email:
        return jsonify({"error": "to_email required"}), 400
    result = send_html_email_detailed(
        to_email=to_email,
        subject="[Akello] SMTP diagnostics",
        html_body="<p>SMTP diagnostics message from Akello.</p>",
        text_body="SMTP diagnostics message from Akello.",
        reply_to=(getattr(current_user, "email", "") or "").strip() or None,
    )
    return jsonify({"ok": bool(result.get("ok")), "result": result})


@bp.route("/api/templates", methods=["GET", "POST"])
@login_required
def api_templates():
    if request.method == "GET":
        rows = MeetingTemplate.query.order_by(MeetingTemplate.name.asc()).all()
        return jsonify([template_to_dict(t) for t in rows])
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    tpl = MeetingTemplate(
        name=name,
        title_pattern=(payload.get("title_pattern") or "").strip(),
        summary_template=(payload.get("summary_template") or "").strip() or None,
        focus_rows_json=payload.get("focus_rows_json") or [],
        created_by=current_user.id,
    )
    db.session.add(tpl)
    db.session.commit()
    return jsonify(template_to_dict(tpl)), 201


@bp.route("/api/templates/<int:template_id>/create-meeting", methods=["POST"])
@login_required
def api_create_meeting_from_template(template_id: int):
    tpl = db.session.get(MeetingTemplate, template_id)
    if not tpl:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    meeting_date = _parse_date_json(payload, "meeting_date") or date.today()
    title = (payload.get("title") or tpl.title_pattern or tpl.name).strip()
    mn = MeetingNote(
        title=title,
        meeting_date=meeting_date,
        summary=tpl.summary_template,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.session.add(mn)
    db.session.flush()
    for idx, row in enumerate(tpl.focus_rows_json or []):
        if not isinstance(row, dict):
            continue
        fr = MeetingFocusRow(
            meeting_note_id=mn.id,
            platform=(row.get("platform") or "").strip(),
            focus_area=(row.get("focus_area") or "").strip(),
            sort_order=idx,
        )
        db.session.add(fr)
    _log_activity(mn.id, "create", "meeting_note", mn.id, f"Created from template: {tpl.name}")
    db.session.commit()
    return jsonify({"id": mn.id, "title": mn.title}), 201


@bp.route("/api/action-items/<int:item_id>/comments", methods=["GET", "POST"])
@login_required
def api_item_comments(item_id: int):
    item = (
        MeetingActionItem.query.options(joinedload(MeetingActionItem.focus_row))
        .filter_by(id=item_id)
        .first()
    )
    if not item:
        return jsonify({"error": "Not found"}), 404
    mid = item.focus_row.meeting_note_id if item.focus_row else None
    if request.method == "GET":
        rows = (
            MeetingItemComment.query.filter_by(action_item_id=item_id)
            .order_by(MeetingItemComment.created_at.asc())
            .all()
        )
        return jsonify([comment_to_dict(c) for c in rows])
    payload = request.get_json(silent=True) or {}
    body = (payload.get("body") or "").strip()
    if not body:
        return jsonify({"error": "body required"}), 400
    comment = MeetingItemComment(
        action_item_id=item_id,
        author_user_id=current_user.id,
        body=body,
    )
    db.session.add(comment)
    users = attendees_for_meeting(mid) if mid else []
    mentioned = parse_mention_user_ids(body, users)
    if mentioned:
        notify_mentioned_users(mentioned, item, mid, current_user, body)
    _log_activity(mid, "create", "comment", comment.id, f"Comment on item #{item_id}")
    db.session.commit()
    return jsonify(comment_to_dict(comment)), 201


@bp.route("/api/mobile/meeting-notes/my-tasks")
@login_required
def api_mobile_my_tasks():
    q = action_items_query(assignee_user_id=current_user.id, status="all")
    items = q.order_by(MeetingActionItem.due_date.asc().nullslast()).limit(100).all()
    return jsonify({"items": [item_to_dict(i) for i in items]})


@bp.route("/api/mobile/meeting-notes/action-items/<int:item_id>", methods=["PUT"])
@login_required
def api_mobile_update_item(item_id: int):
    item = (
        MeetingActionItem.query.options(joinedload(MeetingActionItem.focus_row))
        .filter_by(id=item_id)
        .first()
    )
    if not item:
        return jsonify({"error": "Not found"}), 404
    payload = request.get_json(silent=True) or {}
    _apply_action_item_fields(item, payload)
    db.session.commit()
    db.session.refresh(item)
    return jsonify(item_to_dict(item))
