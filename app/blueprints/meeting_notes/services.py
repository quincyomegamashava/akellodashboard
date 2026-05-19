"""Query helpers and serialization for meeting notes."""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app import db
from app.models import User

from app.blueprints.meeting_notes.models import (
    MeetingActionItem,
    MeetingFocusRow,
    MeetingNote,
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
    return {
        "id": mn.id,
        "title": mn.title,
        "meeting_date": mn.meeting_date.isoformat() if mn.meeting_date else None,
        "summary": mn.summary,
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


def action_items_query(
    meeting_note_id: Optional[int] = None,
    platform: Optional[str] = None,
    assignee_user_id: Optional[int] = None,
    status: Optional[str] = None,
    due_preset: Optional[str] = None,
    due_start: Optional[date] = None,
    due_end: Optional[date] = None,
) -> Any:
    q = (
        MeetingActionItem.query.options(
            joinedload(MeetingActionItem.assignees),
            joinedload(MeetingActionItem.focus_row).joinedload(MeetingFocusRow.meeting_note),
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

    return q


def item_to_dict(item: MeetingActionItem) -> dict:
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
    progress = 0
    if item.status == "in_progress":
        progress = 50
    elif item.status == "done":
        progress = 100
    return {
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
        "assignee_ids": [u.id for u in assignees],
        "assignee_names": names,
        "gantt_start": start_d.isoformat() if start_d else None,
        "gantt_end": end_d.isoformat() if end_d else None,
        "progress": progress,
    }


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


def existing_cta_keys_for_meeting(meeting_note_id: int) -> set:
    rows = (
        db.session.query(MeetingActionItem.call_to_action)
        .join(MeetingFocusRow, MeetingActionItem.focus_row_id == MeetingFocusRow.id)
        .filter(MeetingFocusRow.meeting_note_id == meeting_note_id)
        .all()
    )
    return {normalize_cta_key(r[0]) for r in rows if r and r[0]}


def carry_forward_preview(source_meeting_id: int, target_meeting_id: int) -> dict:
    """Count open items on source that would be copied (excluding duplicates on target)."""
    src = db.session.get(MeetingNote, source_meeting_id)
    if not src:
        return {"error": "Source not found", "count": 0, "skipped_duplicate": 0}
    existing = existing_cta_keys_for_meeting(target_meeting_id)
    to_copy = 0
    skipped = 0
    for fr in src.focus_rows.order_by(MeetingFocusRow.sort_order, MeetingFocusRow.id):
        for it in fr.action_items.filter(MeetingActionItem.status != "done").order_by(
            MeetingActionItem.sort_order, MeetingActionItem.id
        ):
            key = normalize_cta_key(it.call_to_action)
            if not key:
                continue
            if key in existing:
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


def overdue_items_count(assignee_user_id: Optional[int] = None) -> int:
    today = date.today()
    q = action_items_query(
        assignee_user_id=assignee_user_id,
        due_preset="overdue",
    )
    return q.count()
