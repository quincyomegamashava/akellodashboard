"""Shared SMTP email helpers."""

import smtplib
from email.message import EmailMessage
from typing import List, Optional

from flask import current_app


def send_email_message(message: EmailMessage) -> bool:
    if current_app.config.get("MAIL_SUPPRESS_SEND"):
        current_app.logger.info(
            "[MAIL_SUPPRESS_SEND] Email skipped for recipients=%s",
            message.get_all("To", []),
        )
        return True

    smtp_host = current_app.config.get("MAIL_SERVER", "smtp.gmail.com")
    smtp_port = current_app.config.get("MAIL_PORT", 587)
    use_tls = current_app.config.get("MAIL_USE_TLS", True)
    username = current_app.config.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD")

    if not (username and password):
        current_app.logger.warning("Email not sent: MAIL_USERNAME/PASSWORD not fully configured")
        return False

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        if use_tls:
            server.starttls()
        server.login(username, password)
        server.send_message(message)
    return True


def send_html_email(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> bool:
    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME")
    if not sender:
        current_app.logger.warning("Email skipped: sender not configured")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(text_body or html_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")
    return send_email_message(msg)


def send_bulk_html_emails(
    *,
    recipients: List[str],
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    footer_note: str = "Reply to this email to unsubscribe from future communications.",
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
            ok = send_html_email(
                to_email=email,
                subject=subject,
                html_body=full_html,
                text_body=full_text,
            )
            results.append({"email": email, "status": "sent" if ok else "failed", "error": None if ok else "smtp_failed"})
        except Exception as exc:
            current_app.logger.exception("Bulk email failed for %s", email)
            results.append({"email": email, "status": "failed", "error": str(exc)[:500]})
    return results
