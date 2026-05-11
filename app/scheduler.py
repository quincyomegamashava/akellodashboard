"""
Background scheduler for helpdesk email fetch.
Runs fetch_emails_and_create_tickets every 60 seconds inside Flask app context.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta

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


def _read_revenue_schedule():
    from app.models import AppSetting

    raw = (AppSetting.get_value('revenue_reports_schedule_time', '06:00') or '06:00').strip()
    try:
        hour_s, minute_s = raw.split(':', 1)
        hour, minute = int(hour_s), int(minute_s)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("out of range")
    except Exception:
        logger.warning("Invalid revenue schedule '%s'. Falling back to 06:00.", raw)
        hour, minute = 6, 0
    return hour, minute


def _scheduled_revenue_report(app):
    with app.app_context():
        try:
            from app.routes import run_revenue_report_job
            as_of = datetime.today() - timedelta(days=1)
            logger.info("Revenue scheduler run starting for as_of=%s", as_of.strftime("%Y-%m-%d"))
            run_revenue_report_job(triggered_by="scheduler", as_of=as_of)
        except Exception as e:
            logger.exception("Revenue reports scheduler job failed: %s", e)


def refresh_revenue_report_schedule(app):
    """Create/update the daily revenue report job from AppSetting time."""
    global _scheduler
    if _scheduler is None:
        return

    hour, minute = _read_revenue_schedule()
    _scheduler.add_job(
        func=_scheduled_revenue_report,
        args=[app],
        trigger="cron",
        hour=hour,
        minute=minute,
        id="revenue_reports_daily_job",
        replace_existing=True,
    )
    logger.info("Revenue report scheduler set to daily %02d:%02d", hour, minute)


def _read_weekly_checkin_schedule():
    from app.models import AppSetting

    raw = (AppSetting.get_value('checkin_reports_schedule_time', '17:00') or '17:00').strip()
    try:
        hour_s, minute_s = raw.split(':', 1)
        hour, minute = int(hour_s), int(minute_s)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("out of range")
    except Exception:
        logger.warning("Invalid weekly check-in schedule '%s'. Falling back to 17:00.", raw)
        hour, minute = 17, 0
    return hour, minute


def _scheduled_weekly_checkin_report(app):
    with app.app_context():
        try:
            from app.routes import run_weekly_checkin_report_job
            logger.info("Weekly check-in scheduler run starting")
            result = run_weekly_checkin_report_job(triggered_by="scheduler")
            logger.info("Weekly check-in scheduler run result: %s", result.get("status"))
        except Exception as e:
            logger.exception("Weekly check-in scheduler job failed: %s", e)


def refresh_weekly_checkin_schedule(app):
    """Create/update the weekly Friday check-in report job from AppSetting time."""
    global _scheduler
    if _scheduler is None:
        return

    hour, minute = _read_weekly_checkin_schedule()
    _scheduler.add_job(
        func=_scheduled_weekly_checkin_report,
        args=[app],
        trigger="cron",
        day_of_week='fri',
        hour=hour,
        minute=minute,
        id="weekly_checkin_reports_job",
        replace_existing=True,
    )
    logger.info("Weekly check-in scheduler set to Fridays %02d:%02d", hour, minute)


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
    with app.app_context():
        refresh_revenue_report_schedule(app)
        refresh_weekly_checkin_schedule(app)
    _scheduler.start()
    logger.info("Helpdesk email scheduler started (interval 60s)")
