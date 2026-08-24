"""Meeting Notes roadmap routes: decisions, carry-forward suggestions, hub command."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from flask import jsonify, request
from flask_login import current_user, login_required

from app import db
from app.models import User

from app.blueprints.meeting_notes import bp
from app.blueprints.meeting_notes.ai import extract_tasks_from_notes, summarize_notes
from app.blueprints.meeting_notes.models import (
    MeetingActionItem,
    MeetingDecision,
    MeetingFocusRow,
    MeetingNote,
)
from app.blueprints.meeting_notes.services import (
    action_items_query,
    carry_forward_preview,
    hub_analytics_summary,
    item_to_dict,
    user_display_name,
)


def _emit_decision_updated(meeting_id: int) -> None:
    try:
        from app.socketio_handlers import emit_meeting_item_event

        emit_meeting_item_event(meeting_id, "decision_updated", {"meeting_id": meeting_id})
    except Exception:
        pass


def decision_to_dict(d: MeetingDecision) -> dict:
    owner = d.owner
    return {
        "id": d.id,
        "meeting_note_id": d.meeting_note_id,
        "body": d.body,
        "owner_user_id": d.owner_user_id,
        "owner_name": user_display_name(owner) if owner else "",
        "source_excerpt": d.source_excerpt or "",
        "decided_at": d.decided_at.isoformat() if d.decided_at else None,
        "sort_order": d.sort_order,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }


@bp.route("/api/meetings/<int:meeting_id>/decisions", methods=["GET", "POST"])
@login_required
def api_meeting_decisions(meeting_id: int):
    mn = db.session.get(MeetingNote, meeting_id)
    if not mn:
        return jsonify({"error": "Not found"}), 404
    if request.method == "GET":
        rows = (
            MeetingDecision.query.filter_by(meeting_note_id=meeting_id)
            .order_by(MeetingDecision.sort_order, MeetingDecision.id)
            .all()
        )
        return jsonify([decision_to_dict(d) for d in rows])
    payload = request.get_json(silent=True) or {}
    body = (payload.get("body") or "").strip()
    if not body:
        return jsonify({"error": "body required"}), 400
    d = MeetingDecision(
        meeting_note_id=meeting_id,
        body=body,
        owner_user_id=payload.get("owner_user_id") or current_user.id,
        source_excerpt=(payload.get("source_excerpt") or "")[:500] or None,
        decided_at=date.fromisoformat(payload["decided_at"][:10]) if payload.get("decided_at") else mn.meeting_date,
        sort_order=int(payload.get("sort_order") or 0),
    )
    db.session.add(d)
    db.session.commit()
    _emit_decision_updated(meeting_id)
    return jsonify(decision_to_dict(d)), 201


@bp.route("/api/decisions/<int:decision_id>", methods=["PUT", "DELETE"])
@login_required
def api_decision_detail(decision_id: int):
    d = db.session.get(MeetingDecision, decision_id)
    if not d:
        return jsonify({"error": "Not found"}), 404
    if request.method == "DELETE":
        meeting_id = d.meeting_note_id
        db.session.delete(d)
        db.session.commit()
        _emit_decision_updated(meeting_id)
        return jsonify({"ok": True})
    payload = request.get_json(silent=True) or {}
    if "body" in payload:
        d.body = (payload.get("body") or "").strip()
    if "owner_user_id" in payload:
        d.owner_user_id = payload.get("owner_user_id")
    if "source_excerpt" in payload:
        d.source_excerpt = (payload.get("source_excerpt") or "")[:500] or None
    if "decided_at" in payload and payload.get("decided_at"):
        try:
            d.decided_at = date.fromisoformat(str(payload["decided_at"])[:10])
        except ValueError:
            pass
    if "sort_order" in payload:
        d.sort_order = int(payload.get("sort_order") or 0)
    db.session.commit()
    _emit_decision_updated(d.meeting_note_id)
    return jsonify(decision_to_dict(d))


@bp.route("/api/meetings/<int:meeting_id>/carry-forward/suggestions", methods=["GET"])
@login_required
def api_carry_forward_suggestions(meeting_id: int):
    target = db.session.get(MeetingNote, meeting_id)
    if not target:
        return jsonify({"error": "Not found"}), 404
    source_id = request.args.get("from_meeting_id", type=int)
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
        return jsonify({"suggestions": [], "preview": {}})
    preview = carry_forward_preview(source_id, meeting_id)
    today = date.today()
    stale_cutoff = today - timedelta(days=14)
    suggestions = []
    src = db.session.get(MeetingNote, source_id)
    if src:
        from app.blueprints.meeting_notes.services import (
            existing_cta_keys_for_meeting,
            existing_lineage_roots_for_meeting,
            existing_source_ids_for_meeting,
            should_skip_carry_item,
        )

        existing = existing_cta_keys_for_meeting(meeting_id)
        existing_sources = existing_source_ids_for_meeting(meeting_id)
        existing_roots = existing_lineage_roots_for_meeting(meeting_id)
        for fr in src.focus_rows.order_by(MeetingFocusRow.sort_order):
            for it in fr.action_items.filter(MeetingActionItem.status != "done"):
                tags = []
                already = should_skip_carry_item(it, existing, existing_sources, existing_roots)
                if already:
                    tags.append("already_present")
                if (it.challenges or "").strip() and it.status == "open":
                    tags.append("blocked")
                updated = getattr(it, "updated_at", None)
                if updated and updated.date() <= stale_cutoff:
                    tags.append("stale")
                cf_count = getattr(it, "carry_forward_count", 0) or 0
                if cf_count >= 3:
                    tags.append("repeat_carry")
                suggestions.append({
                    "item": item_to_dict(it),
                    "tags": tags,
                    "already_present": already,
                    "focus_row_id": fr.id,
                    "platform": fr.platform,
                })
    return jsonify({"suggestions": suggestions, "preview": preview, "from_meeting_id": source_id})


@bp.route("/api/hub/command", methods=["POST"])
@login_required
def api_hub_command():
    payload = request.get_json(silent=True) or {}
    text = (payload.get("query") or payload.get("text") or "").strip().lower()
    if not text:
        return jsonify({"error": "query required"}), 400

    if "overdue" in text:
        return jsonify({
            "intent": "navigate",
            "url": "/meeting-notes/all-items?mine=1&due_preset=overdue",
            "message": "Opening overdue items",
        })
    if "summarize" in text or "summary" in text:
        mid = payload.get("meeting_id")
        if mid:
            summary, err = summarize_notes(int(mid), None)
            if err:
                return jsonify({"error": err}), 400
            return jsonify({"intent": "summarize", "summary": summary})
    if "extract" in text:
        mid = payload.get("meeting_id")
        if mid:
            data, err = extract_tasks_from_notes(int(mid), None)
            if err:
                return jsonify({"error": err}), 400
            return jsonify({"intent": "extract", "preview": data})
    assign_match = re.search(r"assign.*@?(\w+)", text)
    if assign_match and payload.get("meeting_id"):
        hint = assign_match.group(1)
        users = User.query.all()
        from app.blueprints.meeting_notes.ai import _fuzzy_match_user
        uid = _fuzzy_match_user(hint, users)
        if uid:
            return jsonify({
                "intent": "bulk_assign_hint",
                "assignee_id": uid,
                "message": f"Use bulk update to assign to user #{uid}",
            })
    return jsonify({"intent": "search", "query": text, "message": "Use command palette search (Ctrl+K)"})


@bp.route("/api/hub/analytics/extended")
@login_required
def api_hub_analytics_extended():
    base = hub_analytics_summary()
    today = date.today()
    users = User.query.limit(200).all()
    per_user = []
    for u in users:
        q = action_items_query(assignee_user_id=u.id, status="all")
        items = q.all()
        if not items:
            continue
        total = len(items)
        done = sum(1 for i in items if (i.status or "") == "done")
        overdue = sum(
            1
            for i in items
            if i.due_date and i.due_date < today and (i.status or "") != "done"
        )
        late_days = []
        for i in items:
            if i.due_date and i.due_date < today and (i.status or "") == "done" and i.updated_at:
                late_days.append((i.updated_at.date() - i.due_date).days)
        per_user.append({
            "user_id": u.id,
            "name": user_display_name(u),
            "completion_rate": int(round(100 * done / total)) if total else 0,
            "overdue_count": overdue,
            "avg_days_late": round(sum(late_days) / len(late_days), 1) if late_days else 0,
        })
    base["per_user"] = sorted(per_user, key=lambda x: -x["overdue_count"])[:20]
    meetings = MeetingNote.query.order_by(MeetingNote.meeting_date.desc()).limit(30).all()
    meeting_health = []
    for mn in meetings:
        total = 0
        done = 0
        for fr in mn.focus_rows:
            for it in fr.action_items:
                total += 1
                if (it.status or "") == "done":
                    done += 1
        score = int(round(100 * done / total)) if total else 100
        meeting_health.append({
            "id": mn.id,
            "title": mn.title,
            "meeting_date": mn.meeting_date.isoformat() if mn.meeting_date else None,
            "health_score": score,
            "open_items": total - done,
        })
    base["meeting_health"] = meeting_health
    return jsonify(base)
