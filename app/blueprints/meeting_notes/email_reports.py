"""Email + PDF helpers for meeting-notes reports."""

from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Iterable, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.email_utils import send_html_email_detailed

from app.blueprints.meeting_notes.models import MeetingActionItem, MeetingDecision, MeetingNote
from app.blueprints.meeting_notes.services import action_items_query, parse_guest_names, user_display_name


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
AKELLO_BLUE = colors.HexColor("#00407D")
SLATE_50 = colors.HexColor("#F8FAFC")
SLATE_200 = colors.HexColor("#E2E8F0")
SLATE_600 = colors.HexColor("#475569")
SLATE_800 = colors.HexColor("#1E293B")


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


def _paragraph(text: str, style) -> Paragraph:
    safe = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe = safe.replace("\n", "<br/>")
    return Paragraph(safe or "—", style)


def build_meeting_report_pdf(meeting: MeetingNote, items: List[MeetingActionItem]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title=f"Meeting report - {meeting.title}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=20,
        textColor=AKELLO_BLUE,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=SLATE_600,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontSize=9,
        leading=12,
        textColor=SLATE_800,
    )
    cell_style = ParagraphStyle(
        "ReportCell",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=SLATE_800,
    )
    story = []

    story.append(Paragraph(f"<b>{meeting.title or 'Meeting notes report'}</b>", title_style))
    story.append(
        Paragraph(
            "Strategic meeting action report",
            subtitle_style,
        )
    )
    story.append(
        Paragraph(
            f"Meeting date: {(meeting.meeting_date.isoformat() if meeting.meeting_date else 'N/A')}"
            f"<br/>Generated: {datetime.utcnow().strftime('%d %b %Y %H:%M UTC')}",
            subtitle_style,
        )
    )
    if meeting.summary:
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Executive summary</b>", styles["Heading4"]))
        story.append(_paragraph(meeting.summary, body_style))

    open_count = sum(1 for it in items if (it.status or "open") != "done")
    done_count = len(items) - open_count
    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            f"<b>{len(items)}</b> action items · <b>{open_count}</b> open · <b>{done_count}</b> completed",
            subtitle_style,
        )
    )
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Action items</b>", styles["Heading4"]))
    story.append(Spacer(1, 6))

    header = ["#", "Action item", "Platform", "Focus", "Priority", "Status", "Due", "Assignees"]
    rows = [header]
    for index, it in enumerate(items, start=1):
        fr = it.focus_row
        assignees = ", ".join(
            [
                f"{(u.firstname or '').strip()} {(u.lastname or '').strip()}".strip() or (u.username or "")
                for u in (it.assignees or [])
            ]
        )
        task = (it.call_to_action or "").strip() or "Untitled action item"
        rows.append(
            [
                str(index),
                _paragraph(task, cell_style),
                (fr.platform if fr else "") or "General",
                (fr.focus_area if fr else "") or "—",
                (it.priority or "medium").replace("_", " ").title(),
                (it.status or "open").replace("_", " ").title(),
                it.due_date.isoformat() if it.due_date else "—",
                assignees or "—",
            ]
        )

    col_widths = [0.35 * inch, 2.35 * inch, 0.75 * inch, 0.95 * inch, 0.65 * inch, 0.7 * inch, 0.7 * inch, 1.0 * inch]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), AKELLO_BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (4, 1), (6, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.25, SLATE_200),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SLATE_50]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buffer.getvalue()


def _parse_agenda_lines(agenda_text: str | None) -> List[str]:
    lines = []
    for raw in (agenda_text or "").replace("\r\n", "\n").split("\n"):
        line = re.sub(r"^\d+[\.\)]\s*", "", raw.strip())
        if line:
            lines.append(line)
    return lines


def build_meeting_minutes_pdf(
    meeting: MeetingNote,
    items: List[MeetingActionItem],
    decisions: List[MeetingDecision] | None = None,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title=f"Meeting minutes - {meeting.title}",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "MinutesTitle",
        parent=styles["Title"],
        fontSize=16,
        textColor=AKELLO_BLUE,
        alignment=1,
        spaceAfter=10,
    )
    label_style = ParagraphStyle(
        "MinutesLabel",
        parent=styles["Normal"],
        fontSize=7,
        textColor=SLATE_600,
        spaceAfter=2,
    )
    cell_style = ParagraphStyle(
        "MinutesCell",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        textColor=SLATE_800,
    )
    story = []
    story.append(Paragraph("<b>MEETING MINUTES</b>", title_style))
    story.append(Spacer(1, 6))

    meta_row = Table(
        [
            [
                Paragraph("<b>SUBJECT</b><br/>" + (meeting.title or "—"), cell_style),
                Paragraph("<b>PLACE</b><br/>" + (meeting.location or "—"), cell_style),
            ],
            [
                Paragraph(
                    "<b>DATE</b><br/>" + (meeting.meeting_date.isoformat() if meeting.meeting_date else "—"),
                    cell_style,
                ),
                Paragraph("<b>TIME</b><br/>" + (meeting.meeting_time or "—"), cell_style),
            ],
        ],
        colWidths=[3.45 * inch, 3.45 * inch],
    )
    meta_row.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, SLATE_200),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(meta_row)
    story.append(Spacer(1, 8))

    agenda_lines = _parse_agenda_lines(meeting.agenda)
    if not agenda_lines:
        agenda_html = "<br/>".join(f"{i + 1}. _________________________" for i in range(5))
    else:
        agenda_html = "<br/>".join(f"{i + 1}. {line}" for i, line in enumerate(agenda_lines))

    taken_by = user_display_name(meeting.creator) if meeting.creator else "—"
    attendee_bits = []
    for u in meeting.attendees or []:
        attendee_bits.append(f"• {user_display_name(u)}")
    for g in parse_guest_names(meeting.guest_attendees):
        attendee_bits.append(f"• {g} (Guest)")
    attendees_html = "<br/>".join(attendee_bits) if attendee_bits else "—"

    mid_row = Table(
        [
            [
                Paragraph(f"<b>AGENDA</b><br/>{agenda_html}", cell_style),
                Paragraph(
                    f"<b>MINUTES TAKEN BY</b><br/>{taken_by}<br/><br/><b>ATTENDEES</b><br/>{attendees_html}",
                    cell_style,
                ),
            ]
        ],
        colWidths=[3.3 * inch, 3.6 * inch],
    )
    mid_row.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, SLATE_200),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(mid_row)
    story.append(Spacer(1, 8))

    summary_safe = (meeting.summary or "—").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
    notes_block = Table(
        [[Paragraph(f"<b>MEETING NOTES</b><br/>{summary_safe}", cell_style)]],
        colWidths=[6.9 * inch],
    )
    notes_block.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, SLATE_200), ("LEFTPADDING", (0, 0), (-1, -1), 6)]))
    story.append(notes_block)
    story.append(Spacer(1, 8))

    decisions = decisions or []
    if decisions:
        story.append(Paragraph("<b>KEY DECISIONS</b>", styles["Heading4"]))
        dec_rows = [["#", "Decision", "Owner"]]
        for idx, d in enumerate(decisions, start=1):
            owner = user_display_name(d.owner) if d.owner else "Team"
            dec_rows.append([str(idx), _paragraph(d.body or "", cell_style), owner])
        dec_table = Table(dec_rows, colWidths=[0.35 * inch, 5.0 * inch, 1.55 * inch], repeatRows=1)
        dec_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), AKELLO_BLUE),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.25, SLATE_200),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(dec_table)
        story.append(Spacer(1, 8))

    story.append(Paragraph("<b>ACTION ITEMS</b>", styles["Heading4"]))
    story.append(Spacer(1, 4))
    action_rows = [["ACTION ITEM", "IN-CHARGE", "COMPLETION DATE", "STATUS"]]
    for it in items:
        assignees = ", ".join(user_display_name(u) for u in (it.assignees or [])) or "—"
        action_rows.append(
            [
                _paragraph((it.call_to_action or "").strip() or "Untitled", cell_style),
                assignees,
                it.due_date.isoformat() if it.due_date else "—",
                (it.status or "open").replace("_", " ").title(),
            ]
        )
    if len(action_rows) == 1:
        action_rows.append(["No action items recorded.", "—", "—", "—"])

    action_table = Table(
        action_rows,
        colWidths=[3.0 * inch, 1.5 * inch, 1.2 * inch, 1.2 * inch],
        repeatRows=1,
    )
    action_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), AKELLO_BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, SLATE_200),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SLATE_50]),
            ]
        )
    )
    story.append(action_table)
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            f"Generated: {datetime.utcnow().strftime('%d %b %Y %H:%M UTC')}",
            label_style,
        )
    )
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
    pdf_format: str = "minutes",
) -> dict:
    items = (
        action_items_query(meeting_note_id=meeting.id, status="all")
        .order_by(MeetingActionItem.sort_order.asc(), MeetingActionItem.id.asc())
        .all()
    )
    items = [it for it in items if (it.status or "open") != "done"] if pdf_format == "minutes" else items

    email_subject = subject or f"Meeting report: {meeting.title or 'Meeting notes'}"
    html_body = body_html or "<p>Please find attached the latest meeting minutes.</p>"
    text_body = body_text or "Please find attached the latest meeting minutes."

    pdf_bytes = attachment_bytes
    if not pdf_bytes:
        if pdf_format == "minutes":
            decisions = (
                MeetingDecision.query.filter_by(meeting_note_id=meeting.id)
                .order_by(MeetingDecision.sort_order, MeetingDecision.id)
                .all()
            )
            pdf_bytes = build_meeting_minutes_pdf(meeting, items, decisions)
        else:
            pdf_bytes = build_meeting_report_pdf(meeting, items)

    safe_title = re.sub(r"[^\w\-]+", "_", (meeting.title or "meeting")).strip("_")[:40] or "meeting"
    date_part = meeting.meeting_date.isoformat() if meeting.meeting_date else "report"
    prefix = "meeting-minutes" if pdf_format == "minutes" else "meeting-notes"
    filename = attachment_filename or f"{prefix}_{safe_title}_{date_part}.pdf"

    results: List[dict] = []
    sent = 0
    failed = 0
    for email in recipients:
        res = send_html_email_detailed(
            to_email=email,
            subject=email_subject,
            html_body=html_body,
            text_body=text_body,
            attachment_bytes=pdf_bytes,
            attachment_filename=filename,
        )
        if res.get("ok"):
            sent += 1
            results.append({"email": email, "status": "sent"})
        else:
            failed += 1
            results.append({"email": email, "status": "failed", "error": res.get("error")})

    return {"sent": sent, "failed": failed, "results": results}
