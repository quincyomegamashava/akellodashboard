"""Routes and JSON API for weekly meeting notes."""

from datetime import date, datetime
from typing import Any, List, Optional, Sequence

from flask import abort, jsonify, render_template, request
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from flask_login import current_user, login_required

from app import db
from app.models import User

from app.blueprints.meeting_notes import bp
from app.blueprints.meeting_notes.models import (
    MeetingActionItem,
    MeetingFocusRow,
    MeetingNote,
    MeetingNotesActivityLog,
)
from app.blueprints.meeting_notes.services import (
    VALID_STATUSES,
    action_items_query,
    carry_forward_preview,
    coalesce_activity_rows,
    distinct_platforms,
    existing_cta_keys_for_meeting,
    guest_names_to_text,
    item_to_dict,
    items_to_fc_events,
    items_to_gantt_tasks,
    meeting_to_dict,
    meetings_index_stats,
    normalize_bullet_text,
    normalize_cta_key,
    overdue_items_count,
    parse_guest_names,
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
        {"id": r.id, "platform": r.platform, "focus_area": r.focus_area} for r in focus_rows
    ]
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
    return meeting_note_id, platform, assignee_user_id, status, due_preset, due_start, due_end


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
    meeting_note_id, platform, assignee_user_id, status, due_preset, due_start, due_end = _filter_args_from_request()
    q = action_items_query(
        meeting_note_id=meeting_note_id,
        platform=platform,
        assignee_user_id=assignee_user_id,
        status=status,
        due_preset=due_preset,
        due_start=due_start,
        due_end=due_end,
    )
    items = q.order_by(MeetingNote.meeting_date.desc(), MeetingFocusRow.sort_order, MeetingActionItem.sort_order).all()
    return jsonify({"items": [item_to_dict(i) for i in items]})


@bp.route("/api/calendar-events")
@login_required
def api_calendar_events():
    meeting_note_id, platform, assignee_user_id, status, due_preset, due_start, due_end = _filter_args_from_request()
    q = action_items_query(
        meeting_note_id=meeting_note_id,
        platform=platform,
        assignee_user_id=assignee_user_id,
        status=status,
        due_preset=due_preset,
        due_start=due_start,
        due_end=due_end,
    )
    items = q.all()
    return jsonify(items_to_fc_events(items))


@bp.route("/api/gantt-tasks")
@login_required
def api_gantt_tasks():
    meeting_note_id, platform, assignee_user_id, status, due_preset, due_start, due_end = _filter_args_from_request()
    q = action_items_query(
        meeting_note_id=meeting_note_id,
        platform=platform,
        assignee_user_id=assignee_user_id,
        status=status,
        due_preset=due_preset,
        due_start=due_start,
        due_end=due_end,
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
                    due_date=it.due_date,
                    start_date=it.start_date,
                    sort_order=it.sort_order,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.session.add(new_it)
                db.session.flush()
                new_it.assignees = list(it.assignees or [])
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
                due_date=it.due_date,
                start_date=it.start_date,
                sort_order=it.sort_order,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.session.add(new_it)
            db.session.flush()
            new_it.assignees = list(it.assignees or [])
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
    else:
        _log_activity(mn.id, "update", "meeting_note", mn.id, f"Updated meeting: {mn.title}")
    db.session.commit()
    db.session.refresh(mn)
    return jsonify(meeting_to_dict(mn))


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
                {"id": r.id, "platform": r.platform, "focus_area": r.focus_area, "sort_order": r.sort_order}
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
    if "sort_order" in payload:
        fr.sort_order = int(payload.get("sort_order") or 0)
    if not _payload_silent(payload):
        _log_activity(mid, "update", "focus_row", fr.id, f"Updated focus row: {fr.platform} / {fr.focus_area}")
    db.session.commit()
    return jsonify({"id": fr.id, "platform": fr.platform, "focus_area": fr.focus_area})


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
        due_date=_parse_date_json(payload, "due_date"),
        start_date=_parse_date_json(payload, "start_date"),
        sort_order=int(payload.get("sort_order") or 0),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.session.add(item)
    db.session.flush()
    if payload.get("assignee_ids"):
        item.assignees = _assignees_from_ids(payload.get("assignee_ids"))
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


@bp.route("/api/action-items/<int:item_id>", methods=["PUT", "DELETE"])
@login_required
def api_action_item(item_id: int):
    item = (
        MeetingActionItem.query.options(joinedload(MeetingActionItem.focus_row))
        .filter_by(id=item_id)
        .first()
    )
    if not item:
        return jsonify({"error": "Not found"}), 404
    fr = item.focus_row
    mid = fr.meeting_note_id if fr else None
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
    return jsonify(item_to_dict(item))
