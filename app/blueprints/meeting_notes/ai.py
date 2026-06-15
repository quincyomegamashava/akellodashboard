"""AI helpers for meeting notes: extract tasks, summarize, transcript."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

import requests
from flask import current_app

from app import db
from app.models import User

from app.blueprints.meeting_notes.models import MeetingNote, VALID_PRIORITIES
from app.blueprints.meeting_notes.services import distinct_platforms, user_display_name


def _call_openai(prompt_text: str) -> Tuple[Optional[str], Optional[str]]:
    api_key = current_app.config.get("OPENAI_API_KEY")
    if not api_key:
        return None, "OPENAI_API_KEY is not configured."

    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": current_app.config.get("OPENAI_MODEL", "gpt-4.1-mini"),
                "input": prompt_text,
            },
            timeout=90,
        )
        if response.status_code >= 400:
            return None, "Generation provider returned an error."
        data = response.json()
        output_text = data.get("output_text")
        if output_text:
            return output_text, None
        return str(data), None
    except requests.RequestException:
        return None, "Unable to reach OpenAI endpoint."


def _extract_json_block(text: str) -> Optional[dict]:
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _fuzzy_match_user(hint: str, users: List[User]) -> Optional[int]:
    hint = (hint or "").strip().lower()
    if not hint:
        return None
    best_id = None
    best_score = 0.0
    for u in users:
        full = f"{(u.firstname or '').strip()} {(u.lastname or '').strip()}".strip().lower()
        candidates = [u.username.lower(), full, (u.firstname or "").lower(), (u.lastname or "").lower()]
        for cand in candidates:
            if not cand:
                continue
            if hint == cand or hint in cand or cand in hint:
                return u.id
            score = SequenceMatcher(None, hint, cand).ratio()
            if score > best_score and score >= 0.55:
                best_score = score
                best_id = u.id
    return best_id


def _parse_due_hint(hint: str, meeting_date: Optional[date]) -> Optional[date]:
    if not hint:
        return None
    hint = hint.strip().lower()
    base = meeting_date or date.today()
    if hint in ("today", "asap", "now"):
        return base
    if hint == "tomorrow":
        return base + timedelta(days=1)
    if "next week" in hint:
        return base + timedelta(days=7)
    if "friday" in hint or "fri" in hint:
        days_ahead = (4 - base.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return base + timedelta(days=days_ahead)
    iso_match = re.search(r"(\d{4}-\d{2}-\d{2})", hint)
    if iso_match:
        try:
            return date.fromisoformat(iso_match.group(1))
        except ValueError:
            pass
    return None


def build_extract_prompt(mn: MeetingNote, notes_text: str, users: List[User]) -> str:
    platforms = distinct_platforms(mn.id)
    attendee_lines = [user_display_name(u) for u in (mn.attendees or [])]
    user_lines = [f"- {user_display_name(u)} (id={u.id})" for u in users[:80]]
    return f"""You are a meeting assistant. Extract structured output from meeting notes.

Meeting title: {mn.title}
Meeting date: {mn.meeting_date.isoformat() if mn.meeting_date else 'unknown'}
Attendees: {', '.join(attendee_lines) or 'none'}
Known platforms: {', '.join(platforms) or 'none'}
Team members:
{chr(10).join(user_lines)}

Raw notes:
{notes_text}

Return ONLY valid JSON with this schema:
{{
  "summary": "short polished summary",
  "decisions": ["decision 1"],
  "action_items": [
    {{
      "title": "clear action",
      "assignee_hint": "name or empty",
      "due_hint": "natural language due date or empty",
      "platform": "platform name or empty",
      "priority": "low|medium|high|urgent",
      "subtasks": ["optional step"],
      "source_excerpt": "quote from notes"
    }}
  ]
}}
"""


def normalize_ai_extract_result(
    raw: dict,
    users: List[User],
    meeting_date: Optional[date],
    platforms: List[str],
) -> dict:
    summary = (raw.get("summary") or "").strip()
    decisions = [str(d).strip() for d in (raw.get("decisions") or []) if str(d).strip()]
    items_out = []
    for row in raw.get("action_items") or []:
        if not isinstance(row, dict):
            continue
        title = (row.get("title") or "").strip()
        if not title:
            continue
        priority = (row.get("priority") or "medium").strip().lower()
        if priority not in VALID_PRIORITIES:
            priority = "medium"
        platform = (row.get("platform") or "").strip()
        if not platform and platforms:
            platform = platforms[0]
        assignee_id = _fuzzy_match_user(row.get("assignee_hint") or "", users)
        due_date = _parse_due_hint(row.get("due_hint") or "", meeting_date)
        items_out.append(
            {
                "title": title,
                "assignee_hint": row.get("assignee_hint") or "",
                "assignee_id": assignee_id,
                "due_hint": row.get("due_hint") or "",
                "due_date": due_date.isoformat() if due_date else None,
                "platform": platform,
                "priority": priority,
                "subtasks": [str(s).strip() for s in (row.get("subtasks") or []) if str(s).strip()],
                "source_excerpt": (row.get("source_excerpt") or title)[:500],
            }
        )
    return {"summary": summary, "decisions": decisions, "action_items": items_out}


def extract_tasks_from_notes(meeting_id: int, notes_text: Optional[str] = None) -> Tuple[Optional[dict], Optional[str]]:
    mn = db.session.get(MeetingNote, meeting_id)
    if not mn:
        return None, "Meeting not found"
    text = (notes_text or mn.summary or "").strip()
    if not text:
        return None, "No notes to extract from"
    users = User.query.order_by(User.firstname, User.lastname).all()
    prompt = build_extract_prompt(mn, text, users)
    output, err = _call_openai(prompt)
    if err:
        return None, err
    parsed = _extract_json_block(output or "")
    if not parsed:
        return None, "Could not parse AI response"
    platforms = distinct_platforms(meeting_id)
    return normalize_ai_extract_result(parsed, users, mn.meeting_date, platforms), None


def summarize_notes(meeting_id: int, notes_text: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    mn = db.session.get(MeetingNote, meeting_id)
    if not mn:
        return None, "Meeting not found"
    text = (notes_text or mn.summary or "").strip()
    if not text:
        return None, "No notes to summarize"
    prompt = f"""Polish these meeting notes into clear markdown with sections:
## Summary
## Decisions
## Discussion
## Action items (bullets only, no assignment)

Notes:
{text}
"""
    return _call_openai(prompt)


def semantic_duplicate_flags(
    new_titles: List[str],
    existing_titles: List[str],
    threshold: float = 0.82,
) -> List[Dict[str, Any]]:
    flags = []
    for nt in new_titles:
        nt_l = (nt or "").strip().lower()
        if not nt_l:
            continue
        for et in existing_titles:
            et_l = (et or "").strip().lower()
            if not et_l:
                continue
            ratio = SequenceMatcher(None, nt_l, et_l).ratio()
            if ratio >= threshold:
                flags.append({"new_title": nt, "existing_title": et, "similarity": round(ratio, 2)})
                break
    return flags
