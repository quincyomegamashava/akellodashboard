"""
Background scheduler for helpdesk email fetch.
Runs fetch_emails_and_create_tickets every 60 seconds inside Flask app context.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)
_scheduler = None


def _scheduled_fetch(app):
    """Job that runs in background: fetch emails and create tickets."""
    with app.app_context():
        try:
            from app.email_fetcher import fetch_emails_and_create_tickets
            count, err = fetch_emails_and_create_tickets(app)
            if err:
                logger.warning("Helpdesk email fetch: %s", err)
            elif count > 0:
                logger.info("Helpdesk email fetch: created %d ticket(s)", count)
        except Exception as e:
            logger.exception("Helpdesk scheduler job failed: %s", e)


def start_scheduler(app):
    """
    Start the background scheduler with a 60-second email fetch job.
    Call once at app startup (e.g. from app/__init__.py).
    """
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        func=_scheduled_fetch,
        args=[app],
        trigger="interval",
        seconds=60,
        id="helpdesk_email_fetch",
    )
    _scheduler.start()
    logger.info("Helpdesk email scheduler started (interval 60s)")
