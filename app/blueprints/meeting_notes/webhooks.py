"""Outgoing Slack (Incoming Webhook) helpers for meeting notes."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import List, Optional

from flask import current_app

from app.blueprints.meeting_notes.models import MeetingActionItem, MeetingNote
from app.blueprints.meeting_notes.services import action_items_query, user_display_name


def get_mn_slack_webhook_url() -> str:
    url = (os.environ.get("MN_SLACK_WEBHOOK_URL") or "").strip()
    if url:
        return url
    try:
        from app.models import AppSetting

        url = (AppSetting.get_value("mn_slack_webhook_url", "") or "").strip()
    except Exception:
        url = ""
    if not url:
        url = (current_app.config.get("MN_SLACK_WEBHOOK_URL") or "").strip()
    return url


def build_meeting_slack_payload(
    meeting: MeetingNote,
    *,
    headline: Optional[str] = None,
    items: Optional[List[MeetingActionItem]] = None,
    app_base_url: str = "",
) -> dict:
    title = meeting.title or "Meeting notes"
    date_str = meeting.meeting_date.isoformat() if meeting.meeting_date else "N/A"
    if items is None:
        items = (
            action_items_query(meeting_note_id=meeting.id, status="all")
            .order_by(MeetingActionItem.sort_order.asc(), MeetingActionItem.id.asc())
            .all()
        )
    open_items = [it for it in items if (it.status or "open") != "done"]
    base = (app_base_url or "").rstrip("/")
    link = f"{base}/meeting-notes/{meeting.id}" if base else f"/meeting-notes/{meeting.id}"

    lines = []
    for it in open_items[:8]:
        cta = (it.call_to_action or "").strip().replace("\n", " ")[:100] or "Untitled"
        owners = ", ".join(user_display_name(u) for u in (it.assignees or [])) or "Unassigned"
        due = it.due_date.isoformat() if it.due_date else "—"
        lines.append(f"• {cta} — {owners} (due {due})")
    more = ""
    if len(open_items) > 8:
        more = f"\n…and {len(open_items) - 8} more"

    text = (
        (headline or f"Meeting updates: *{title}* ({date_str})")
        + f"\n*{len(open_items)}* open action item(s)\n"
        + ("\n".join(lines) if lines else "_No open action items_")
        + more
        + f"\n<{link}|Open meeting notes>"
    )
    return {"text": text}


def post_slack_webhook(payload: dict, webhook_url: Optional[str] = None) -> dict:
    url = (webhook_url or get_mn_slack_webhook_url()).strip()
    if not url:
        return {"ok": False, "skipped": True, "error": "Slack webhook not configured"}
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"ok": True, "status_code": getattr(resp, "status", 200), "body": body[:200]}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "error": f"HTTP {exc.code}: {(exc.read() or b'')[:200].decode('utf-8', errors='replace')}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}


def share_meeting_to_slack(
    meeting: MeetingNote,
    *,
    headline: Optional[str] = None,
    app_base_url: str = "",
) -> dict:
    payload = build_meeting_slack_payload(
        meeting,
        headline=headline,
        app_base_url=app_base_url,
    )
    return post_slack_webhook(payload)
