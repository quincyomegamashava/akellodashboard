"""Email + PDF helpers for meeting-notes reports."""

from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Iterable, List

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.email_utils import send_html_email_detailed

from app.blueprints.meeting_notes.models import MeetingActionItem, MeetingFocusRow, MeetingNote


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_recipients(raw: str | Iterable[str]) -> List[str]:
    if isinstance(raw, str):
        chunks = re.split(r"[,\s;]+", raw or "")
    else:
        chunks = list(raw or [])
    cleaned: List[str] = []
    seen = set()
    for chunk in chunks:
        email = (chunk or "").strip().lower()
        if not email or email in seen or not EMAIL_RE.match(email):
            continue
        seen.add(email)
        cleaned.append(email)
    return cleaned


def build_meeting_report_pdf(meeting: MeetingNote, items: List[MeetingActionItem]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=24,
        rightMargin=24,
        topMargin=24,
        bottomMargin=24,
        title=f"Meeting report - {meeting.title}",
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>{meeting.title or 'Meeting notes report'}</b>", styles["Title"]))
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            f"Meeting date: {(meeting.meeting_date.isoformat() if meeting.meeting_date else 'N/A')}<br/>"
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            styles["Normal"],
        )
    )
    if meeting.summary:
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Summary</b>", styles["Heading4"]))
        story.append(Paragraph((meeting.summary or "").replace("\n", "<br/>"), styles["BodyText"]))

    story.append(Spacer(1, 12))
    rows = [["Platform", "Focus area", "Task", "Due", "Status", "Priority", "Assignees"]]
    for it in items:
        fr = it.focus_row
        assignees = ", ".join(
            [f"{(u.firstname or '').strip()} {(u.lastname or '').strip()}".strip() or (u.username or "") for u in (it.assignees or [])]
        )
        rows.append(
            [
                (fr.platform if fr else "") or "General",
                (fr.focus_area if fr else "") or "",
                (it.call_to_action or "")[:280],
                it.due_date.isoformat() if it.due_date else "",
                (it.status or "open").replace("_", " "),
                (it.priority or "medium"),
                assignees,
            ]
        )

    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00407D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (3, 1), (5, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buffer.getvalue()


def send_meeting_report_email(
    *,
    meeting: MeetingNote,
    recipients: List[str],
    subject: str | None = None,
    body_html: str | None = None,
    body_text: str | None = None,
    attachment_bytes: bytes | None = None,
    attachment_filename: str | None = None,
) -> dict:
    if not recipients:
        return {"sent": 0, "failed": 0, "results": []}

    if attachment_bytes:
        pdf_bytes = attachment_bytes
    else:
        items = (
            MeetingActionItem.query.join(MeetingFocusRow, MeetingActionItem.focus_row_id == MeetingFocusRow.id)
            .filter(MeetingFocusRow.meeting_note_id == meeting.id)
            .order_by(MeetingFocusRow.sort_order, MeetingActionItem.sort_order, MeetingActionItem.id)
            .all()
        )
        pdf_bytes = build_meeting_report_pdf(meeting, items)
    safe_title = (meeting.title or "meeting_report").strip().replace(" ", "_")
    filename = attachment_filename or f"{safe_title}_{(meeting.meeting_date.isoformat() if meeting.meeting_date else 'report')}.pdf"
    report_subject = subject or f"Meeting report: {meeting.title or 'Meeting notes'}"
    html = body_html or (
        "<p>Hello,</p>"
        f"<p>Please find attached the meeting report for <strong>{meeting.title or 'Meeting notes'}</strong>.</p>"
    )
    text = body_text or f"Meeting report attached: {meeting.title or 'Meeting notes'}"

    sent = 0
    failed = 0
    results = []
    for email in recipients:
        result = send_html_email_detailed(
            to_email=email,
            subject=report_subject[:200],
            html_body=html,
            text_body=text,
            attachment_bytes=pdf_bytes,
            attachment_filename=filename,
            attachment_mimetype="application/pdf",
        )
        ok = result.get("ok", False)
        results.append(
            {
                "email": email,
                "status": "sent" if ok else "failed",
                "error": None if ok else (result.get("error") or "smtp_failed"),
                "error_code": result.get("code"),
            }
        )
        if ok:
            sent += 1
        else:
            failed += 1
    current_app.logger.info(
        "Meeting report email sent for meeting_id=%s sent=%s failed=%s",
        meeting.id,
        sent,
        failed,
    )
    return {"sent": sent, "failed": failed, "results": results}
