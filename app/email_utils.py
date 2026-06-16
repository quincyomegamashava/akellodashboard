"""Shared SMTP email helpers."""

import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from typing import List, Optional

from flask import current_app

DEFAULT_SENDER_EMAIL = "quincy.mashava@akello.co"


def send_email_message_detailed(message: EmailMessage) -> dict:
    if current_app.config.get("MAIL_SUPPRESS_SEND"):
        current_app.logger.info(
            "[MAIL_SUPPRESS_SEND] Email skipped for recipients=%s",
            message.get_all("To", []),
        )
        return {"ok": True, "error": None, "code": "suppressed"}

    smtp_host = current_app.config.get("MAIL_SERVER", "smtp.gmail.com")
    smtp_port = current_app.config.get("MAIL_PORT", 587)
    use_tls = current_app.config.get("MAIL_USE_TLS", True)
    username = current_app.config.get("MAIL_USERNAME") or DEFAULT_SENDER_EMAIL
    password = current_app.config.get("MAIL_PASSWORD")

    if not (username and password):
        current_app.logger.warning("Email not sent: MAIL_USERNAME/PASSWORD not fully configured")
        return {"ok": False, "error": "MAIL_USERNAME/PASSWORD not fully configured", "code": "mail_credentials_missing"}

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            if use_tls:
                server.starttls()
            server.login(username, password)
            server.send_message(message)
        return {"ok": True, "error": None, "code": "sent"}
    except smtplib.SMTPAuthenticationError as exc:
        return {"ok": False, "error": f"SMTP auth failed: {str(exc)[:240]}", "code": "smtp_auth_failed"}
    except smtplib.SMTPRecipientsRefused as exc:
        return {"ok": False, "error": f"Recipient refused: {str(exc)[:240]}", "code": "recipient_refused"}
    except smtplib.SMTPSenderRefused as exc:
        return {"ok": False, "error": f"Sender refused: {str(exc)[:240]}", "code": "sender_refused"}
    except smtplib.SMTPException as exc:
        return {"ok": False, "error": f"SMTP error: {str(exc)[:240]}", "code": "smtp_error"}
    except Exception as exc:
        return {"ok": False, "error": f"Unexpected mail error: {str(exc)[:240]}", "code": "unexpected_error"}


def send_email_message(message: EmailMessage) -> bool:
    return send_email_message_detailed(message).get("ok", False)


def send_html_email(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    reply_to: Optional[str] = None,
    from_name: Optional[str] = None,
    attachment_bytes: Optional[bytes] = None,
    attachment_filename: Optional[str] = None,
    attachment_mimetype: str = "application/pdf",
) -> bool:
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME") or DEFAULT_SENDER_EMAIL
    if not sender:
        current_app.logger.warning("Email skipped: sender not configured")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, sender)) if from_name else sender
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text_body or html_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    if attachment_bytes:
        maintype, subtype = (attachment_mimetype or "application/pdf").split("/", 1)
        msg.add_attachment(
            attachment_bytes,
            maintype=maintype,
            subtype=subtype,
            filename=attachment_filename or "attachment.pdf",
        )
    return send_email_message(msg)


def send_html_email_detailed(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    reply_to: Optional[str] = None,
    from_name: Optional[str] = None,
    attachment_bytes: Optional[bytes] = None,
    attachment_filename: Optional[str] = None,
    attachment_mimetype: str = "application/pdf",
) -> dict:
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME") or DEFAULT_SENDER_EMAIL
    if not sender:
        current_app.logger.warning("Email skipped: sender not configured")
        return {"ok": False, "error": "sender not configured", "code": "sender_missing"}

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, sender)) if from_name else sender
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text_body or html_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    if attachment_bytes:
        maintype, subtype = (attachment_mimetype or "application/pdf").split("/", 1)
        msg.add_attachment(
            attachment_bytes,
            maintype=maintype,
            subtype=subtype,
            filename=attachment_filename or "attachment.pdf",
        )
    return send_email_message_detailed(msg)


def send_bulk_html_emails(
    *,
    recipients: List[str],
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    footer_note: str = "Reply to this email to unsubscribe from future communications.",
    reply_to: Optional[str] = None,
    from_name: Optional[str] = None,
) -> List[dict]:
    """Send one email per recipient; returns per-recipient status dicts."""
    full_html = html_body
    if footer_note and footer_note not in html_body:
        full_html = f"{html_body}<hr><p style='font-size:12px;color:#666;'>{footer_note}</p>"
    full_text = (text_body or "") + f"\n\n{footer_note}" if footer_note else (text_body or "")

    results = []
    for email in recipients:
        email = (email or "").strip()
        if not email:
            results.append({"email": email, "status": "skipped", "error": "empty"})
            continue
        try:
            result = send_html_email_detailed(
                to_email=email,
                subject=subject,
                html_body=full_html,
                text_body=full_text,
                reply_to=reply_to,
                from_name=from_name,
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
        except Exception as exc:
            current_app.logger.exception("Bulk email failed for %s", email)
            results.append({"email": email, "status": "failed", "error": str(exc)[:500]})
    return results
