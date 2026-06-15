"""Alembic migration status and upgrade helpers for the admin UI."""

from __future__ import annotations

import io
import logging
import threading
from contextlib import redirect_stdout
from typing import Any

from alembic import command
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util import CommandError
from flask import current_app
from sqlalchemy import inspect

from app import db

logger = logging.getLogger(__name__)

_upgrade_lock = threading.Lock()


def _get_migrate_extension():
    return current_app.extensions['migrate']


def _get_alembic_config():
    migrate_ext = _get_migrate_extension()
    return migrate_ext.migrate.get_config(migrate_ext.directory)


def _get_engine():
    migrate_ext = _get_migrate_extension()
    try:
        return migrate_ext.db.get_engine()
    except (TypeError, AttributeError):
        return migrate_ext.db.engine


def _get_script_directory() -> ScriptDirectory:
    config = _get_alembic_config()
    return ScriptDirectory.from_config(config)


def _get_current_revision() -> str | None:
    engine = _get_engine()
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        return context.get_current_revision()


def _revision_info(revision) -> dict[str, Any]:
    return {
        'revision': revision.revision,
        'down_revision': revision.down_revision,
        'message': revision.doc or '',
        'is_head': revision.is_head,
    }


def _safe_database_label() -> str:
    try:
        url = _get_engine().url
        driver = url.drivername or 'unknown'
        database = url.database or ''
        if driver.startswith('sqlite'):
            return 'sqlite'
        host = url.host or 'localhost'
        port = f':{url.port}' if url.port else ''
        name = database or '(default)'
        return f'{driver} @ {host}{port}/{name}'
    except Exception:
        return 'unknown'


def _table_exists(table_name: str) -> bool:
    try:
        return table_name in inspect(db.engine).get_table_names()
    except Exception:
        return False


def get_status() -> dict[str, Any]:
    """Return current DB revision, heads, and pending migrations."""
    try:
        script = _get_script_directory()
        heads = script.get_heads()
        head_revisions = [_revision_info(script.get_revision(h)) for h in heads]

        if not _table_exists('alembic_version'):
            current = None
            pending = [
                _revision_info(rev)
                for rev in script.walk_revisions(base='base', head='heads')
            ]
            pending.reverse()
        else:
            current = _get_current_revision()
            if current is None:
                pending = [
                    _revision_info(rev)
                    for rev in script.walk_revisions(base='base', head='heads')
                ]
                pending.reverse()
            else:
                pending = []
                for rev in script.iterate_revisions('heads', current):
                    if rev.revision != current:
                        pending.append(_revision_info(rev))
                pending.reverse()

        is_up_to_date = len(pending) == 0 and len(heads) > 0 and (
            current is not None or len(pending) == 0
        )
        if current is None and len(heads) > 0:
            is_up_to_date = False

        return {
            'success': True,
            'current_revision': current,
            'head_revisions': head_revisions,
            'pending_revisions': pending,
            'pending_count': len(pending),
            'is_up_to_date': is_up_to_date and len(pending) == 0,
            'database': _safe_database_label(),
            'web_migrations_enabled': current_app.config.get('ALLOW_WEB_MIGRATIONS', True),
        }
    except Exception as exc:
        logger.exception('Failed to read migration status')
        return {
            'success': False,
            'error': str(exc),
            'is_up_to_date': None,
            'pending_count': None,
        }


def get_history(limit: int = 20) -> dict[str, Any]:
    """Return recent migration revisions from the script directory."""
    try:
        script = _get_script_directory()
        current = _get_current_revision() if _table_exists('alembic_version') else None
        revisions = []
        for rev in script.walk_revisions():
            info = _revision_info(rev)
            info['is_current'] = rev.revision == current
            revisions.append(info)
            if len(revisions) >= limit:
                break
        return {
            'success': True,
            'revisions': revisions,
            'current_revision': current,
        }
    except Exception as exc:
        logger.exception('Failed to read migration history')
        return {
            'success': False,
            'error': str(exc),
            'revisions': [],
        }


def run_upgrade(revision: str = 'head') -> dict[str, Any]:
    """Apply pending migrations up to the given revision."""
    if not current_app.config.get('ALLOW_WEB_MIGRATIONS', True):
        return {
            'success': False,
            'error': 'Web migrations are disabled (ALLOW_WEB_MIGRATIONS=false).',
        }

    if not _upgrade_lock.acquire(blocking=False):
        return {
            'success': False,
            'error': 'Another migration upgrade is already in progress.',
        }

    try:
        before = get_status()
        if before.get('success') and before.get('is_up_to_date'):
            return {
                'success': True,
                'message': 'Database is already up to date.',
                'applied_from': before.get('current_revision'),
                'applied_to': before.get('current_revision'),
                'output': '',
            }

        config = _get_alembic_config()
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            command.upgrade(config, revision)
        output = buffer.getvalue().strip()

        after = get_status()
        return {
            'success': True,
            'message': 'Migrations applied successfully.',
            'applied_from': before.get('current_revision'),
            'applied_to': after.get('current_revision'),
            'pending_count': after.get('pending_count', 0),
            'is_up_to_date': after.get('is_up_to_date', False),
            'output': output,
        }
    except CommandError as exc:
        logger.error('Migration upgrade failed: %s', exc)
        return {
            'success': False,
            'error': str(exc),
        }
    except Exception as exc:
        logger.exception('Migration upgrade failed')
        return {
            'success': False,
            'error': str(exc),
        }
    finally:
        _upgrade_lock.release()
