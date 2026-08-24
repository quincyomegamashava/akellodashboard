"""Query helpers and serialization for meeting notes."""

from __future__ import annotations

import json
import re
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app import db
from app.models import User

from app.blueprints.meeting_notes.models import (
    MeetingActionItem,
    MeetingActionSubtask,
    MeetingFocusRow,
    MeetingItemComment,
    MeetingLabel,
    MeetingNote,
    MeetingSavedView,
    MeetingTemplate,
    VALID_PRIORITIES,
)


VALID_STATUSES = ("open", "in_progress", "done")

_BULLET_PREFIX_RE = re.compile(r"^[-*•]\s*")


def normalize_bullet_text(value: Optional[str]) -> Optional[str]:
    """Normalize multiline bullet text: one non-empty line per bullet, no leading markers."""
    if value is None:
        return None
    raw = str(value).replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return None
    lines = []
    for line in raw.split("\n"):
        cleaned = _BULLET_PREFIX_RE.sub("", line.strip())
        if cleaned:
            lines.append(cleaned)
    if not lines:
        return None
    return "\n".join(lines)


def parse_guest_names(value: Optional[str]) -> List[str]:
    if not value:
        return []
    names = []
    seen = set()
    for line in str(value).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        name = line.strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def parse_agenda_item_notes(value: Optional[str]) -> Dict[str, str]:
    if not value:
        return {}
    try:
        data = json.loads(value)
        if isinstance(data, dict):
            return {str(k): str(v or "") for k, v in data.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return {}


def agenda_item_notes_to_text(notes: Optional[dict]) -> Optional[str]:
    if not notes or not isinstance(notes, dict):
        return None
    cleaned = {str(k): str(v or "") for k, v in notes.items()}
    if not cleaned:
        return None
    return json.dumps(cleaned)


def guest_names_to_text(names: Optional[Sequence[str]]) -> Optional[str]:
    if not names:
        return None
    cleaned: List[str] = []
    seen = set()
    for raw in names:
        name = (raw or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(name)
    if not cleaned:
        return None
    return "\n".join(cleaned)


def user_display_name(user: User) -> str:
    return f"{(user.firstname or '').strip()} {(user.lastname or '').strip()}".strip() or user.username


def meeting_to_dict(mn: MeetingNote) -> dict:
    attendees = mn.attendees or []
    attendee_names = [user_display_name(u) for u in attendees]
    guest_names = parse_guest_names(mn.guest_attendees)
    creator_name = user_display_name(mn.creator) if mn.creator else ""
    return {
        "id": mn.id,
        "title": mn.title,
        "meeting_date": mn.meeting_date.isoformat() if mn.meeting_date else None,
        "summary": mn.summary,
        "location": mn.location or "",
        "meeting_time": mn.meeting_time or "",
        "agenda": mn.agenda or "",
        "agenda_item_notes": parse_agenda_item_notes(mn.agenda_item_notes),
        "minutes_taken_by": creator_name,
        "attendee_ids": [u.id for u in attendees],
        "attendee_names": attendee_names,
        "guest_names": guest_names,
    }


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _month_end(d: date) -> date:
    last = monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last)


def due_range_for_preset(
    preset: Optional[str],
    custom_start: Optional[date],
    custom_end: Optional[date],
    today: Optional[date] = None,
) -> Tuple[Optional[date], Optional[date], Optional[str]]:
    """
    Returns (start, end, mode) where mode is 'between', 'null', or None (no due filter).
    For 'between', both start and end inclusive.
    """
    t = today or date.today()
    preset = (preset or "").strip().lower() or None

    if preset == "none":
        return None, None, "null"

    if preset == "custom":
        if custom_start and custom_end:
            return custom_start, custom_end, "between"
        if custom_start:
            return custom_start, custom_start, "between"
        return None, None, None

    if preset == "overdue":
        return None, t - timedelta(days=1), "between"

    if preset == "this_week":
        start = t - timedelta(days=t.weekday())
        end = start + timedelta(days=6)
        return start, end, "between"

    if preset == "this_month":
        return _month_start(t), _month_end(t), "between"

    if preset == "next_month":
        y, m = t.year, t.month
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
        start = date(y, m, 1)
        end = _month_end(start)
        return start, end, "between"

    return None, None, None


def label_to_dict(label: MeetingLabel) -> dict:
    return {"id": label.id, "name": label.name, "color": label.color}


def saved_view_to_dict(view: MeetingSavedView) -> dict:
    return {
        "id": view.id,
        "name": view.name,
        "filters_json": view.filters_json or {},
        "view_mode": view.view_mode,
        "is_default": bool(view.is_default),
        "sort_order": view.sort_order,
    }


def template_to_dict(tpl: MeetingTemplate) -> dict:
    return {
        "id": tpl.id,
        "name": tpl.name,
        "title_pattern": tpl.title_pattern,
        "summary_template": tpl.summary_template,
        "focus_rows_json": tpl.focus_rows_json or [],
    }


def comment_to_dict(comment: MeetingItemComment) -> dict:
    author = comment.author
    aname = user_display_name(author) if author else "?"
    return {
        "id": comment.id,
        "action_item_id": comment.action_item_id,
        "author_user_id": comment.author_user_id,
        "author_name": aname,
        "body": comment.body,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


def parse_mention_user_ids(body: str, users: Sequence[User]) -> set:
    """Find @Firstname Lastname or @username mentions in comment body."""
    if not body:
        return set()
    found = set()
    lower_body = body.lower()
    for u in users:
        full = f"{(u.firstname or '').strip()} {(u.lastname or '').strip()}".strip()
        candidates = [u.username]
        if full:
            candidates.append(full)
        for cand in candidates:
            if not cand:
                continue
            needle = "@" + cand.lower()
            if needle in lower_body:
                found.add(u.id)
    return found


def action_items_query(
    meeting_note_id: Optional[int] = None,
    platform: Optional[str] = None,
    assignee_user_id: Optional[int] = None,
    status: Optional[str] = None,
    due_preset: Optional[str] = None,
    due_start: Optional[date] = None,
    due_end: Optional[date] = None,
    priority: Optional[str] = None,
    label_id: Optional[int] = None,
    search_q: Optional[str] = None,
    stakeholder_lead_id: Optional[int] = None,
    marketing_event_id: Optional[int] = None,
) -> Any:
    q = (
        MeetingActionItem.query.options(
            joinedload(MeetingActionItem.assignees),
            joinedload(MeetingActionItem.labels),
            joinedload(MeetingActionItem.subtasks).joinedload(MeetingActionSubtask.assignee),
            joinedload(MeetingActionItem.source_item)
            .joinedload(MeetingActionItem.focus_row)
            .joinedload(MeetingFocusRow.meeting_note),
            joinedload(MeetingActionItem.focus_row)
            .joinedload(MeetingFocusRow.meeting_note)
            .joinedload(MeetingNote.attendees),
        )
        .join(MeetingFocusRow, MeetingActionItem.focus_row_id == MeetingFocusRow.id)
        .join(MeetingNote, MeetingFocusRow.meeting_note_id == MeetingNote.id)
    )

    if meeting_note_id is not None:
        q = q.filter(MeetingNote.id == meeting_note_id)

    if platform and platform.strip():
        q = q.filter(MeetingFocusRow.platform.ilike(f"%{platform.strip()}%"))

    if assignee_user_id is not None:
        q = q.filter(MeetingActionItem.assignees.any(User.id == assignee_user_id))

    if status and status.strip().lower() not in ("", "all"):
        st = status.strip().lower()
        if st in VALID_STATUSES:
            q = q.filter(MeetingActionItem.status == st)

    dstart, dend, dmode = due_range_for_preset(due_preset, due_start, due_end)
    if dmode == "null":
        q = q.filter(MeetingActionItem.due_date.is_(None))
    elif dmode == "between" and dstart is not None and dend is not None:
        q = q.filter(
            MeetingActionItem.due_date.isnot(None),
            MeetingActionItem.due_date >= dstart,
            MeetingActionItem.due_date <= dend,
        )
    elif dmode == "between" and dstart is None and dend is not None:
        q = q.filter(MeetingActionItem.due_date.isnot(None), MeetingActionItem.due_date <= dend)

    if priority and priority.strip().lower() in VALID_PRIORITIES:
        q = q.filter(MeetingActionItem.priority == priority.strip().lower())

    if label_id is not None:
        q = q.filter(MeetingActionItem.labels.any(MeetingLabel.id == label_id))

    if search_q and search_q.strip():
        term = f"%{search_q.strip()}%"
        q = q.filter(
            db.or_(
                MeetingActionItem.call_to_action.ilike(term),
                MeetingActionItem.comments.ilike(term),
                MeetingFocusRow.platform.ilike(term),
            )
        )

    if stakeholder_lead_id is not None:
        q = q.filter(MeetingActionItem.stakeholder_lead_id == stakeholder_lead_id)
    if marketing_event_id is not None:
        q = q.filter(MeetingActionItem.marketing_event_id == marketing_event_id)

    return q


def attendees_for_meeting(meeting_id: Optional[int]) -> List[User]:
    """Registered users listed as attendees on a meeting."""
    if not meeting_id:
        return []
    mn = db.session.get(MeetingNote, meeting_id)
    if not mn:
        return []
    return list(mn.attendees or [])


def attendee_ids_for_meeting(meeting_id: Optional[int]) -> List[int]:
    return [u.id for u in attendees_for_meeting(meeting_id)]


def subtask_allowed_assignee_ids(
    meeting_id: Optional[int],
    item: Optional[MeetingActionItem] = None,
) -> set:
    """Users who may be assigned to a sub-task: meeting attendees plus task owners."""
    allowed = set(attendee_ids_for_meeting(meeting_id))
    if item:
        for u in item.assignees or []:
            allowed.add(u.id)
    return allowed


def validate_subtask_assignee(
    assignee_user_id: Optional[int],
    meeting_id: Optional[int],
    item: Optional[MeetingActionItem] = None,
) -> Optional[str]:
    """Return error message if assignee is invalid for this meeting/task."""
    if assignee_user_id is None:
        return None
    allowed = subtask_allowed_assignee_ids(meeting_id, item)
    if assignee_user_id not in allowed:
        return "Assignee must be a meeting attendee or someone assigned to this task"
    return None


def subtask_to_dict(st: MeetingActionSubtask) -> dict:
    assignee = getattr(st, "assignee", None)
    aname = user_display_name(assignee) if assignee else None
    return {
        "id": st.id,
        "title": st.title,
        "is_done": bool(st.is_done),
        "sort_order": st.sort_order,
        "assignee_user_id": st.assignee_user_id,
        "assignee_name": aname,
    }


def rollup_parent_status_from_subtasks(item: MeetingActionItem) -> Optional[str]:
    subtasks = list(item.subtasks or [])
    if not subtasks:
        return None
    done_count = sum(1 for s in subtasks if s.is_done)
    if done_count == len(subtasks):
        return "done"
    if done_count > 0:
        return "in_progress"
    return "open"


def apply_subtask_parent_rollup(item: MeetingActionItem) -> bool:
    """Update parent status from sub-task completion. Returns True if status changed."""
    new_status = rollup_parent_status_from_subtasks(item)
    if new_status is None or item.status == new_status:
        return False
    item.status = new_status
    item.updated_at = datetime.utcnow()
    return True


def item_to_dict(
    item: MeetingActionItem,
    comment_threads: Optional[Sequence[MeetingItemComment]] = None,
) -> dict:
    fr = item.focus_row
    mn = fr.meeting_note if fr else None
    assignees = item.assignees or []
    names = []
    for u in assignees:
        names.append(f"{(u.firstname or '').strip()} {(u.lastname or '').strip()}".strip() or u.username)
    start_d = item.start_date or item.due_date
    end_d = item.due_date or item.start_date
    if start_d and end_d and end_d < start_d:
        start_d, end_d = end_d, start_d
    subtasks = sorted(item.subtasks or [], key=lambda s: (s.sort_order, s.id))
    subtask_done_count = sum(1 for s in subtasks if s.is_done)
    subtask_total = len(subtasks)
    progress = 0
    if subtask_total:
        progress = int(round(100 * subtask_done_count / subtask_total))
    elif item.status == "in_progress":
        progress = 50
    elif item.status == "done":
        progress = 100
    d = {
        "id": item.id,
        "call_to_action": item.call_to_action,
        "expected_impact": item.expected_impact or "",
        "challenges": item.challenges or "",
        "comments": item.comments or "",
        "status": item.status,
        "due_date": item.due_date.isoformat() if item.due_date else None,
        "start_date": item.start_date.isoformat() if item.start_date else None,
        "sort_order": item.sort_order,
        "platform": fr.platform if fr else "",
        "focus_area": fr.focus_area if fr else "",
        "focus_row_id": fr.id if fr else None,
        "meeting_note_id": mn.id if mn else None,
        "meeting_title": mn.title if mn else "",
        "meeting_date": mn.meeting_date.isoformat() if mn and mn.meeting_date else None,
        "meeting_attendee_ids": [u.id for u in (mn.attendees or [])] if mn else [],
        "assignee_ids": [u.id for u in assignees],
        "assignee_names": names,
        "gantt_start": start_d.isoformat() if start_d else None,
        "gantt_end": end_d.isoformat() if end_d else None,
        "progress": progress,
        "subtasks": [subtask_to_dict(s) for s in subtasks],
        "subtask_done_count": subtask_done_count,
        "subtask_total": subtask_total,
        "priority": getattr(item, "priority", None) or "medium",
        "label_ids": [lb.id for lb in (item.labels or [])],
        "labels": [label_to_dict(lb) for lb in (item.labels or [])],
        "source_excerpt": getattr(item, "source_excerpt", None) or "",
        "ai_extracted": bool(getattr(item, "ai_extracted", False)),
        "carry_forward_count": getattr(item, "carry_forward_count", 0) or 0,
        "source_item_id": getattr(item, "source_item_id", None),
        "lineage_root_id": lineage_root_id(item),
        "source_meeting_note_id": None,
        "source_meeting_title": None,
        "stakeholder_lead_id": getattr(item, "stakeholder_lead_id", None),
        "marketing_event_id": getattr(item, "marketing_event_id", None),
    }
    src = getattr(item, "source_item", None)
    if src is not None:
        src_fr = src.focus_row
        src_mn = src_fr.meeting_note if src_fr else None
        if src_mn:
            d["source_meeting_note_id"] = src_mn.id
            d["source_meeting_title"] = src_mn.title or ""
    if comment_threads is not None:
        d["comment_threads"] = [comment_to_dict(c) for c in comment_threads]
    return d


def items_to_fc_events(items: Sequence[MeetingActionItem]) -> List[dict]:
    out = []
    for it in items:
        d = item_to_dict(it)
        due = it.due_date
        if not due:
            continue
        title = f"[{d['platform']}] {it.call_to_action[:80]}{'…' if len(it.call_to_action) > 80 else ''}"
        out.append(
            {
                "id": str(it.id),
                "title": title,
                "start": due.isoformat(),
                "allDay": True,
                "extendedProps": {
                    "meeting_note_id": d["meeting_note_id"],
                    "status": it.status,
                    "assignees": ", ".join(d["assignee_names"]),
                },
                "url": d.get("meeting_note_id")
                and f"/meeting-notes/{d['meeting_note_id']}?view=table&highlight={it.id}",
            }
        )
    return out


def items_to_gantt_tasks(items: Sequence[MeetingActionItem]) -> List[dict]:
    tasks = []
    for it in items:
        d = item_to_dict(it)
        gs, ge = d.get("gantt_start"), d.get("gantt_end")
        if not gs:
            continue
        if not ge:
            ge = gs
        try:
            sdt = datetime.fromisoformat(gs).date()
            edt = datetime.fromisoformat(ge).date()
            if edt <= sdt:
                edt = sdt + timedelta(days=1)
        except Exception:
            continue
        name = f"[{d['platform']}] {it.call_to_action[:60]}{'…' if len(it.call_to_action) > 60 else ''}"
        status = (it.status or "open").lower()
        custom_class = "gantt-open"
        if status == "in_progress":
            custom_class = "gantt-in-progress"
        elif status == "done":
            custom_class = "gantt-done"
        tasks.append(
            {
                "id": str(it.id),
                "name": name,
                "start": sdt.isoformat(),
                "end": edt.isoformat(),
                "progress": d["progress"],
                "custom_class": custom_class,
            }
        )
    return tasks


def distinct_platforms(meeting_note_id: Optional[int] = None) -> List[str]:
    q = db.session.query(MeetingFocusRow.platform).distinct().filter(MeetingFocusRow.platform != "")
    if meeting_note_id is not None:
        q = q.filter(MeetingFocusRow.meeting_note_id == meeting_note_id)
    rows = q.order_by(MeetingFocusRow.platform.asc()).all()
    return [r[0] for r in rows if r and r[0]]


def coalesce_activity_rows(rows: Sequence[dict], window_seconds: int = 90) -> List[dict]:
    """Merge noisy consecutive update logs for the same entity."""
    if not rows:
        return []
    parsed = []
    for r in rows:
        ts = None
        if r.get("occurred_at"):
            try:
                ts = datetime.fromisoformat(str(r["occurred_at"]).replace("Z", ""))
            except ValueError:
                ts = None
        parsed.append({**r, "_ts": ts})
    out: List[dict] = []
    i = 0
    while i < len(parsed):
        cur = parsed[i]
        if cur.get("action") != "update":
            out.append({k: v for k, v in cur.items() if k != "_ts"})
            i += 1
            continue
        group = [cur]
        j = i + 1
        while j < len(parsed):
            nxt = parsed[j]
            if nxt.get("action") != "update":
                break
            if (
                nxt.get("entity_type") == cur.get("entity_type")
                and nxt.get("entity_id") == cur.get("entity_id")
                and nxt.get("actor") == cur.get("actor")
                and cur.get("_ts")
                and nxt.get("_ts")
                and abs((cur["_ts"] - nxt["_ts"]).total_seconds()) <= window_seconds
            ):
                group.append(nxt)
                j += 1
            else:
                break
        if len(group) > 1:
            merged = {k: v for k, v in group[0].items() if k != "_ts"}
            merged["summary"] = f"Edited {merged.get('entity_type', 'item')} ({len(group)} saves)"
            merged["coalesced_count"] = len(group)
            out.append(merged)
        else:
            out.append({k: v for k, v in cur.items() if k != "_ts"})
        i = j if j > i else i + 1
    return out


def meetings_index_stats(meeting_ids: Sequence[int]) -> Dict[int, dict]:
    if not meeting_ids:
        return {}
    ids = list(meeting_ids)
    counts = (
        db.session.query(
            MeetingFocusRow.meeting_note_id,
            MeetingActionItem.status,
            func.count(MeetingActionItem.id),
        )
        .join(MeetingActionItem, MeetingActionItem.focus_row_id == MeetingFocusRow.id)
        .filter(MeetingFocusRow.meeting_note_id.in_(ids))
        .group_by(MeetingFocusRow.meeting_note_id, MeetingActionItem.status)
        .all()
    )
    stats: Dict[int, dict] = {
        mid: {"open": 0, "in_progress": 0, "done": 0, "total": 0} for mid in ids
    }
    for mid, status, cnt in counts:
        if mid not in stats:
            stats[mid] = {"open": 0, "in_progress": 0, "done": 0, "total": 0}
        stats[mid][status] = cnt
        stats[mid]["total"] += cnt
    return stats


def normalize_cta_key(call_to_action: Optional[str]) -> str:
    cta = (call_to_action or "").strip()
    prefix = "[carried forward]"
    if cta.lower().startswith(prefix):
        cta = cta[len(prefix) :].strip()
    return cta.lower()


def lineage_root_id(item: MeetingActionItem, max_depth: int = 32) -> int:
    """Walk source_item_id chain to the root item id."""
    current = item
    seen = set()
    depth = 0
    while current is not None and depth < max_depth:
        if current.id in seen:
            break
        seen.add(current.id)
        sid = getattr(current, "source_item_id", None)
        if not sid:
            return current.id
        parent = getattr(current, "source_item", None)
        if parent is None:
            parent = db.session.get(MeetingActionItem, sid)
        if parent is None:
            return current.id
        current = parent
        depth += 1
    return current.id if current is not None else item.id


def existing_cta_keys_for_meeting(meeting_note_id: int) -> set:
    rows = (
        db.session.query(MeetingActionItem.call_to_action)
        .join(MeetingFocusRow, MeetingActionItem.focus_row_id == MeetingFocusRow.id)
        .filter(MeetingFocusRow.meeting_note_id == meeting_note_id)
        .all()
    )
    return {normalize_cta_key(r[0]) for r in rows if r and r[0]}


def existing_source_ids_for_meeting(meeting_note_id: int) -> set:
    """Direct source_item_id values already present on the target meeting."""
    rows = (
        db.session.query(MeetingActionItem.source_item_id)
        .join(MeetingFocusRow, MeetingActionItem.focus_row_id == MeetingFocusRow.id)
        .filter(
            MeetingFocusRow.meeting_note_id == meeting_note_id,
            MeetingActionItem.source_item_id.isnot(None),
        )
        .all()
    )
    return {r[0] for r in rows if r and r[0]}


def existing_lineage_roots_for_meeting(meeting_note_id: int) -> set:
    items = (
        MeetingActionItem.query.options(
            joinedload(MeetingActionItem.source_item),
        )
        .join(MeetingFocusRow, MeetingActionItem.focus_row_id == MeetingFocusRow.id)
        .filter(MeetingFocusRow.meeting_note_id == meeting_note_id)
        .all()
    )
    return {lineage_root_id(it) for it in items}


def find_or_create_focus_row(
    meeting_note_id: int,
    platform: str,
    focus_area: str,
    sort_order: int = 0,
    cache: Optional[Dict[Tuple[str, str], MeetingFocusRow]] = None,
) -> MeetingFocusRow:
    """Reuse an existing focus row on the meeting with the same platform + focus_area."""
    key = ((platform or "").strip().lower(), (focus_area or "").strip().lower())
    if cache is not None and key in cache:
        return cache[key]
    existing = (
        MeetingFocusRow.query.filter_by(meeting_note_id=meeting_note_id)
        .order_by(MeetingFocusRow.sort_order, MeetingFocusRow.id)
        .all()
    )
    for fr in existing:
        fr_key = ((fr.platform or "").strip().lower(), (fr.focus_area or "").strip().lower())
        if fr_key == key:
            if cache is not None:
                cache[key] = fr
            return fr
    new_fr = MeetingFocusRow(
        meeting_note_id=meeting_note_id,
        platform=platform,
        focus_area=focus_area,
        sort_order=sort_order,
    )
    db.session.add(new_fr)
    db.session.flush()
    if cache is not None:
        cache[key] = new_fr
    return new_fr


def should_skip_carry_item(
    item: MeetingActionItem,
    existing_cta_keys: set,
    existing_source_ids: set,
    existing_roots: set,
) -> bool:
    key = normalize_cta_key(item.call_to_action)
    if not key:
        return True
    if key in existing_cta_keys:
        return True
    if item.id in existing_source_ids:
        return True
    root = lineage_root_id(item)
    if root in existing_roots or item.id in existing_roots:
        return True
    return False


def carry_forward_preview(source_meeting_id: int, target_meeting_id: int) -> dict:
    """Count open items on source that would be copied (excluding duplicates on target)."""
    src = db.session.get(MeetingNote, source_meeting_id)
    if not src:
        return {"error": "Source not found", "count": 0, "skipped_duplicate": 0}
    existing = existing_cta_keys_for_meeting(target_meeting_id)
    existing_sources = existing_source_ids_for_meeting(target_meeting_id)
    existing_roots = existing_lineage_roots_for_meeting(target_meeting_id)
    to_copy = 0
    skipped = 0
    for fr in src.focus_rows.order_by(MeetingFocusRow.sort_order, MeetingFocusRow.id):
        for it in fr.action_items.filter(MeetingActionItem.status != "done").order_by(
            MeetingActionItem.sort_order, MeetingActionItem.id
        ):
            if should_skip_carry_item(it, existing, existing_sources, existing_roots):
                skipped += 1
            else:
                to_copy += 1
    return {
        "from_meeting_id": source_meeting_id,
        "from_meeting_title": src.title,
        "from_meeting_date": src.meeting_date.isoformat() if src.meeting_date else None,
        "count": to_copy,
        "skipped_duplicate": skipped,
    }


def collapse_items_by_lineage(items: Sequence[MeetingActionItem]) -> List[MeetingActionItem]:
    """Keep one canonical row per lineage root: prefer newest non-done, else newest."""
    buckets: Dict[int, List[MeetingActionItem]] = {}
    for it in items:
        root = lineage_root_id(it)
        buckets.setdefault(root, []).append(it)

    def _rank(it: MeetingActionItem) -> tuple:
        is_open = 0 if (it.status or "open") != "done" else 1
        created = it.created_at or datetime.min
        return (is_open, -created.timestamp() if hasattr(created, "timestamp") else 0, -it.id)

    out: List[MeetingActionItem] = []
    for group in buckets.values():
        group_sorted = sorted(group, key=_rank)
        out.append(group_sorted[0])
    return out


def overdue_items_count(assignee_user_id: Optional[int] = None) -> int:
    q = action_items_query(
        assignee_user_id=assignee_user_id,
        due_preset="overdue",
    )
    return q.count()


def copy_subtasks_to_item(source: MeetingActionItem, target: MeetingActionItem) -> None:
    for st in sorted(source.subtasks or [], key=lambda s: (s.sort_order, s.id)):
        db.session.add(
            MeetingActionSubtask(
                action_item_id=target.id,
                title=st.title,
                is_done=False,
                sort_order=st.sort_order,
            )
        )


def hub_user_items_query(user_id: int) -> Any:
    """Action items assigned to the user on the task or on any sub-task."""
    return (
        MeetingActionItem.query.options(
            joinedload(MeetingActionItem.assignees),
            joinedload(MeetingActionItem.labels),
            joinedload(MeetingActionItem.subtasks).joinedload(MeetingActionSubtask.assignee),
            joinedload(MeetingActionItem.focus_row)
            .joinedload(MeetingFocusRow.meeting_note)
            .joinedload(MeetingNote.attendees),
        )
        .join(MeetingFocusRow, MeetingActionItem.focus_row_id == MeetingFocusRow.id)
        .join(MeetingNote, MeetingFocusRow.meeting_note_id == MeetingNote.id)
        .filter(
            or_(
                MeetingActionItem.assignees.any(User.id == user_id),
                MeetingActionItem.subtasks.any(MeetingActionSubtask.assignee_user_id == user_id),
            )
        )
    )


def hub_my_tasks_buckets(user_id: int) -> dict:
    """Bucket hub tasks: overdue, due this week, in progress."""
    today = date.today()
    week_start, week_end, _ = due_range_for_preset("this_week", None, None)
    items = hub_user_items_query(user_id).order_by(
        MeetingNote.meeting_date.desc(),
        MeetingFocusRow.sort_order,
        MeetingActionItem.sort_order,
    ).all()
    items = collapse_items_by_lineage(items)

    overdue: List[dict] = []
    due_week: List[dict] = []
    in_progress: List[dict] = []
    seen: set = set()

    for it in items:
        if it.id in seen:
            continue
        seen.add(it.id)
        d = item_to_dict(it)
        st = (it.status or "open").lower()
        if st == "done":
            continue
        due = it.due_date
        in_overdue = False
        in_week = False
        if due and due < today:
            overdue.append(d)
            in_overdue = True
        if due and week_start and week_end and week_start <= due <= week_end:
            due_week.append(d)
            in_week = True
        # In-progress status, or open tasks not already shown by date buckets
        if st == "in_progress" or (st == "open" and not in_overdue and not in_week):
            in_progress.append(d)

    return {
        "overdue": overdue,
        "due_this_week": due_week,
        "in_progress": in_progress,
    }


def hub_analytics_summary() -> dict:
    """Completion and overdue stats for hub analytics strip."""
    today = date.today()
    total = MeetingActionItem.query.count()
    done = MeetingActionItem.query.filter_by(status="done").count()
    overdue = MeetingActionItem.query.filter(
        MeetingActionItem.due_date.isnot(None),
        MeetingActionItem.due_date < today,
        MeetingActionItem.status.in_(("open", "in_progress")),
    ).count()
    by_platform = (
        db.session.query(MeetingFocusRow.platform, MeetingActionItem.status, func.count(MeetingActionItem.id))
        .join(MeetingActionItem, MeetingActionItem.focus_row_id == MeetingFocusRow.id)
        .group_by(MeetingFocusRow.platform, MeetingActionItem.status)
        .all()
    )
    platform_stats: Dict[str, dict] = {}
    for plat, status, cnt in by_platform:
        if not plat:
            continue
        if plat not in platform_stats:
            platform_stats[plat] = {"open": 0, "in_progress": 0, "done": 0, "total": 0}
        platform_stats[plat][status] = cnt
        platform_stats[plat]["total"] += cnt
    completion_rate = int(round(100 * done / total)) if total else 0
    return {
        "total_items": total,
        "done_items": done,
        "overdue_items": overdue,
        "completion_rate": completion_rate,
        "by_platform": platform_stats,
    }
