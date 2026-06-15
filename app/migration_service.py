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
from sqlalchemy import inspect

from app import db

logger = logging.getLogger(__name__)

_upgrade_lock = threading.Lock()

# Schema probes tied to recent meeting notes / sales marketing migrations.
_SCHEMA_HINTS = (
    {'check': 'sales_marketing_stakeholder_leads table', 'type': 'table', 'name': 'sales_marketing_stakeholder_leads'},
    {'check': 'sales_marketing_stakeholder_leads.follow_up_status', 'type': 'column', 'table': 'sales_marketing_stakeholder_leads', 'column': 'follow_up_status'},
    {'check': 'meeting_notes_action_items table', 'type': 'table', 'name': 'meeting_notes_action_items'},
    {'check': 'meeting_notes_action_subtasks table', 'type': 'table', 'name': 'meeting_notes_action_subtasks'},
)

# Most specific schema signal first — used for stamp inference and recommendations.
_SCHEMA_REVISION_HINTS = (
    ('sales_marketing_stakeholder_leads.follow_up_status', 'r8s9t0u1v2w3', 'Sales marketing enhancements (follow-up status)'),
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


def _table_exists(table_name: str) -> bool:
    try:
        return table_name in inspect(db.engine).get_table_names()
    except Exception:
        return False


def _column_exists(table_name: str, column_name: str) -> bool:
    try:
        if not _table_exists(table_name):
            return False
        columns = {col['name'] for col in inspect(db.engine).get_columns(table_name)}
        return column_name in columns
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
        if before.get('needs_repair'):
            return {
                'success': False,
                'error': before.get('error_detail') or 'Migration chain is broken. Run repair first.',
            }
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
