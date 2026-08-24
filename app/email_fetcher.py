"""
Fetch unread emails from Outlook via IMAP and create helpdesk tickets.

Configuration: Set HELPDESK_EMAIL (Outlook address) and HELPDESK_APP_PASSWORD (app password)
in your .env file or environment. See config.py HELPDESK_* settings.
"""
import logging

logger = logging.getLogger(__name__)


def fetch_emails_and_create_tickets(flask_app):
    """
    Connect to Outlook IMAP, fetch unread emails, create unified HelpDeskQuery tickets
    (and legacy Ticket rows for compatibility). Returns (count_created, error_message).
    """
    from app.blueprints.help_desk.email_ingest import fetch_emails_into_queries

    return fetch_emails_into_queries(flask_app)
