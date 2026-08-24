"""IMAP email ingest → unified HelpDeskQuery tickets."""

from __future__ import annotations

import logging
from typing import Optional, Tuple

from app import db
from app.models import HelpDeskQuery, Ticket

logger = logging.getLogger(__name__)


def create_query_from_email(
    *,
    sender_email: str,
    subject: str,
    body: str,
    message_id: str,
    created_at=None,
    team_id: Optional[int] = None,
) -> Optional[HelpDeskQuery]:
    """Create a source=email HelpDeskQuery if message_id is new."""
    from app.blueprints.help_desk.services import create_ticket

    if not message_id:
        return None
    existing = HelpDeskQuery.query.filter_by(message_id=message_id).first()
    if existing:
        return None

    q = create_ticket(
        title=subject or "(No subject)",
        description=body or "",
        query_type="self",
        created_by="email",
        source="email",
        priority="normal",
        category="general",
        requester_email=sender_email,
        message_id=message_id,
        team_id=team_id,
        auto_assign=bool(team_id),
    )
    if created_at:
        q.timestamp = created_at
    db.session.commit()
    return q


def migrate_legacy_ticket(ticket: Ticket, team_id: Optional[int] = None) -> Optional[HelpDeskQuery]:
    """Convert a legacy Ticket row into a HelpDeskQuery if not already present."""
    if ticket.message_id:
        existing = HelpDeskQuery.query.filter_by(message_id=ticket.message_id).first()
        if existing:
            return existing
    from app.blueprints.help_desk.services import create_ticket, set_status

    q = create_ticket(
        title=ticket.subject or "(No subject)",
        description=ticket.message or "",
        query_type="self",
        created_by="email",
        source="email",
        requester_email=ticket.sender_email,
        message_id=ticket.message_id,
        team_id=team_id,
        auto_assign=bool(team_id),
    )
    if ticket.created_at:
        q.timestamp = ticket.created_at
    if ticket.status == "closed":
        set_status(q, "Resolved")
    db.session.commit()
    return q


def fetch_emails_into_queries(flask_app) -> Tuple[int, Optional[str]]:
    """
    Fetch unread IMAP emails and create HelpDeskQuery records (and legacy Ticket for compat).
    Returns (count_created, error_message).
    """
    import email
    import imaplib
    import re
    from datetime import datetime
    from email.header import decode_header
    from email.utils import parsedate_to_datetime

    def _decode_header_value(header_value):
        if not header_value:
            return ""
        parts = decode_header(header_value)
        result = []
        for part, charset in parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                result.append(part)
        return " ".join(result).strip()

    def _extract_email_address(from_header):
        if not from_header:
            return ""
        decoded = _decode_header_value(from_header)
        match = re.search(r"<([^>]+)>", decoded)
        if match:
            return match.group(1).strip()
        return decoded.strip() if decoded else ""

    def _get_body(msg):
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            body = payload.decode(charset, errors="replace")
                    except Exception:
                        pass
                    break
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
            except Exception:
                pass
        return body or ""

    count_created = 0
    server = flask_app.config.get("HELPDESK_IMAP_SERVER", "outlook.office365.com")
    port = int(flask_app.config.get("HELPDESK_IMAP_PORT", 993))
    email_address = flask_app.config.get("HELPDESK_EMAIL")
    app_password = flask_app.config.get("HELPDESK_APP_PASSWORD")

    if not email_address or not app_password:
        logger.warning("Helpdesk IMAP: credentials not set; skipping fetch.")
        return 0, "Email configuration not set"

    # Optional default team for email intake
    default_team_id = None
    try:
        from app.models import AppSetting

        raw = AppSetting.get_value("helpdesk_default_email_team_id", "")
        if raw and raw.isdigit():
            default_team_id = int(raw)
    except Exception:
        pass

    mail = None
    try:
        mail = imaplib.IMAP4_SSL(server, port)
        mail.login(email_address, app_password)
        mail.select("INBOX")

        status, message_ids = mail.search(None, "UNSEEN")
        if status != "OK" or not message_ids[0]:
            return 0, None

        for num in message_ids[0].split():
            try:
                status, data = mail.fetch(num, "(RFC822)")
                if status != "OK" or not data or not data[0]:
                    continue
                raw = data[0][1]
                msg = email.message_from_bytes(raw)

                msg_id_raw = msg.get("Message-ID", "").strip()
                message_id = msg_id_raw.strip("<>").strip() if msg_id_raw else None
                if not message_id:
                    mail.store(num, "+FLAGS", "\\Seen")
                    continue

                if HelpDeskQuery.query.filter_by(message_id=message_id).first():
                    mail.store(num, "+FLAGS", "\\Seen")
                    continue

                subject = _decode_header_value(msg.get("Subject", ""))
                sender_email = _extract_email_address(msg.get("From", "")) or "unknown@unknown"
                body = _get_body(msg)
                try:
                    date_parsed = parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else None
                except Exception:
                    date_parsed = None

                # Legacy Ticket row (compat with old dashboard)
                if not Ticket.query.filter_by(message_id=message_id).first():
                    db.session.add(
                        Ticket(
                            sender_email=sender_email,
                            subject=subject or "(No subject)",
                            message=body,
                            status="open",
                            created_at=date_parsed or datetime.utcnow(),
                            message_id=message_id,
                        )
                    )

                create_query_from_email(
                    sender_email=sender_email,
                    subject=subject,
                    body=body,
                    message_id=message_id,
                    created_at=date_parsed,
                    team_id=default_team_id,
                )
                count_created += 1
                mail.store(num, "+FLAGS", "\\Seen")
            except Exception as e:
                logger.exception("Error processing email: %s", e)
                db.session.rollback()
                try:
                    mail.store(num, "+FLAGS", "\\Seen")
                except Exception:
                    pass

        return count_created, None
    except imaplib.IMAP4.error as e:
        logger.exception("IMAP error: %s", e)
        return count_created, str(e)
    except Exception as e:
        logger.exception("Helpdesk email fetch error: %s", e)
        return count_created, str(e)
    finally:
        if mail:
            try:
                mail.logout()
            except Exception:
                pass
