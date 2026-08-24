"""Idempotent schema guards for Help Desk hub columns/tables (SQLite-friendly)."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from app import db

logger = logging.getLogger(__name__)
_ensured = False


def ensure_helpdesk_hub_schema() -> None:
    """Add missing helpdesk columns/tables if migrations have not run yet."""
    global _ensured
    if _ensured:
        return
    try:
        from app.models import HelpDeskTeam, helpdesk_team_members, helpdesk_watchers
        from app.blueprints.help_desk import models as hd_models  # noqa: F401

        tables = [
            HelpDeskTeam.__table__,
            helpdesk_team_members,
            helpdesk_watchers,
            hd_models.HelpDeskMessage.__table__,
            hd_models.HelpDeskAttachment.__table__,
            hd_models.HelpDeskMacro.__table__,
            hd_models.HelpDeskArticle.__table__,
            hd_models.HelpDeskCSAT.__table__,
        ]
        db.metadata.create_all(bind=db.engine, tables=tables)

        inspector = inspect(db.engine)
        if "helpdesk_queries" not in inspector.get_table_names():
            _ensured = True
            return
        columns = {c["name"] for c in inspector.get_columns("helpdesk_queries")}
        alters = []
        if "source" not in columns:
            alters.append("ALTER TABLE helpdesk_queries ADD COLUMN source VARCHAR(20) DEFAULT 'internal' NOT NULL")
        if "priority" not in columns:
            alters.append("ALTER TABLE helpdesk_queries ADD COLUMN priority VARCHAR(20) DEFAULT 'normal' NOT NULL")
        if "category" not in columns:
            alters.append("ALTER TABLE helpdesk_queries ADD COLUMN category VARCHAR(40) DEFAULT 'general' NOT NULL")
        if "requester_email" not in columns:
            alters.append("ALTER TABLE helpdesk_queries ADD COLUMN requester_email VARCHAR(255)")
        if "first_response_at" not in columns:
            alters.append("ALTER TABLE helpdesk_queries ADD COLUMN first_response_at DATETIME")
        if "sla_first_response_due" not in columns:
            alters.append("ALTER TABLE helpdesk_queries ADD COLUMN sla_first_response_due DATETIME")
        if "sla_resolve_due" not in columns:
            alters.append("ALTER TABLE helpdesk_queries ADD COLUMN sla_resolve_due DATETIME")
        if "sla_breached" not in columns:
            alters.append("ALTER TABLE helpdesk_queries ADD COLUMN sla_breached BOOLEAN DEFAULT 0 NOT NULL")
        if "team_id" not in columns:
            alters.append("ALTER TABLE helpdesk_queries ADD COLUMN team_id INTEGER")
        if "message_id" not in columns:
            alters.append("ALTER TABLE helpdesk_queries ADD COLUMN message_id VARCHAR(500)")
        for ddl in alters:
            try:
                db.session.execute(text(ddl))
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.warning("Helpdesk schema alter skipped: %s (%s)", ddl, e)
    except Exception as e:
        logger.warning("Helpdesk schema ensure failed: %s", e)
    finally:
        _ensured = True
