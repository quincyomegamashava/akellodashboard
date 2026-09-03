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
    from sqlalchemy.exc import OperationalError

    from app.models import AppSetting

    try:
        raw = (AppSetting.get_value('revenue_reports_schedule_time', '06:00') or '06:00').strip()
    except OperationalError:
        logger.warning(
            "app_settings table missing; using default revenue schedule 06:00. Run flask db upgrade."
        )
        return 6, 0
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
    from sqlalchemy.exc import OperationalError

    from app.models import AppSetting

    try:
        raw = (AppSetting.get_value('checkin_reports_schedule_time', '17:00') or '17:00').strip()
    except OperationalError:
        logger.warning(
            "app_settings table missing; using default check-in schedule 17:00. Run flask db upgrade."
        )
        return 17, 0
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


def _scheduled_weekly_hub_digest(app):
    with app.app_context():
        try:
            from app.email_utils import send_html_email
            from app.models import User
            from app.blueprints.meeting_notes.services import hub_analytics_summary, hub_my_tasks_buckets
            from app.blueprints.sales_marketing.services import stakeholders_stats
            from app.blueprints.sales_marketing.notifications import can_access_sales_marketing_for_user

            users = User.query.filter(User.email.isnot(None)).all()
            for user in users:
                if not (user.email or "").strip():
                    continue
                parts = []
                buckets = hub_my_tasks_buckets(user.id)
                overdue = len(buckets.get("overdue") or [])
                if overdue:
                    parts.append(f"You have {overdue} overdue meeting action item(s).")
                analytics = hub_analytics_summary()
                parts.append(f"Team completion rate: {analytics.get('completion_rate', 0)}%.")
                if can_access_sales_marketing_for_user(user):
                    stats = stakeholders_stats()
                    parts.append(
                        f"Sales: {stats.get('leads_this_week', 0)} leads this week, "
                        f"{stats.get('active_events', 0)} active events."
                    )
                if not parts:
                    continue
                body = "<p>" + "</p><p>".join(parts) + "</p>"
                send_html_email(user.email, "Akello weekly hub digest", body)
        except Exception as e:
            logger.exception("Weekly hub digest failed: %s", e)


def _scheduled_meeting_overdue_notifications(app):
    with app.app_context():
        try:
            from app.blueprints.meeting_notes.notifications import notify_overdue_items

            count = notify_overdue_items()
            if count:
                logger.info("Meeting notes overdue notifications: %d", count)
        except Exception as e:
            logger.exception("Meeting overdue notification job failed: %s", e)


def _read_meeting_report_schedule():
    from sqlalchemy.exc import OperationalError
    from app.models import AppSetting

    try:
        enabled = (AppSetting.get_value("meeting_notes_report_emails_enabled", "false") or "false").strip().lower() in (
            "true",
            "1",
            "yes",
            "y",
            "t",
        )
        cadence = (AppSetting.get_value("meeting_notes_report_emails_cadence", "weekly") or "weekly").strip().lower()
        if cadence not in ("daily", "weekly"):
            cadence = "weekly"
        time_raw = (AppSetting.get_value("meeting_notes_report_emails_time", "08:30") or "08:30").strip()
        recipients_raw = (AppSetting.get_value("meeting_notes_report_emails_recipients", "") or "").strip()
    except OperationalError:
        logger.warning("app_settings table missing; meeting report emails disabled until migrations run.")
        return False, "weekly", 8, 30, ""

    try:
        hh, mm = time_raw.split(":", 1)
        hour = max(0, min(23, int(hh)))
        minute = max(0, min(59, int(mm)))
    except Exception:
        hour, minute = 8, 30
    return enabled, cadence, hour, minute, recipients_raw


def _scheduled_meeting_report_emails(app):
    with app.app_context():
        try:
            from datetime import timedelta

            from app.blueprints.meeting_notes.email_reports import normalize_recipients, send_meeting_report_email
            from app.blueprints.meeting_notes.models import MeetingNote

            enabled, cadence, _, _, recipients_raw = _read_meeting_report_schedule()
            if not enabled:
                return
            recipients = normalize_recipients(recipients_raw)
            if not recipients:
                logger.warning("Meeting report email job skipped: no recipients configured.")
                return

            today = datetime.utcnow().date()
            if cadence == "weekly":
                if datetime.utcnow().weekday() != 0:  # Monday
                    return
                cutoff = today - timedelta(days=7)
            else:
                cutoff = today - timedelta(days=1)

            meetings = (
                MeetingNote.query.filter(MeetingNote.meeting_date >= cutoff)
                .order_by(MeetingNote.meeting_date.desc())
                .limit(50)
                .all()
            )
            total_sent = 0
            for meeting in meetings:
                res = send_meeting_report_email(
                    meeting=meeting,
                    recipients=recipients,
                    subject=f"Scheduled meeting report: {meeting.title}",
                )
                total_sent += int(res.get("sent", 0))
            if meetings:
                logger.info(
                    "Scheduled meeting report emails: meetings=%d sent=%d cadence=%s",
                    len(meetings),
                    total_sent,
                    cadence,
                )
        except Exception as e:
            logger.exception("Meeting report email job failed: %s", e)


def refresh_meeting_report_email_schedule(app):
    global _scheduler
    if _scheduler is None:
        return
    enabled, _, hour, minute, _ = _read_meeting_report_schedule()
    if not enabled:
        try:
            _scheduler.remove_job("meeting_notes_report_email_job")
        except Exception:
            pass
        return
    _scheduler.add_job(
        func=_scheduled_meeting_report_emails,
        args=[app],
        trigger="cron",
        hour=hour,
        minute=minute,
        id="meeting_notes_report_email_job",
        replace_existing=True,
    )
    logger.info("Meeting report email scheduler set to %02d:%02d", hour, minute)


def _read_akello_revenue_digest_schedule():
    from sqlalchemy.exc import OperationalError

    from app.models import AppSetting

    try:
        enabled = (AppSetting.get_value("akello_revenue_digest_enabled", "false") or "false").strip().lower() in (
            "true",
            "1",
            "yes",
            "y",
            "t",
        )
        raw = (AppSetting.get_value("akello_revenue_digest_schedule", "07:00") or "07:00").strip()
    except OperationalError:
        return False, 7, 0
    try:
        hour_s, minute_s = raw.split(":", 1)
        hour, minute = int(hour_s), int(minute_s)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("out of range")
    except Exception:
        logger.warning("Invalid FY digest schedule '%s'. Falling back to 07:00.", raw)
        hour, minute = 7, 0
    return enabled, hour, minute


def _scheduled_akello_revenue_digest(app):
    with app.app_context():
        try:
            from app.blueprints.akello_revenue.services import run_akello_revenue_digest

            result = run_akello_revenue_digest(triggered_by="scheduler")
            logger.info("Akello Revenue FY digest result: %s", result.get("status"))
        except Exception as e:
            logger.exception("Akello Revenue FY digest job failed: %s", e)


def refresh_akello_revenue_digest_schedule(app):
    """Create/update monthly (day 1) Akello Revenue FY digest job."""
    global _scheduler
    if _scheduler is None:
        return
    enabled, hour, minute = _read_akello_revenue_digest_schedule()
    if not enabled:
        try:
            _scheduler.remove_job("akello_revenue_fy_digest_job")
        except Exception:
            pass
        return
    _scheduler.add_job(
        func=_scheduled_akello_revenue_digest,
        args=[app],
        trigger="cron",
        day=1,
        hour=hour,
        minute=minute,
        id="akello_revenue_fy_digest_job",
        replace_existing=True,
    )
    logger.info("Akello Revenue FY digest scheduler set to day 1 at %02d:%02d", hour, minute)


def _scheduled_pm_due_soon(app):
    with app.app_context():
        try:
            from app.pm_service import run_pm_due_soon_job
            n = run_pm_due_soon_job()
            if n:
                logger.info("PM due-soon job: created %d notification(s)", n)
        except Exception as e:
            logger.exception("PM due-soon scheduler job failed: %s", e)


def _scheduled_pm_stats_snapshot(app):
    with app.app_context():
        try:
            from app.pm_service import run_pm_stats_snapshot_job
            n = run_pm_stats_snapshot_job()
            if n:
                logger.info("PM stats snapshot job: captured %d project(s)", n)
        except Exception as e:
            logger.exception("PM stats snapshot scheduler job failed: %s", e)


def _scheduled_helpdesk_sla(app):
    with app.app_context():
        try:
            from app.blueprints.help_desk.services import check_sla_breaches
            n = check_sla_breaches()
            if n:
                logger.info("Helpdesk SLA job: marked %d new breach(es)", n)
        except Exception as e:
            logger.exception("Helpdesk SLA scheduler job failed: %s", e)


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
    _scheduler.add_job(
        func=_scheduled_helpdesk_sla,
        args=[app],
        trigger="interval",
        minutes=5,
        id="helpdesk_sla_check",
        replace_existing=True,
    )
    _scheduler.add_job(
        func=_scheduled_meeting_overdue_notifications,
        args=[app],
        trigger="cron",
        hour=8,
        minute=0,
        id="meeting_notes_overdue_notifications",
    )
    _scheduler.add_job(
        func=_scheduled_weekly_hub_digest,
        args=[app],
        trigger="cron",
        day_of_week="mon",
        hour=8,
        minute=0,
        id="weekly_hub_digest",
    )
    _scheduler.add_job(
        func=_scheduled_pm_due_soon,
        args=[app],
        trigger="cron",
        hour=8,
        minute=0,
        id="pm_due_soon_notifications",
        replace_existing=True,
    )
    _scheduler.add_job(
        func=_scheduled_pm_stats_snapshot,
        args=[app],
        trigger="cron",
        day_of_week="mon",
        hour=7,
        minute=0,
        id="pm_stats_snapshot_weekly",
        replace_existing=True,
    )
    with app.app_context():
        refresh_revenue_report_schedule(app)
        refresh_weekly_checkin_schedule(app)
        refresh_meeting_report_email_schedule(app)
        refresh_akello_revenue_digest_schedule(app)
    _scheduler.start()
    logger.info("Helpdesk email scheduler started (interval 60s)")
