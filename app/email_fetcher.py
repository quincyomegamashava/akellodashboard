"""
Fetch unread emails from Outlook via IMAP and create helpdesk tickets.

Configuration: Set HELPDESK_EMAIL (Outlook address) and HELPDESK_APP_PASSWORD (app password)
in your .env file or environment. See config.py HELPDESK_* settings.
"""
import imaplib
import email
from email.header import decode_header
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)


def _decode_header_value(header_value):
    """Decode MIME-encoded header (e.g. subject, from) into a string."""
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
    """Extract email address from From header (e.g. 'Name <user@domain.com>')."""
    if not from_header:
        return ""
    decoded = _decode_header_value(from_header)
    match = re.search(r"<([^>]+)>", decoded)
    if match:
        return match.group(1).strip()
    return decoded.strip() if decoded else ""


def _get_body(msg):
    """Extract plain-text body from email message (prefer text/plain)."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="replace")
                except Exception:
                    pass
                break
        if not body:
            for part in msg.walk():
                if part.get_content_maintype() == "text":
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


def _parse_date(date_str):
    """Parse email Date header; return datetime or None."""
    if not date_str:
        return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def fetch_emails_and_create_tickets(flask_app):
    """
    Connect to Outlook IMAP, fetch unread emails, create Ticket records, mark as read.
    Run inside Flask app context (caller must use app.app_context() or pass app from request).
    Returns (count_created, error_message). error_message is None on success.
    """
    from app import db
    from app.models import Ticket

    count_created = 0
    # Credentials: set HELPDESK_EMAIL and HELPDESK_APP_PASSWORD in .env
    server = flask_app.config.get("HELPDESK_IMAP_SERVER", "outlook.office365.com")
    port = int(flask_app.config.get("HELPDESK_IMAP_PORT", 993))
    email_address = flask_app.config.get("HELPDESK_EMAIL")
    app_password = flask_app.config.get("HELPDESK_APP_PASSWORD")

    if not email_address or not app_password:
        logger.warning("Helpdesk IMAP: HELPDESK_EMAIL or HELPDESK_APP_PASSWORD not set; skipping fetch.")
        return 0, "Email configuration not set"

    mail = None
    try:
        # IMAP over SSL: outlook.office365.com, port 993
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

                # Message-ID: strip angle brackets for storage
                msg_id_raw = msg.get("Message-ID", "").strip()
                message_id = None
                if msg_id_raw:
                    message_id = msg_id_raw.strip("<>").strip() or None

                # Skip if no Message-ID (optional: could use a fallback like date+from)
                if not message_id:
                    logger.debug("Skipping email without Message-ID")
                    mail.store(num, "+FLAGS", "\\Seen")
                    continue

                # Deduplicate
                existing = db.session.query(Ticket).filter_by(message_id=message_id).first()
                if existing:
                    mail.store(num, "+FLAGS", "\\Seen")
                    continue

                subject = _decode_header_value(msg.get("Subject", ""))
                from_header = msg.get("From", "")
                sender_email = _extract_email_address(from_header) or "unknown@unknown"
                body = _get_body(msg)
                date_parsed = _parse_date(msg.get("Date"))

                ticket = Ticket(
                    sender_email=sender_email,
                    subject=subject or "(No subject)",
                    message=body,
                    status="open",
                    created_at=date_parsed or datetime.utcnow(),
                    message_id=message_id,
                )
                db.session.add(ticket)
                db.session.commit()
                count_created += 1
                # Mark as read after successful create
                mail.store(num, "+FLAGS", "\\Seen")
            except Exception as e:
                logger.exception("Error processing email: %s", e)
                db.session.rollback()
                # Still mark as read to avoid endless retry (optional: remove if you prefer to retry)
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
