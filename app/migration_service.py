"""Alembic migration status, diagnostics, repair, and upgrade helpers for the admin UI."""

from __future__ import annotations

import ast
import io
import logging
import os
import re
import shutil
import threading
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from typing import Any

from alembic import command
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util import CommandError
from flask import current_app

from app import db
from app.migration_schema import (
    column_exists as schema_column_exists,
    evaluate_operation_preflight,
    parse_migration_schema_operations,
    table_exists as schema_table_exists,
)

logger = logging.getLogger(__name__)

_upgrade_lock = threading.Lock()

# Schema probes tied to recent meeting notes / sales marketing migrations.
_SCHEMA_HINTS = (
    {'check': 'meeting_notes_action_items.priority', 'type': 'column', 'table': 'meeting_notes_action_items', 'column': 'priority'},
    {'check': 'meeting_notes_action_items.source_excerpt', 'type': 'column', 'table': 'meeting_notes_action_items', 'column': 'source_excerpt'},
    {'check': 'meeting_notes_labels table', 'type': 'table', 'name': 'meeting_notes_labels'},
    {'check': 'notifications.meeting_note_id', 'type': 'column', 'table': 'notifications', 'column': 'meeting_note_id'},
    {'check': 'meeting_notes.location', 'type': 'column', 'table': 'meeting_notes', 'column': 'location'},
    {'check': 'meeting_notes_decisions table', 'type': 'table', 'name': 'meeting_notes_decisions'},
    {'check': 'sales_marketing_events.slug', 'type': 'column', 'table': 'sales_marketing_events', 'column': 'slug'},
    {'check': 'sales_marketing_stakeholder_leads table', 'type': 'table', 'name': 'sales_marketing_stakeholder_leads'},
    {'check': 'sales_marketing_stakeholder_leads.follow_up_status', 'type': 'column', 'table': 'sales_marketing_stakeholder_leads', 'column': 'follow_up_status'},
    {'check': 'sales_marketing_stakeholder_leads.duplicate_dismissed', 'type': 'column', 'table': 'sales_marketing_stakeholder_leads', 'column': 'duplicate_dismissed'},
    {'check': 'sales_marketing_stakeholder_lead_notes table', 'type': 'table', 'name': 'sales_marketing_stakeholder_lead_notes'},
    {'check': 'meeting_notes_action_items table', 'type': 'table', 'name': 'meeting_notes_action_items'},
    {'check': 'meeting_notes_action_subtasks table', 'type': 'table', 'name': 'meeting_notes_action_subtasks'},
    {'check': 'meeting_notes_action_subtasks.assignee_user_id', 'type': 'column', 'table': 'meeting_notes_action_subtasks', 'column': 'assignee_user_id'},
)

# Most specific schema signal first — used for stamp inference and recommendations.
_SCHEMA_REVISION_HINTS = (
    ('sales_marketing_events.slug', 't2u3v4w5x6y7', 'Phase 1–3 meeting notes / sales marketing features'),
    ('meeting_notes.location', 'u3v4w5x6y7z8', 'Meeting notes minutes metadata'),
    ('meeting_notes_decisions table', 't2u3v4w5x6y7', 'Meeting notes decisions'),
    ('meeting_notes_labels table', 'p6q7r8s9t0u1', 'Meeting notes planner upgrade'),
    ('meeting_notes_action_items.priority', 'p6q7r8s9t0u1', 'Meeting notes priority column'),
    ('meeting_notes_action_subtasks.assignee_user_id', 'q7r8s9t0u1v2', 'Subtask assignee user id'),
    ('sales_marketing_stakeholder_leads.follow_up_status', 'r8s9t0u1v2w3', 'Sales marketing enhancements (follow-up status)'),
    ('sales_marketing_stakeholder_leads.duplicate_dismissed', 'r8s9t0u1v2w3', 'Sales marketing enhancements (duplicate dismiss)'),
    ('sales_marketing_stakeholder_lead_notes table', 'r8s9t0u1v2w3', 'Sales marketing lead notes'),
    ('sales_marketing_stakeholder_leads table', 'o5p6q7r8s9t0', 'Sales marketing tables'),
    ('meeting_notes_action_subtasks table', 'n4o5p6q7r8s9', 'Meeting notes action subtasks'),
    ('meeting_notes_action_items table', 'f71e8a9b0c1d', 'Meeting notes action items'),
)


def _get_migrate_extension():
    return current_app.extensions['migrate']


def _get_versions_directory() -> Path:
    migrate_ext = _get_migrate_extension()
    return Path(migrate_ext.directory) / 'versions'


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


def _get_bind():
    return _get_engine()


def _table_exists(table_name: str) -> bool:
    try:
        return schema_table_exists(_get_bind(), table_name)
    except Exception:
        return False


def _column_exists(table_name: str, column_name: str) -> bool:
    try:
        return schema_column_exists(_get_bind(), table_name, column_name)
    except Exception:
        return False


def _parse_migration_file(path: Path) -> dict[str, Any] | None:
    """Parse revision metadata from a migration file without loading Alembic's revision map."""
    try:
        source = path.read_text(encoding='utf-8')
    except OSError:
        return None

    revision = None
    down_revision: str | tuple[str, ...] | None = None
    message = ''

    try:
        tree = ast.parse(source)
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if target.id == 'revision':
                    revision = _ast_constant(node.value)
                elif target.id == 'down_revision':
                    down_revision = _ast_constant(node.value)
    except SyntaxError:
        pass

    if revision is None:
        rev_match = re.search(r"^revision\s*=\s*['\"]([^'\"]+)['\"]", source, re.MULTILINE)
        if rev_match:
            revision = rev_match.group(1)

    if down_revision is None:
        down_match = re.search(r"^down_revision\s*=\s*(.+)$", source, re.MULTILINE)
        if down_match:
            down_revision = _parse_down_revision_literal(down_match.group(1).strip())

    doc_match = re.search(r'"""(.*?)"""', source, re.DOTALL)
    if doc_match:
        message = doc_match.group(1).strip().split('\n')[0]

    if not revision:
        return None

    return {
        'file': path.name,
        'path': str(path),
        'revision': revision,
        'down_revision': down_revision,
        'message': message,
    }


def _ast_constant(value) -> Any:
    if isinstance(value, ast.Constant):
        return value.value
    if isinstance(value, (ast.Tuple, ast.List)):
        items = []
        for elt in value.elts:
            if isinstance(elt, ast.Constant):
                items.append(elt.value)
        return tuple(items) if isinstance(value, ast.Tuple) else items
    if isinstance(value, ast.Name) and value.id == 'None':
        return None
    return None


def _parse_down_revision_literal(raw: str) -> str | tuple[str, ...] | None:
    if raw in ('None', 'null'):
        return None
    if raw.startswith('('):
        inner = re.findall(r"['\"]([^'\"]+)['\"]", raw)
        return tuple(inner) if inner else None
    match = re.match(r"^['\"]([^'\"]+)['\"]", raw)
    if match:
        return match.group(1)
    return None


def _normalize_down_revisions(down_revision: str | tuple[str, ...] | list[str] | None) -> list[str]:
    if down_revision is None:
        return []
    if isinstance(down_revision, (tuple, list)):
        return [str(item) for item in down_revision if item]
    return [str(down_revision)]


def scan_migration_files() -> list[dict[str, Any]]:
    versions_dir = _get_versions_directory()
    if not versions_dir.is_dir():
        return []

    files = []
    for path in sorted(versions_dir.glob('*.py')):
        if path.name.startswith('__'):
            continue
        parsed = _parse_migration_file(path)
        if parsed:
            files.append(parsed)
    return files


def _compute_heads(scanned_files: list[dict[str, Any]]) -> list[str]:
    revisions = {item['revision'] for item in scanned_files}
    child_counts: dict[str, int] = {rev: 0 for rev in revisions}
    for item in scanned_files:
        for parent in _normalize_down_revisions(item.get('down_revision')):
            if parent in child_counts:
                child_counts[parent] += 1
    return sorted(rev for rev, count in child_counts.items() if count == 0)


def _find_orphan_files(scanned_files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    revisions = {item['revision'] for item in scanned_files}
    orphans = []
    for item in scanned_files:
        for parent in _normalize_down_revisions(item.get('down_revision')):
            if parent not in revisions:
                orphans.append({
                    'file': item['file'],
                    'path': item['path'],
                    'revision': item['revision'],
                    'missing_parent': parent,
                    'message': item.get('message') or '',
                })
    return orphans


def _build_schema_hints() -> list[dict[str, Any]]:
    hints = []
    for probe in _SCHEMA_HINTS:
        if probe['type'] == 'table':
            exists = _table_exists(probe['name'])
        else:
            exists = _column_exists(probe['table'], probe['column'])
        hints.append({
            'check': probe['check'],
            'exists': exists,
        })
    return hints


def _schema_hint_exists(schema_hints: list[dict[str, Any]], check: str) -> bool:
    for hint in schema_hints:
        if hint.get('check') == check:
            return bool(hint.get('exists'))
    return False


def _infer_stamp_revision(
    schema_hints: list[dict[str, Any]],
    heads: list[str],
    known_revisions: set[str] | None = None,
) -> str | None:
    """Pick a stamp target from schema probes; prefer revisions present on disk."""
    known = known_revisions or set()
    for check, revision, _label in _SCHEMA_REVISION_HINTS:
        if not _schema_hint_exists(schema_hints, check):
            continue
        if known and revision not in known:
            for alt in (revision, '88a51ab2a25e'):
                if alt in known:
                    return alt
            continue
        return revision
    if len(heads) == 1:
        return heads[0]
    if len(heads) > 1:
        return 'head'
    return None


def _build_recommended_stamp_targets(
    scanned_files: list[dict[str, Any]],
    heads: list[str],
    schema_hints: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    known = {item['revision'] for item in scanned_files}
    recommended: list[dict[str, Any]] = []
    inferred = _infer_stamp_revision(schema_hints, heads, known)

    if inferred:
        label = 'Inferred from schema (recommended)'
        for check, revision, desc in _SCHEMA_REVISION_HINTS:
            if revision == inferred or (inferred == '88a51ab2a25e' and revision == 'o5p6q7r8s9t0'):
                if _schema_hint_exists(schema_hints, check):
                    label = f'Inferred from schema: {desc}'
                    break
        recommended.append({
            'revision': inferred,
            'label': label,
            'confidence': 'schema',
        })

    if len(heads) == 1:
        head_rev = heads[0]
        if not any(item['revision'] == head_rev for item in recommended):
            recommended.append({
                'revision': head_rev,
                'label': 'Head (latest deployed migration)',
                'confidence': 'manual',
            })
    elif len(heads) > 1:
        recommended.append({
            'revision': 'head',
            'label': 'Head (after merging branches)',
            'confidence': 'manual',
        })

    for item in scanned_files:
        rev = item['revision']
        if rev in {r['revision'] for r in recommended}:
            continue
        if rev in heads:
            recommended.append({
                'revision': rev,
                'label': item.get('message') or rev,
                'confidence': 'manual',
            })

    return recommended


def _build_suggested_actions(
    analysis: dict[str, Any],
    current: str | None,
    schema_hints: list[dict[str, Any]],
) -> list[str]:
    actions: list[str] = []
    heads = analysis.get('heads') or []
    known = set(analysis.get('known_revisions') or [])
    issues = analysis.get('issues') or []

    if analysis.get('orphan_files'):
        actions.append('remove_orphans')
    if len(heads) > 1:
        actions.append('merge_heads')

    orphaned_db = any(issue.get('code') == 'orphaned_db_revision' for issue in issues)
    inferred = _infer_stamp_revision(schema_hints, heads, known)
    stamp_needed = orphaned_db or current is None
    if not stamp_needed and inferred and current and inferred not in ('head', current):
        if inferred in known and current in known and current != inferred:
            stamp_needed = _schema_hint_exists(schema_hints, _SCHEMA_REVISION_HINTS[0][0]) or any(
                _schema_hint_exists(schema_hints, check) for check, _, _ in _SCHEMA_REVISION_HINTS
            )
        elif current not in known:
            stamp_needed = True

    if stamp_needed:
        actions.append('stamp')
    actions.append('upgrade')
    return actions


def _stamp_needed(
    current: str | None,
    known_revisions: set[str],
    schema_hints: list[dict[str, Any]],
    heads: list[str],
    issues: list[dict[str, Any]],
) -> bool:
    if any(issue.get('code') == 'orphaned_db_revision' for issue in issues):
        return True
    if current is None:
        return True
    if current not in known_revisions:
        return True
    inferred = _infer_stamp_revision(schema_hints, heads, known_revisions)
    if not inferred or inferred in ('head', current):
        return False
    if inferred in known_revisions and current != inferred:
        return any(_schema_hint_exists(schema_hints, check) for check, _, _ in _SCHEMA_REVISION_HINTS)
    return False


def _analyze_chain(scanned_files: list[dict[str, Any]], current: str | None) -> dict[str, Any]:
    revisions = {item['revision'] for item in scanned_files}
    orphan_files = _find_orphan_files(scanned_files)
    heads = _compute_heads(scanned_files)
    issues: list[dict[str, Any]] = []

    if current and current not in revisions:
        issues.append({
            'code': 'orphaned_db_revision',
            'revision': current,
            'message': (
                f'Database revision {current} is not present in deployed migration files.'
            ),
        })

    for orphan in orphan_files:
        issues.append({
            'code': 'missing_parent_file',
            'revision': orphan['revision'],
            'missing_parent': orphan['missing_parent'],
            'file': orphan['file'],
            'message': (
                f"Migration file {orphan['file']} references missing parent "
                f"{orphan['missing_parent']}."
            ),
        })

    if len(heads) > 1:
        issues.append({
            'code': 'multiple_heads',
            'heads': heads,
            'message': f'Multiple migration heads detected: {", ".join(heads)}. Merge required.',
        })

    chain_broken = bool(issues)
    return {
        'issues': issues,
        'orphan_files': orphan_files,
        'heads': heads,
        'chain_broken': chain_broken,
        'known_revisions': sorted(revisions),
    }


def get_diagnostics() -> dict[str, Any]:
    """Return migration chain health, orphan files, and schema hints."""
    try:
        scanned_files = scan_migration_files()
        current = _get_current_revision() if _table_exists('alembic_version') else None
        analysis = _analyze_chain(scanned_files, current)
        heads = analysis['heads']
        schema_hints = _build_schema_hints()

        available_revisions = [
            {
                'revision': item['revision'],
                'message': item.get('message') or '',
                'is_head': item['revision'] in heads,
            }
            for item in scanned_files
        ]
        available_revisions.sort(key=lambda item: item['revision'])

        recommended = _build_recommended_stamp_targets(scanned_files, heads, schema_hints)
        multiple_heads = len(heads) > 1
        has_orphan_files = bool(analysis['orphan_files'])
        suggested_actions = _build_suggested_actions(analysis, current, schema_hints)

        return {
            'success': True,
            'chain_broken': analysis['chain_broken'],
            'issues': analysis['issues'],
            'current_revision': current,
            'head_revisions': heads,
            'orphan_files': analysis['orphan_files'],
            'schema_hints': schema_hints,
            'recommended_stamp_targets': recommended,
            'available_revisions': available_revisions,
            'database': _safe_database_label(),
            'web_migrations_enabled': current_app.config.get('ALLOW_WEB_MIGRATIONS', True),
            'multiple_heads': multiple_heads,
            'has_orphan_files': has_orphan_files,
            'suggested_actions': suggested_actions,
            'inferred_stamp_revision': _infer_stamp_revision(
                schema_hints, heads, set(analysis['known_revisions'])
            ),
        }
    except Exception as exc:
        logger.exception('Failed to read migration diagnostics')
        return {
            'success': False,
            'error': str(exc),
            'chain_broken': None,
            'issues': [],
            'orphan_files': [],
            'schema_hints': [],
            'available_revisions': [],
        }


def _merge_diagnostics_into_status(status: dict[str, Any]) -> dict[str, Any]:
    diagnostics = get_diagnostics()
    if not diagnostics.get('success'):
        if not status.get('success'):
            status['needs_repair'] = True
            status['chain_broken'] = True
            status['error_detail'] = diagnostics.get('error') or status.get('error')
        return status

    chain_broken = diagnostics.get('chain_broken', False)
    status['chain_broken'] = chain_broken
    status['needs_repair'] = chain_broken
    status['multiple_heads'] = diagnostics.get('multiple_heads', False)
    status['has_orphan_files'] = diagnostics.get('has_orphan_files', False)
    status['suggested_actions'] = diagnostics.get('suggested_actions', [])
    status['inferred_stamp_revision'] = diagnostics.get('inferred_stamp_revision')
    if chain_broken:
        status['is_up_to_date'] = False
        messages = [issue.get('message') for issue in diagnostics.get('issues', []) if issue.get('message')]
        status['error_detail'] = ' '.join(messages) if messages else 'Migration chain requires repair.'
        if diagnostics.get('head_revisions'):
            status['head_revisions'] = [
                {'revision': rev, 'message': '', 'is_head': True}
                for rev in diagnostics['head_revisions']
            ]
    return status


def _read_migration_status() -> dict[str, Any]:
    """Return current DB revision, heads, and pending migrations (no health merge)."""
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

        status = {
            'success': True,
            'current_revision': current,
            'head_revisions': head_revisions,
            'pending_revisions': pending,
            'pending_count': len(pending),
            'is_up_to_date': is_up_to_date and len(pending) == 0,
            'database': _safe_database_label(),
            'web_migrations_enabled': current_app.config.get('ALLOW_WEB_MIGRATIONS', True),
            'chain_broken': False,
            'needs_repair': False,
        }
        return _merge_diagnostics_into_status(status)
    except Exception as exc:
        logger.exception('Failed to read migration status')
        current = _get_current_revision() if _table_exists('alembic_version') else None
        status = {
            'success': False,
            'error': str(exc),
            'current_revision': current,
            'is_up_to_date': False,
            'pending_count': 0,
            'pending_revisions': [],
            'database': _safe_database_label(),
            'web_migrations_enabled': current_app.config.get('ALLOW_WEB_MIGRATIONS', True),
            'chain_broken': True,
            'needs_repair': True,
        }
        return _merge_diagnostics_into_status(status)


def get_status() -> dict[str, Any]:
    """Return current DB revision, heads, pending migrations, and health recommendations."""
    status = _read_migration_status()
    diagnostics = get_diagnostics()
    health = get_health_recommendations(
        status=status,
        diagnostics=diagnostics,
        preflight=_preflight_for_health(status),
    )
    status['health'] = health
    status['is_healthy'] = health.get('is_healthy', False)
    status['can_sync'] = health.get('can_sync', False)
    status['can_align_schema'] = health.get('can_align_schema', False)
    status['align_stamp_revision'] = health.get('align_stamp_revision')
    status['can_downgrade'] = health.get('can_downgrade', False)
    return status


def _preflight_for_health(status: dict[str, Any]) -> dict[str, Any] | None:
    if status.get('needs_repair') or status.get('chain_broken'):
        return None
    if (status.get('pending_count') or 0) <= 0:
        return None
    return get_preflight(status=status)


def get_history(limit: int = 20) -> dict[str, Any]:
    """Return recent migration revisions from the script directory or scanned files."""
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
    except Exception:
        logger.warning('Alembic history unavailable; falling back to scanned migration files')
        try:
            scanned_files = scan_migration_files()
            current = _get_current_revision() if _table_exists('alembic_version') else None
            heads = _compute_heads(scanned_files)
            revisions = []
            for item in scanned_files[:limit]:
                revisions.append({
                    'revision': item['revision'],
                    'down_revision': item.get('down_revision'),
                    'message': item.get('message') or '',
                    'is_head': item['revision'] in heads,
                    'is_current': item['revision'] == current,
                })
            return {
                'success': True,
                'revisions': revisions,
                'current_revision': current,
                'fallback': True,
            }
        except Exception as exc:
            logger.exception('Failed to read migration history')
            return {
                'success': False,
                'error': str(exc),
                'revisions': [],
            }


def _sqlite_db_path() -> str | None:
    url = _get_engine().url
    if not url.drivername.startswith('sqlite'):
        return None
    database = url.database
    if not database or database == ':memory:':
        return None
    if database.startswith('/'):
        return database
    return os.path.abspath(database)


def _backup_sqlite_database() -> dict[str, Any]:
    db_path = _sqlite_db_path()
    if not db_path or not os.path.isfile(db_path):
        return {
            'success': False,
            'error': 'Automatic backup is only supported for on-disk SQLite databases.',
        }

    basedir = Path(current_app.root_path).parent
    backup_dir = basedir / 'backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    backup_path = backup_dir / f'app.db.repair.{timestamp}'
    shutil.copy2(db_path, backup_path)
    return {
        'success': True,
        'backup_path': str(backup_path),
    }


def backup_app_database() -> dict[str, Any]:
    """Public wrapper for SQLite backup before schema-studio DDL."""
    return _backup_sqlite_database()


def _check_web_migrations_enabled() -> dict[str, Any] | None:
    if not current_app.config.get('ALLOW_WEB_MIGRATIONS', True):
        return {
            'success': False,
            'error': 'Web migrations are disabled (ALLOW_WEB_MIGRATIONS=false).',
        }
    return None


def _remove_orphan_files(orphan_files: list[dict[str, Any]]) -> list[str]:
    removed_files: list[str] = []
    for orphan in orphan_files:
        file_path = orphan.get('path')
        if file_path and os.path.isfile(file_path):
            os.remove(file_path)
            removed_files.append(orphan.get('file') or file_path)
    return removed_files


def _merge_heads_internal(
    heads: list[str],
    message: str | None = None,
) -> dict[str, Any]:
    config = _get_alembic_config()
    buffer = io.StringIO()
    merge_message = message or 'Merge migration heads (admin)'
    with redirect_stdout(buffer):
        script = command.merge(config, tuple(heads), message=merge_message)

    new_revision = script.revision if script else None
    new_file = None
    if script is not None:
        script_path = getattr(script, 'path', None)
        if script_path:
            new_file = {
                'path': str(script_path),
                'filename': Path(script_path).name,
            }

    after = get_diagnostics()
    return {
        'merged_heads': heads,
        'new_revision': new_revision,
        'new_file': new_file,
        'output': buffer.getvalue().strip(),
        'head_revisions_after': after.get('head_revisions') or [],
    }


def _stamp_revision(stamp_revision: str, stamped_from: str | None) -> dict[str, Any]:
    config = _get_alembic_config()
    diagnostics = get_diagnostics()
    heads = diagnostics.get('head_revisions') or []
    known_revisions = {item['revision'] for item in diagnostics.get('available_revisions', [])}

    if stamp_revision == 'head':
        if not heads:
            raise CommandError('No migration head found to stamp.')
        if len(heads) > 1:
            raise CommandError(
                'Multiple heads remain; merge heads before stamping to head.'
            )
        stamp_revision = heads[0]

    if stamp_revision not in known_revisions:
        raise CommandError(f'Unknown stamp revision: {stamp_revision}')

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        command.stamp(config, stamp_revision)
    return {
        'from': stamped_from,
        'to': stamp_revision,
        'output': buffer.getvalue().strip(),
    }


def _upgrade_to_head() -> dict[str, Any]:
    config = _get_alembic_config()
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        command.upgrade(config, 'head')
    upgrade_output = buffer.getvalue().strip()
    upgrade_result = get_status()
    return {
        'output': upgrade_output,
        'pending_count': upgrade_result.get('pending_count', 0),
        'is_up_to_date': upgrade_result.get('is_up_to_date', False),
        'current_revision': upgrade_result.get('current_revision'),
    }


def run_merge_heads(message: str | None = None) -> dict[str, Any]:
    """Merge multiple migration heads into a single revision (creates a merge file)."""
    disabled = _check_web_migrations_enabled()
    if disabled:
        return disabled

    if not _upgrade_lock.acquire(blocking=False):
        return {
            'success': False,
            'error': 'Another migration operation is already in progress.',
        }

    steps: list[dict[str, Any]] = []
    try:
        before = get_diagnostics()
        if not before.get('success'):
            return {
                'success': False,
                'error': before.get('error', 'Could not read migration diagnostics.'),
            }

        if before.get('has_orphan_files'):
            orphan_names = [o.get('file') for o in before.get('orphan_files', [])]
            return {
                'success': False,
                'error': (
                    'Orphan migration files must be removed before merging heads. '
                    'Use Fix migrations or remove orphans first: '
                    + ', '.join(name for name in orphan_names if name)
                ),
            }

        heads = before.get('head_revisions') or []
        if len(heads) <= 1:
            return {
                'success': False,
                'error': (
                    'Multiple heads are not present; merge is not required.'
                    if len(heads) == 1
                    else 'No migration heads found.'
                ),
            }

        backup_result = _backup_sqlite_database()
        if not backup_result.get('success'):
            return backup_result
        steps.append({'step': 'backup', 'success': True, 'detail': backup_result.get('backup_path')})

        merge_result = _merge_heads_internal(heads, message=message)
        steps.append({'step': 'merge_heads', 'success': True, 'detail': merge_result})

        after = get_diagnostics()
        return {
            'success': True,
            'message': 'Migration heads merged successfully.',
            'steps': steps,
            'backup_path': backup_result.get('backup_path'),
            'merged_heads': merge_result.get('merged_heads'),
            'new_revision': merge_result.get('new_revision'),
            'new_file': merge_result.get('new_file'),
            'head_revisions_after': after.get('head_revisions') or [],
            'chain_broken': after.get('chain_broken', False),
            'multiple_heads': after.get('multiple_heads', False),
            'output': merge_result.get('output', ''),
            'git_commit_reminder': (
                'Commit the new merge migration file to git so future deploys keep a consistent chain.'
            ),
        }
    except CommandError as exc:
        logger.error('Migration merge failed: %s', exc)
        return {
            'success': False,
            'error': str(exc),
            'steps': steps,
        }
    except Exception as exc:
        logger.exception('Migration merge failed')
        return {
            'success': False,
            'error': str(exc),
            'steps': steps,
        }
    finally:
        _upgrade_lock.release()


def run_fix_migrations(
    stamp_revision: str | None = None,
    *,
    remove_orphan_files: bool = True,
    merge_heads: bool = True,
    run_stamp: bool = True,
    run_upgrade_after: bool = True,
) -> dict[str, Any]:
    """One-click recovery: backup, remove orphans, merge heads, stamp, upgrade."""
    disabled = _check_web_migrations_enabled()
    if disabled:
        return disabled

    if not _upgrade_lock.acquire(blocking=False):
        return {
            'success': False,
            'error': 'Another migration operation is already in progress.',
        }

    steps: list[dict[str, Any]] = []
    try:
        before = get_diagnostics()
        if not before.get('success'):
            return {
                'success': False,
                'error': before.get('error', 'Could not read migration diagnostics.'),
            }

        backup_result = _backup_sqlite_database()
        if not backup_result.get('success'):
            return backup_result
        steps.append({'step': 'backup', 'success': True, 'detail': backup_result.get('backup_path')})

        removed_files: list[str] = []
        if remove_orphan_files and before.get('orphan_files'):
            removed_files = _remove_orphan_files(before.get('orphan_files', []))
            steps.append({'step': 'remove_orphan_files', 'success': True, 'detail': removed_files})

        diagnostics = get_diagnostics()
        heads = diagnostics.get('head_revisions') or []
        if merge_heads and len(heads) > 1:
            merge_result = _merge_heads_internal(heads)
            steps.append({'step': 'merge_heads', 'success': True, 'detail': merge_result})
            diagnostics = get_diagnostics()
            heads = diagnostics.get('head_revisions') or []

        stamped_from = diagnostics.get('current_revision')
        known_revisions = {item['revision'] for item in diagnostics.get('available_revisions', [])}
        schema_hints = diagnostics.get('schema_hints') or []
        issues = diagnostics.get('issues') or []

        stamp_target = stamp_revision
        if run_stamp and _stamp_needed(stamped_from, known_revisions, schema_hints, heads, issues):
            if not stamp_target:
                stamp_target = diagnostics.get('inferred_stamp_revision') or (
                    heads[0] if len(heads) == 1 else 'head'
                )
            stamp_detail = _stamp_revision(stamp_target, stamped_from)
            steps.append({'step': 'stamp', 'success': True, 'detail': stamp_detail})
            stamped_from = stamp_detail.get('to', stamp_target)
        elif run_stamp:
            steps.append({
                'step': 'stamp',
                'success': True,
                'detail': {'skipped': True, 'reason': 'Stamp not required.'},
            })

        upgrade_output = ''
        if run_upgrade_after:
            upgrade_detail = _upgrade_to_head()
            upgrade_output = upgrade_detail.get('output', '')
            steps.append({'step': 'upgrade', 'success': True, 'detail': upgrade_detail})

        after = get_status()
        merge_step = next((s for s in steps if s.get('step') == 'merge_heads'), None)
        merge_detail = (merge_step or {}).get('detail') or {}
        return {
            'success': True,
            'message': 'Migrations fixed successfully.',
            'steps': steps,
            'removed_files': removed_files,
            'backup_path': backup_result.get('backup_path'),
            'stamped_from': diagnostics.get('current_revision'),
            'stamped_to': after.get('current_revision'),
            'new_revision': merge_detail.get('new_revision'),
            'new_file': merge_detail.get('new_file'),
            'upgrade_output': upgrade_output,
            'pending_count': after.get('pending_count', 0),
            'is_up_to_date': after.get('is_up_to_date', False),
            'chain_broken': after.get('chain_broken', False),
            'git_commit_reminder': (
                'Commit any new merge migration file to git so future deploys keep a consistent chain.'
                if merge_detail.get('new_file')
                else None
            ),
        }
    except CommandError as exc:
        logger.error('Migration fix failed: %s', exc)
        return {
            'success': False,
            'error': str(exc),
            'steps': steps,
        }
    except Exception as exc:
        logger.exception('Migration fix failed')
        return {
            'success': False,
            'error': str(exc),
            'steps': steps,
        }
    finally:
        _upgrade_lock.release()


def run_repair(
    stamp_revision: str,
    *,
    remove_orphan_files: bool = True,
    run_upgrade_after: bool = True,
    auto_merge_heads: bool = False,
) -> dict[str, Any]:
    """Repair a broken migration chain: backup, cleanup, stamp, optional upgrade."""
    disabled = _check_web_migrations_enabled()
    if disabled:
        return disabled

    if not _upgrade_lock.acquire(blocking=False):
        return {
            'success': False,
            'error': 'Another migration operation is already in progress.',
        }

    steps: list[dict[str, Any]] = []
    try:
        before = get_diagnostics()
        if not before.get('success'):
            return {
                'success': False,
                'error': before.get('error', 'Could not read migration diagnostics.'),
            }

        if not before.get('chain_broken'):
            return {
                'success': False,
                'error': 'Migration chain is not broken; repair is not required.',
            }

        heads = before.get('head_revisions') or []

        backup_result = _backup_sqlite_database()
        if not backup_result.get('success'):
            return backup_result
        steps.append({'step': 'backup', 'success': True, 'detail': backup_result.get('backup_path')})

        removed_files: list[str] = []
        if remove_orphan_files and before.get('orphan_files'):
            removed_files = _remove_orphan_files(before.get('orphan_files', []))
            steps.append({'step': 'remove_orphan_files', 'success': True, 'detail': removed_files})
            before = get_diagnostics()
            heads = before.get('head_revisions') or []

        if len(heads) > 1:
            if not auto_merge_heads:
                return {
                    'success': False,
                    'error': (
                        'Multiple migration heads detected. Merge heads before running repair: '
                        + ', '.join(heads)
                    ),
                    'steps': steps,
                }
            merge_result = _merge_heads_internal(heads)
            steps.append({'step': 'merge_heads', 'success': True, 'detail': merge_result})
            before = get_diagnostics()
            heads = before.get('head_revisions') or []

        known_revisions = {item['revision'] for item in before.get('available_revisions', [])}
        if stamp_revision == 'head':
            if not heads:
                return {'success': False, 'error': 'No migration head found to stamp.'}
            stamp_revision = heads[0]

        if stamp_revision not in known_revisions:
            return {
                'success': False,
                'error': f'Unknown stamp revision: {stamp_revision}',
                'steps': steps,
            }

        stamped_from = before.get('current_revision')
        stamp_detail = _stamp_revision(stamp_revision, stamped_from)
        steps.append({'step': 'stamp', 'success': True, 'detail': stamp_detail})

        upgrade_output = ''
        if run_upgrade_after:
            upgrade_detail = _upgrade_to_head()
            upgrade_output = upgrade_detail.get('output', '')
            steps.append({'step': 'upgrade', 'success': True, 'detail': upgrade_detail})

        after = get_status()
        return {
            'success': True,
            'message': 'Migration chain repaired successfully.',
            'steps': steps,
            'removed_files': removed_files,
            'backup_path': backup_result.get('backup_path'),
            'stamped_from': stamped_from,
            'stamped_to': after.get('current_revision') or stamp_revision,
            'upgrade_output': upgrade_output,
            'pending_count': after.get('pending_count', 0),
            'is_up_to_date': after.get('is_up_to_date', False),
            'chain_broken': after.get('chain_broken', False),
        }
    except CommandError as exc:
        logger.error('Migration repair failed: %s', exc)
        return {
            'success': False,
            'error': str(exc),
            'steps': steps,
        }
    except Exception as exc:
        logger.exception('Migration repair failed')
        return {
            'success': False,
            'error': str(exc),
            'steps': steps,
        }
    finally:
        _upgrade_lock.release()


def get_next_pending_revision() -> str | None:
    """Return the next pending migration revision, or None if up to date."""
    status = get_status()
    pending = status.get('pending_revisions') or []
    if not pending:
        return None
    return pending[0].get('revision')


def _resolve_upgrade_target(
    revision: str | None = None,
    mode: str = 'all',
) -> tuple[str | None, dict[str, Any] | None]:
    """Resolve Alembic upgrade target revision; return (target, error_payload)."""
    before = get_status()
    if before.get('needs_repair'):
        return None, {
            'success': False,
            'error': before.get('error_detail') or 'Migration chain is broken. Run repair first.',
        }

    pending = before.get('pending_revisions') or []
    if before.get('success') and before.get('is_up_to_date'):
        return None, {
            'success': True,
            'message': 'Database is already up to date.',
            'applied_from': before.get('current_revision'),
            'applied_to': before.get('current_revision'),
            'output': '',
            'mode': mode,
        }

    if mode == 'next':
        if not pending:
            return None, {
                'success': True,
                'message': 'Database is already up to date.',
                'applied_from': before.get('current_revision'),
                'applied_to': before.get('current_revision'),
                'output': '',
                'mode': mode,
            }
        return pending[0]['revision'], None

    target = (revision or 'head').strip() or 'head'
    if target != 'head':
        pending_ids = {item['revision'] for item in pending}
        if target not in pending_ids:
            return None, {
                'success': False,
                'error': (
                    f'Revision {target} is not in the pending migration list. '
                    f'Pending: {", ".join(sorted(pending_ids)) or "(none)"}.'
                ),
            }
    return target, None


def _parse_failed_revision(output: str, pending: list[dict[str, Any]]) -> str | None:
    """Infer which migration failed from Alembic stdout/stderr text."""
    if not output:
        return pending[0]['revision'] if pending else None

    running = re.findall(
        r'Running upgrade\s+([^\s]+)\s+->\s+([^\s,]+)',
        output,
        flags=re.IGNORECASE,
    )
    if running:
        return running[-1][1]

    for item in pending:
        if item.get('revision') and item['revision'] in output:
            return item['revision']
    return pending[0]['revision'] if pending else None


def get_preflight(status: dict[str, Any] | None = None) -> dict[str, Any]:
    """Static + live schema checks for each pending migration."""
    try:
        if status is None:
            status = _read_migration_status()
        if not status.get('success'):
            return {
                'success': False,
                'error': status.get('error') or 'Could not read migration status.',
            }

        pending = status.get('pending_revisions') or []
        if not pending:
            return {
                'success': True,
                'ready': True,
                'pending_count': 0,
                'next_revision': None,
                'findings': [],
                'blockers': [],
                'warnings': [],
                'info': [],
                'message': 'No pending migrations.',
            }

        versions_dir = _get_versions_directory()
        bind = _get_bind()
        findings: list[dict[str, Any]] = []
        revision_files = {item['revision']: item for item in scan_migration_files()}

        for item in pending:
            revision = item['revision']
            file_meta = revision_files.get(revision)
            if not file_meta:
                findings.append({
                    'revision': revision,
                    'severity': 'blocker',
                    'code': 'missing_migration_file',
                    'message': f'Migration file for revision {revision} is not on disk.',
                })
                continue

            path = Path(file_meta['path'])
            try:
                source = path.read_text(encoding='utf-8')
            except OSError as exc:
                findings.append({
                    'revision': revision,
                    'severity': 'blocker',
                    'code': 'unreadable_migration_file',
                    'message': f'Could not read {path.name}: {exc}',
                })
                continue

            operations = parse_migration_schema_operations(source)
            if not operations:
                findings.append({
                    'revision': revision,
                    'severity': 'warning',
                    'code': 'unparsed_operations',
                    'message': (
                        f'Could not statically parse operations in {path.name}; '
                        'upgrade may still succeed.'
                    ),
                })
                continue

            for operation in operations:
                finding = evaluate_operation_preflight(bind, source, revision, operation)
                if finding:
                    findings.append(finding)

        blockers = [f for f in findings if f.get('severity') == 'blocker']
        warnings = [f for f in findings if f.get('severity') == 'warning']
        info = [f for f in findings if f.get('severity') == 'info']
        next_revision = pending[0]['revision']

        return {
            'success': True,
            'ready': len(blockers) == 0,
            'pending_count': len(pending),
            'next_revision': next_revision,
            'findings': findings,
            'blockers': blockers,
            'warnings': warnings,
            'info': info,
            'can_sync': _can_sync_pending(pending, blockers, warnings, info),
            'message': (
                'Ready to apply migrations.'
                if not blockers
                else f'{len(blockers)} blocker(s) found. Resolve before upgrading.'
            ),
        }
    except Exception as exc:
        logger.exception('Migration preflight failed')
        return {
            'success': False,
            'error': str(exc),
        }


def _missing_schema_hints(schema_hints: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    hints = schema_hints if schema_hints is not None else _build_schema_hints()
    return [hint for hint in hints if not hint.get('exists')]


def _infer_actual_schema_revision(schema_hints: list[dict[str, Any]] | None = None) -> str | None:
    """Best-effort revision inferred from present schema objects (not alembic_version)."""
    hints = schema_hints if schema_hints is not None else _build_schema_hints()
    for check, revision, _label in _SCHEMA_REVISION_HINTS:
        if _schema_hint_exists(hints, check):
            return revision
    return None


def _can_sync_pending(
    pending: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    info: list[dict[str, Any]],
) -> bool:
    """True when pending migrations appear already applied (preflight is info-only)."""
    if not pending or blockers:
        return False
    if warnings:
        return False
    if not info:
        return False
    idempotent_codes = {
        'table_exists_idempotent',
        'column_exists_idempotent',
        'index_exists',
        'fk_exists',
    }
    return all(item.get('code') in idempotent_codes for item in info)


def get_health_recommendations(
    status: dict[str, Any] | None = None,
    diagnostics: dict[str, Any] | None = None,
    preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze migration + schema alignment and return actionable recommendations."""
    if status is None:
        status = _read_migration_status()
    if diagnostics is None:
        diagnostics = get_diagnostics()
    if preflight is None and status.get('pending_count', 0) > 0 and not status.get('needs_repair'):
        preflight = get_preflight(status=status)

    schema_hints = diagnostics.get('schema_hints') or _build_schema_hints()
    missing = _missing_schema_hints(schema_hints)
    inferred_schema = _infer_actual_schema_revision(schema_hints)
    current = status.get('current_revision')
    heads = [h.get('revision') if isinstance(h, dict) else h for h in (status.get('head_revisions') or [])]
    head = heads[0] if len(heads) == 1 else None
    pending_count = status.get('pending_count') or 0
    chain_broken = bool(status.get('chain_broken') or status.get('needs_repair'))
    recommendations: list[dict[str, Any]] = []

    if chain_broken:
        recommendations.append({
            'severity': 'error',
            'code': 'chain_broken',
            'title': 'Repair the migration chain',
            'message': status.get('error_detail') or 'Migration files and database revision are out of sync.',
            'action': 'fix_migrations',
        })

    if missing:
        missing_list = ', '.join(item['check'] for item in missing[:5])
        if len(missing) > 5:
            missing_list += f' (+{len(missing) - 5} more)'
        if status.get('is_up_to_date') and current:
            if pending_count == 0 and inferred_schema and inferred_schema != current:
                recommendations.append({
                    'severity': 'error',
                    'code': 'schema_behind_revision',
                    'title': 'Align schema & re-apply migrations',
                    'message': (
                        f'alembic_version is {current} but required schema is missing: {missing_list}. '
                        f'Use Align schema to stamp to {inferred_schema}, then re-run migrations to head.'
                    ),
                    'action': 'align_schema',
                    'target_revision': inferred_schema,
                })
            else:
                recommendations.append({
                    'severity': 'error',
                    'code': 'schema_behind_revision',
                    'title': 'Database revision is ahead of schema',
                    'message': (
                        f'alembic_version is {current} but required schema is missing: {missing_list}. '
                        'Apply pending migrations or use Align schema if none are pending.'
                    ),
                    'action': 'apply_migrations',
                })
                if inferred_schema and inferred_schema != current and pending_count == 0:
                    recommendations.append({
                        'severity': 'warning',
                        'code': 'stamp_to_match_schema',
                        'title': 'Align revision to match schema',
                        'message': (
                            f'Schema objects suggest revision {inferred_schema} '
                            f'but alembic_version is {current}.'
                        ),
                        'action': 'align_schema',
                        'target_revision': inferred_schema,
                    })
        else:
            recommendations.append({
                'severity': 'warning',
                'code': 'schema_incomplete',
                'title': 'Schema is incomplete',
                'message': f'Missing: {missing_list}. Apply pending migrations to add them.',
                'action': 'apply_migrations',
            })

    if pending_count > 0 and not chain_broken:
        can_sync = bool(preflight and preflight.get('can_sync'))
        if preflight and not preflight.get('ready'):
            blocker_msgs = [
                item.get('message', '')
                for item in (preflight.get('blockers') or [])[:3]
            ]
            recommendations.append({
                'severity': 'error',
                'code': 'preflight_blockers',
                'title': 'Resolve preflight blockers before upgrading',
                'message': '; '.join(msg for msg in blocker_msgs if msg) or 'Preflight found blocking issues.',
                'action': 'run_preflight',
            })
        elif can_sync:
            sync_target = head or (status.get('pending_revisions') or [{}])[-1].get('revision')
            recommendations.append({
                'severity': 'info',
                'code': 'sync_available',
                'title': 'Sync revision without re-running DDL',
                'message': (
                    'Preflight shows pending migrations would only skip existing schema. '
                    'Use Sync revision to update alembic_version safely.'
                ),
                'action': 'sync_revision',
                'target_revision': sync_target,
            })
        else:
            next_rev = (status.get('pending_revisions') or [{}])[0].get('revision')
            recommendations.append({
                'severity': 'info',
                'code': 'pending_migrations',
                'title': 'Apply pending migrations',
                'message': (
                    f'{pending_count} migration(s) pending'
                    + (f' (next: {next_rev})' if next_rev else '')
                    + '. Run preflight, then apply next or all.'
                ),
                'action': 'apply_migrations',
            })

    can_downgrade = bool(current) and not chain_broken
    down_revision = None
    if can_downgrade:
        try:
            script = _get_script_directory()
            rev = script.get_revision(current)
            parent = rev.down_revision
            if isinstance(parent, tuple):
                down_revision = parent[0] if parent else None
            else:
                down_revision = parent
            can_downgrade = down_revision is not None
        except Exception:
            can_downgrade = False

    if can_downgrade and missing and status.get('is_up_to_date'):
        recommendations.append({
            'severity': 'warning',
            'code': 'rollback_option',
            'title': 'Rollback one revision (advanced)',
            'message': (
                f'If schema was stamped incorrectly, roll back to {down_revision} '
                'then re-apply migrations. A database backup is created automatically.'
            ),
            'action': 'downgrade_one',
            'target_revision': down_revision,
        })

    is_healthy = (
        not chain_broken
        and not missing
        and pending_count == 0
        and status.get('success', True)
    )

    can_align = _can_align_schema(
        status=status,
        missing=missing,
        inferred_schema=inferred_schema,
        chain_broken=chain_broken,
        pending_count=pending_count,
        heads=heads,
    )

    return {
        'is_healthy': is_healthy,
        'missing_schema': missing,
        'inferred_schema_revision': inferred_schema,
        'align_stamp_revision': inferred_schema if can_align else None,
        'can_sync': bool(preflight and preflight.get('can_sync')) if pending_count else False,
        'can_align_schema': can_align,
        'can_downgrade': can_downgrade,
        'down_revision': down_revision,
        'recommendations': recommendations,
    }


def _can_align_schema(
    *,
    status: dict[str, Any],
    missing: list[dict[str, Any]],
    inferred_schema: str | None,
    chain_broken: bool,
    pending_count: int,
    heads: list[str],
) -> bool:
    """True when revision is at head but live schema is behind (re-stamp + upgrade helps)."""
    if chain_broken or not missing:
        return False
    if pending_count > 0:
        return False
    current = status.get('current_revision')
    if not current:
        return False
    if len(heads) != 1:
        return False
    if not inferred_schema or inferred_schema == current:
        return False
    return True


def run_align_schema(stamp_revision: str | None = None) -> dict[str, Any]:
    """Stamp to schema-inferred revision, then upgrade to head (fixes stamp-without-DDL drift)."""
    disabled = _check_web_migrations_enabled()
    if disabled:
        return disabled

    if not _upgrade_lock.acquire(blocking=False):
        return {
            'success': False,
            'error': 'Another migration operation is already in progress.',
        }

    steps: list[dict[str, Any]] = []
    try:
        before = _read_migration_status()
        if before.get('needs_repair') or before.get('chain_broken'):
            return {
                'success': False,
                'error': before.get('error_detail') or 'Migration chain is broken. Repair first.',
            }

        diagnostics = get_diagnostics()
        health = get_health_recommendations(status=before, diagnostics=diagnostics)
        missing = health.get('missing_schema') or []
        if not missing:
            return {
                'success': False,
                'error': 'Schema alignment is not needed; no missing schema objects were detected.',
            }

        if (before.get('pending_count') or 0) > 0:
            return {
                'success': False,
                'error': (
                    'Pending migrations are already queued. Run Apply all migrations instead of align.'
                ),
            }

        heads = [
            h.get('revision') if isinstance(h, dict) else h
            for h in (before.get('head_revisions') or [])
        ]
        if len(heads) != 1:
            return {
                'success': False,
                'error': 'Multiple migration heads detected. Merge heads before aligning schema.',
            }

        stamp_target = (stamp_revision or '').strip() or health.get('align_stamp_revision')
        if not stamp_target:
            return {
                'success': False,
                'error': (
                    'Could not infer a stamp target from schema probes. '
                    'Choose an earlier revision in Repair stamp target, then try again.'
                ),
            }

        known = {item['revision'] for item in diagnostics.get('available_revisions', [])}
        if stamp_target not in known:
            return {
                'success': False,
                'error': f'Unknown stamp revision: {stamp_target}',
            }

        current = before.get('current_revision')
        if stamp_target == current:
            return {
                'success': False,
                'error': (
                    f'Stamp target {stamp_target} matches current revision but schema is still incomplete. '
                    'Pick an earlier revision that matches the database schema.'
                ),
            }

        backup_result = _backup_sqlite_database()
        if not backup_result.get('success'):
            return backup_result
        steps.append({'step': 'backup', 'success': True, 'detail': backup_result.get('backup_path')})

        stamp_detail = _stamp_revision(stamp_target, current)
        steps.append({'step': 'stamp', 'success': True, 'detail': stamp_detail})

        upgrade_detail = _upgrade_to_head()
        steps.append({'step': 'upgrade', 'success': True, 'detail': upgrade_detail})

        after = get_status()
        still_missing = (after.get('health') or {}).get('missing_schema') or []
        message = 'Schema aligned and migrations re-applied successfully.'
        if still_missing:
            message += f' Warning: {len(still_missing)} schema probe(s) still missing.'

        return {
            'success': True,
            'message': message,
            'steps': steps,
            'backup_path': backup_result.get('backup_path'),
            'stamped_from': current,
            'stamped_to': stamp_target,
            'current_revision': after.get('current_revision'),
            'pending_count': after.get('pending_count', 0),
            'is_up_to_date': after.get('is_up_to_date', False),
            'is_healthy': after.get('is_healthy', False),
            'missing_schema_after': still_missing,
            'upgrade_output': upgrade_detail.get('output', ''),
        }
    except CommandError as exc:
        logger.error('Schema align failed: %s', exc)
        return {'success': False, 'error': str(exc), 'steps': steps}
    except Exception as exc:
        logger.exception('Schema align failed')
        return {'success': False, 'error': str(exc), 'steps': steps}
    finally:
        _upgrade_lock.release()


def run_sync_revision(revision: str | None = None) -> dict[str, Any]:
    """Stamp to target when schema already matches pending migrations (no DDL)."""
    disabled = _check_web_migrations_enabled()
    if disabled:
        return disabled

    if not _upgrade_lock.acquire(blocking=False):
        return {
            'success': False,
            'error': 'Another migration operation is already in progress.',
        }

    steps: list[dict[str, Any]] = []
    try:
        before = get_status()
        if before.get('needs_repair') or before.get('chain_broken'):
            return {
                'success': False,
                'error': before.get('error_detail') or 'Migration chain is broken. Repair first.',
            }

        preflight = get_preflight()
        if not preflight.get('success'):
            return {
                'success': False,
                'error': preflight.get('error') or 'Could not run preflight.',
            }
        if not preflight.get('can_sync'):
            return {
                'success': False,
                'error': (
                    'Sync is not available: preflight must show only idempotent skips '
                    '(no blockers or warnings). Try Apply migrations instead.'
                ),
            }

        heads = [h.get('revision') for h in (before.get('head_revisions') or [])]
        target = revision or (heads[0] if len(heads) == 1 else 'head')
        if not target:
            return {'success': False, 'error': 'No sync target revision found.'}

        backup_result = _backup_sqlite_database()
        if not backup_result.get('success'):
            return backup_result
        steps.append({'step': 'backup', 'success': True, 'detail': backup_result.get('backup_path')})

        stamped_from = before.get('current_revision')
        stamp_detail = _stamp_revision(target, stamped_from)
        steps.append({'step': 'sync_stamp', 'success': True, 'detail': stamp_detail})

        after = get_status()
        return {
            'success': True,
            'message': 'Revision synced without re-running DDL.',
            'steps': steps,
            'backup_path': backup_result.get('backup_path'),
            'stamped_from': stamped_from,
            'stamped_to': after.get('current_revision'),
            'pending_count': after.get('pending_count', 0),
            'is_up_to_date': after.get('is_up_to_date', False),
            'output': stamp_detail.get('output', ''),
        }
    except CommandError as exc:
        logger.error('Migration sync failed: %s', exc)
        return {'success': False, 'error': str(exc), 'steps': steps}
    except Exception as exc:
        logger.exception('Migration sync failed')
        return {'success': False, 'error': str(exc), 'steps': steps}
    finally:
        _upgrade_lock.release()


def run_downgrade(
    revision: str | None = None,
    mode: str = 'one',
) -> dict[str, Any]:
    """Roll back migrations (one step or to a specific revision)."""
    disabled = _check_web_migrations_enabled()
    if disabled:
        return disabled

    if not _upgrade_lock.acquire(blocking=False):
        return {
            'success': False,
            'error': 'Another migration operation is already in progress.',
        }

    buffer = io.StringIO()
    steps: list[dict[str, Any]] = []
    before: dict[str, Any] = {}

    try:
        before = get_status()
        if before.get('needs_repair') or before.get('chain_broken'):
            return {
                'success': False,
                'error': before.get('error_detail') or 'Migration chain is broken. Repair first.',
            }

        current = before.get('current_revision')
        if not current:
            return {'success': False, 'error': 'Database has no current revision to roll back from.'}

        script = _get_script_directory()
        if mode == 'one':
            rev = script.get_revision(current)
            parent = rev.down_revision
            if isinstance(parent, tuple):
                target = parent[0] if parent else None
            else:
                target = parent
            if not target:
                return {'success': False, 'error': 'Cannot roll back: already at base revision.'}
        else:
            target = (revision or '').strip()
            if not target:
                return {'success': False, 'error': 'revision is required when mode is "to".'}

        backup_result = _backup_sqlite_database()
        if not backup_result.get('success'):
            return backup_result
        steps.append({'step': 'backup', 'success': True, 'detail': backup_result.get('backup_path')})

        config = _get_alembic_config()
        with redirect_stdout(buffer):
            command.downgrade(config, target)
        output = buffer.getvalue().strip()

        after = get_status()
        steps.append({
            'step': 'downgrade',
            'success': True,
            'detail': {'from': current, 'to': after.get('current_revision'), 'target': target},
        })

        return {
            'success': True,
            'message': 'Migration rollback completed.',
            'mode': mode,
            'applied_from': current,
            'applied_to': after.get('current_revision'),
            'target_revision': target,
            'backup_path': backup_result.get('backup_path'),
            'output': output,
            'steps': steps,
            'warning': (
                'Rollback runs downgrade() DDL which may drop columns or tables. '
                'Verify application health after rolling back.'
            ),
        }
    except CommandError as exc:
        output = buffer.getvalue().strip()
        logger.error('Migration downgrade failed: %s', exc)
        return {
            'success': False,
            'error': str(exc),
            'mode': mode,
            'applied_from': before.get('current_revision'),
            'output': output,
            'steps': steps,
        }
    except Exception as exc:
        output = buffer.getvalue().strip()
        logger.exception('Migration downgrade failed')
        return {
            'success': False,
            'error': str(exc),
            'mode': mode,
            'applied_from': before.get('current_revision'),
            'output': output,
            'steps': steps,
        }
    finally:
        _upgrade_lock.release()


def run_upgrade(
    revision: str | None = 'head',
    mode: str = 'all',
) -> dict[str, Any]:
    """Apply pending migrations up to the given revision (or only the next one)."""
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

    buffer = io.StringIO()
    before: dict[str, Any] = {}
    target_revision: str | None = None

    try:
        before = get_status()
        target_revision, early = _resolve_upgrade_target(revision=revision, mode=mode)
        if early:
            early['mode'] = mode
            return early

        assert target_revision is not None
        pending = before.get('pending_revisions') or []
        attempted_revision = (
            pending[0]['revision']
            if mode == 'next' and pending
            else target_revision
        )

        config = _get_alembic_config()
        with redirect_stdout(buffer):
            command.upgrade(config, target_revision)
        output = buffer.getvalue().strip()

        after = get_status()
        applied_count = max(0, (before.get('pending_count') or 0) - (after.get('pending_count') or 0))
        message = 'Migrations applied successfully.'
        if mode == 'next':
            message = 'Next migration applied successfully.'

        return {
            'success': True,
            'message': message,
            'mode': mode,
            'target_revision': target_revision,
            'attempted_revision': attempted_revision,
            'applied_from': before.get('current_revision'),
            'applied_to': after.get('current_revision'),
            'applied_count': applied_count,
            'pending_count': after.get('pending_count', 0),
            'is_up_to_date': after.get('is_up_to_date', False),
            'output': output,
        }
    except CommandError as exc:
        output = buffer.getvalue().strip()
        pending = before.get('pending_revisions') or []
        failed_revision = _parse_failed_revision(output + '\n' + str(exc), pending)
        logger.error('Migration upgrade failed: %s', exc)
        return {
            'success': False,
            'error': str(exc),
            'mode': mode,
            'target_revision': target_revision,
            'failed_revision': failed_revision,
            'applied_from': before.get('current_revision'),
            'output': output,
        }
    except Exception as exc:
        output = buffer.getvalue().strip()
        pending = before.get('pending_revisions') or []
        failed_revision = _parse_failed_revision(output + '\n' + str(exc), pending)
        logger.exception('Migration upgrade failed')
        return {
            'success': False,
            'error': str(exc),
            'mode': mode,
            'target_revision': target_revision,
            'failed_revision': failed_revision,
            'applied_from': before.get('current_revision'),
            'output': output,
        }
    finally:
        _upgrade_lock.release()
