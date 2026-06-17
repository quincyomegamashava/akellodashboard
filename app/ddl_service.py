"""Dialect-aware DDL builder and executor for Database Schema Studio."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from flask import current_app, has_request_context, request
from flask_login import current_user
from sqlalchemy.engine import Engine

from app import db
from app.migration_schema import column_exists, table_exists
from app.migration_service import _backup_sqlite_database
from app.models import AuditLog
from app.schema_studio_service import APP_DB_KEY, get_engine


def _quote_ident(name: str, dialect: str) -> str:
    if dialect == 'mysql':
        return f'`{name}`'
    return f'"{name}"'


def _format_default(default: Any, dialect: str) -> str:
    if default is None or default == '':
        return ''
    if isinstance(default, bool):
        if dialect == 'mysql':
            return ' DEFAULT 1' if default else ' DEFAULT 0'
        return f' DEFAULT {str(default).upper()}'
    if isinstance(default, (int, float)):
        return f' DEFAULT {default}'
    escaped = str(default).replace("'", "''")
    return f" DEFAULT '{escaped}'"


def _check_schema_changes_enabled() -> dict[str, Any] | None:
    if not current_app.config.get('ALLOW_WEB_SCHEMA_CHANGES', True):
        return {
            'success': False,
            'error': 'Web schema changes are disabled (ALLOW_WEB_SCHEMA_CHANGES=false).',
        }
    return None


def _validate_confirmation(
    data: dict[str, Any],
    expected: str,
    *,
    require_confirm: bool = True,
) -> dict[str, Any] | None:
    if require_confirm and not data.get('confirm'):
        return {'success': False, 'error': 'Confirmation required. Send {"confirm": true}.'}
    typed = (data.get('confirmation_text') or '').strip()
    if require_confirm and typed != expected:
        return {
            'success': False,
            'error': f'Type exactly "{expected}" to confirm this operation.',
        }
    return None


def _audit_ddl(
    db_key: str,
    action: str,
    entity_label: str,
    snapshot: dict[str, Any],
) -> None:
    ctx = {}
    if has_request_context():
        try:
            if current_user.is_authenticated:
                ctx['actor_user_id'] = current_user.id
                ctx['actor_username'] = current_user.username
        except Exception:
            pass
        ctx['ip_address'] = request.remote_addr
        ctx['endpoint'] = request.endpoint
        ctx['http_method'] = request.method
        ctx['url_path'] = request.path
        ctx['user_agent'] = (request.headers.get('User-Agent') or '')[:500]

    entry = AuditLog(
        action=action,
        entity_type='schema_ddl',
        entity_id=db_key,
        entity_label=entity_label,
        snapshot=snapshot,
        occurred_at=datetime.utcnow(),
        **ctx,
    )
    db.session.add(entry)
    db.session.commit()


def _maybe_backup_app_db(db_key: str) -> dict[str, Any] | None:
    if db_key != APP_DB_KEY:
        return None
    return _backup_sqlite_database()


def _execute_statements(engine: Engine, statements: list[str]) -> None:
    with engine.begin() as conn:
        for sql in statements:
            conn.execute(sa.text(sql))


def build_create_table_sql(db_key: str, payload: dict[str, Any]) -> list[str]:
    engine = get_engine(db_key)
    dialect = engine.dialect.name
    table_name = (payload.get('name') or '').strip()
    if not table_name:
        raise ValueError('Table name is required')
    if table_exists(engine, table_name):
        raise ValueError(f'Table {table_name} already exists')

    columns = payload.get('columns') or []
    if not columns:
        raise ValueError('At least one column is required')

    col_defs: list[str] = []
    pk_cols: list[str] = []
    for col in columns:
        name = (col.get('name') or '').strip()
        if not name:
            raise ValueError('Column name is required')
        col_type = (col.get('type') or 'TEXT').strip()
        parts = [f'{_quote_ident(name, dialect)} {col_type}']
        if col.get('primary_key'):
            pk_cols.append(name)
        if not col.get('nullable', True):
            parts.append('NOT NULL')
        parts.append(_format_default(col.get('default'), dialect))
        col_defs.append(' '.join(p for p in parts if p))

    if pk_cols:
        pk_list = ', '.join(_quote_ident(c, dialect) for c in pk_cols)
        col_defs.append(f'PRIMARY KEY ({pk_list})')

    qt = _quote_ident(table_name, dialect)
    return [f'CREATE TABLE {qt} (\n  ' + ',\n  '.join(col_defs) + '\n)']


def build_rename_table_sql(db_key: str, table_name: str, new_name: str) -> list[str]:
    engine = get_engine(db_key)
    dialect = engine.dialect.name
    new_name = (new_name or '').strip()
    if not new_name:
        raise ValueError('New table name is required')
    if not table_exists(engine, table_name):
        raise ValueError(f'Table {table_name} does not exist')
    if table_exists(engine, new_name):
        raise ValueError(f'Table {new_name} already exists')

    old_q = _quote_ident(table_name, dialect)
    new_q = _quote_ident(new_name, dialect)
    if dialect == 'mysql':
        return [f'RENAME TABLE {old_q} TO {new_q}']
    if dialect == 'sqlite':
        return [f'ALTER TABLE {old_q} RENAME TO {new_q}']
    return [f'ALTER TABLE {old_q} RENAME TO {new_q}']


def build_drop_table_sql(db_key: str, table_name: str) -> list[str]:
    engine = get_engine(db_key)
    dialect = engine.dialect.name
    if not table_exists(engine, table_name):
        raise ValueError(f'Table {table_name} does not exist')
    qt = _quote_ident(table_name, dialect)
    return [f'DROP TABLE {qt}']


def build_add_column_sql(db_key: str, table_name: str, col: dict[str, Any]) -> list[str]:
    engine = get_engine(db_key)
    dialect = engine.dialect.name
    if not table_exists(engine, table_name):
        raise ValueError(f'Table {table_name} does not exist')

    name = (col.get('name') or '').strip()
    if not name:
        raise ValueError('Column name is required')
    if column_exists(engine, table_name, name):
        raise ValueError(f'Column {name} already exists')

    col_type = (col.get('type') or 'TEXT').strip()
    parts = [f'ALTER TABLE {_quote_ident(table_name, dialect)} ADD COLUMN {_quote_ident(name, dialect)} {col_type}']
    if not col.get('nullable', True):
        parts.append('NOT NULL')
    default = _format_default(col.get('default'), dialect)
    if default:
        parts.append(default)
    return [' '.join(parts)]


def build_alter_column_sql(
    db_key: str,
    table_name: str,
    column_name: str,
    changes: dict[str, Any],
) -> list[str]:
    engine = get_engine(db_key)
    dialect = engine.dialect.name
    if not column_exists(engine, table_name, column_name):
        raise ValueError(f'Column {column_name} does not exist')

    new_type = changes.get('type')
    nullable = changes.get('nullable')
    default = changes.get('default')
    qt = _quote_ident(table_name, dialect)
    qc = _quote_ident(column_name, dialect)

    if dialect == 'mysql':
        parts = [f'ALTER TABLE {qt} MODIFY COLUMN {qc}']
        if new_type:
            parts.append(str(new_type))
        if nullable is False:
            parts.append('NOT NULL')
        elif nullable is True:
            parts.append('NULL')
        if 'default' in changes:
            parts.append(_format_default(default, dialect) or ' DEFAULT NULL')
        return [' '.join(p for p in parts if p)]

    if dialect == 'postgresql':
        stmts = []
        if new_type:
            stmts.append(f'ALTER TABLE {qt} ALTER COLUMN {qc} TYPE {new_type}')
        if nullable is False:
            stmts.append(f'ALTER TABLE {qt} ALTER COLUMN {qc} SET NOT NULL')
        elif nullable is True:
            stmts.append(f'ALTER TABLE {qt} ALTER COLUMN {qc} DROP NOT NULL')
        if 'default' in changes:
            if default is None or default == '':
                stmts.append(f'ALTER TABLE {qt} ALTER COLUMN {qc} DROP DEFAULT')
            else:
                stmts.append(
                    f'ALTER TABLE {qt} ALTER COLUMN {qc} SET{_format_default(default, dialect)}'
                )
        return stmts or [f'-- No changes for {table_name}.{column_name}']

    if new_type and dialect == 'sqlite':
        return _sqlite_rebuild_column(engine, table_name, column_name, changes)

    stmts = []
    if new_type:
        stmts.append(f'ALTER TABLE {qt} ALTER COLUMN {qc} {new_type}')
    return stmts or [f'-- SQLite: limited ALTER for {table_name}.{column_name}; may require table rebuild']


def _sqlite_rebuild_column(
    engine: Engine,
    table_name: str,
    column_name: str,
    changes: dict[str, Any],
) -> list[str]:
    inspector = sa.inspect(engine)
    columns = inspector.get_columns(table_name)
    new_type = changes.get('type')
    stmts: list[str] = []
    temp = f'{table_name}__studio_tmp'
    qt = _quote_ident(table_name, 'sqlite')
    temp_q = _quote_ident(temp, 'sqlite')

    col_defs = []
    select_cols = []
    for col in columns:
        name = col['name']
        if name == column_name and new_type:
            type_str = str(new_type)
        else:
            type_str = str(col['type'])
        nullable = col.get('nullable', True)
        if name == column_name and changes.get('nullable') is False:
            nullable = False
        nn = '' if nullable else ' NOT NULL'
        col_defs.append(f'{_quote_ident(name, "sqlite")} {type_str}{nn}')
        select_cols.append(_quote_ident(name, 'sqlite'))

    stmts.append(f'CREATE TABLE {temp_q} ({", ".join(col_defs)})')
    stmts.append(f'INSERT INTO {temp_q} SELECT {", ".join(select_cols)} FROM {qt}')
    stmts.append(f'DROP TABLE {qt}')
    stmts.append(f'ALTER TABLE {temp_q} RENAME TO {table_name}')
    return stmts


def build_drop_column_sql(db_key: str, table_name: str, column_name: str) -> list[str]:
    engine = get_engine(db_key)
    dialect = engine.dialect.name
    if not column_exists(engine, table_name, column_name):
        raise ValueError(f'Column {column_name} does not exist')

    qt = _quote_ident(table_name, dialect)
    qc = _quote_ident(column_name, dialect)
    if dialect == 'sqlite':
        try:
            return [f'ALTER TABLE {qt} DROP COLUMN {qc}']
        except Exception:
            return _sqlite_rebuild_drop_column(engine, table_name, column_name)
    if dialect == 'mysql':
        return [f'ALTER TABLE {qt} DROP COLUMN {qc}']
    return [f'ALTER TABLE {qt} DROP COLUMN {qc}']


def _sqlite_rebuild_drop_column(engine: Engine, table_name: str, column_name: str) -> list[str]:
    inspector = sa.inspect(engine)
    columns = [c for c in inspector.get_columns(table_name) if c['name'] != column_name]
    if not columns:
        raise ValueError('Cannot drop the only column')

    temp = f'{table_name}__studio_tmp'
    qt = _quote_ident(table_name, 'sqlite')
    temp_q = _quote_ident(temp, 'sqlite')
    col_defs = []
    select_cols = []
    for col in columns:
        name = col['name']
        type_str = str(col['type'])
        nullable = col.get('nullable', True)
        nn = '' if nullable else ' NOT NULL'
        col_defs.append(f'{_quote_ident(name, "sqlite")} {type_str}{nn}')
        select_cols.append(_quote_ident(name, 'sqlite'))

    return [
        f'CREATE TABLE {temp_q} ({", ".join(col_defs)})',
        f'INSERT INTO {temp_q} SELECT {", ".join(select_cols)} FROM {qt}',
        f'DROP TABLE {qt}',
        f'ALTER TABLE {temp_q} RENAME TO {table_name}',
    ]


def preview_ddl(operation: str, db_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    builders = {
        'create_table': lambda: build_create_table_sql(db_key, payload),
        'rename_table': lambda: build_rename_table_sql(
            db_key, payload['table'], payload['new_name']
        ),
        'drop_table': lambda: build_drop_table_sql(db_key, payload['table']),
        'add_column': lambda: build_add_column_sql(db_key, payload['table'], payload['column']),
        'alter_column': lambda: build_alter_column_sql(
            db_key, payload['table'], payload['column'], payload.get('changes', {})
        ),
        'drop_column': lambda: build_drop_column_sql(db_key, payload['table'], payload['column']),
    }
    if operation not in builders:
        raise ValueError(f'Unknown operation: {operation}')
    statements = builders[operation]()
    return {
        'success': True,
        'operation': operation,
        'statements': statements,
        'sql': ';\n'.join(statements) + (';' if statements else ''),
    }


def execute_ddl_operation(
    operation: str,
    db_key: str,
    payload: dict[str, Any],
    *,
    require_confirmation: bool = True,
) -> dict[str, Any]:
    disabled = _check_schema_changes_enabled()
    if disabled:
        return disabled

    preview = preview_ddl(operation, db_key, payload)
    statements = preview['statements']
    table = payload.get('table') or payload.get('name', '')
    confirm_key = f'{db_key}.{table}' if table else db_key

    if operation == 'drop_table':
        confirm_key = f'DROP {db_key}.{table}'
    elif operation == 'drop_column':
        confirm_key = f'DROP {db_key}.{table}.{payload.get("column", "")}'

    err = _validate_confirmation(payload, confirm_key, require_confirm=require_confirmation)
    if err:
        return err

    backup = _maybe_backup_app_db(db_key)
    if backup and not backup.get('success') and db_key == APP_DB_KEY:
        return backup

    try:
        engine = get_engine(db_key)
        _execute_statements(engine, statements)
        _audit_ddl(
            db_key,
            operation,
            confirm_key,
            {
                'sql': preview['sql'],
                'payload': payload,
                'backup_path': backup.get('backup_path') if backup else None,
            },
        )
        return {
            'success': True,
            'operation': operation,
            'sql': preview['sql'],
            'backup_path': backup.get('backup_path') if backup else None,
        }
    except Exception as exc:
        current_app.logger.exception('DDL operation failed: %s', operation)
        return {'success': False, 'error': str(exc), 'sql': preview.get('sql')}


def execute_sql_query(
    db_key: str,
    query: str,
    *,
    allow_write: bool = False,
    limit: int = 1000,
) -> dict[str, Any]:
    query = (query or '').strip()
    if not query:
        return {'success': False, 'error': 'Query is required'}

    upper = query.upper().lstrip()
    is_select = upper.startswith('SELECT') or upper.startswith('WITH') or upper.startswith('PRAGMA')
    is_read = is_select or upper.startswith('SHOW') or upper.startswith('DESCRIBE')

    if not is_read and not allow_write:
        disabled = _check_schema_changes_enabled()
        if disabled:
            return disabled

    if db_key == APP_DB_KEY:
        engine = get_engine(db_key)
    else:
        from app.database_manager import get_db_manager
        return get_db_manager().execute_query(db_key, query, limit=limit)

    start = datetime.utcnow()
    try:
        with engine.begin() as conn:
            if is_select and 'LIMIT' not in upper:
                query = f'{query.rstrip(";")} LIMIT {limit}'
            result = conn.execute(sa.text(query))
            if is_read or result.returns_rows:
                columns = list(result.keys())
                rows = []
                for row in result.fetchall():
                    item = {}
                    for i, col in enumerate(columns):
                        val = row[i]
                        if hasattr(val, 'isoformat'):
                            val = val.isoformat()
                        item[col] = val
                    rows.append(item)
                elapsed = (datetime.utcnow() - start).total_seconds()
                return {
                    'success': True,
                    'type': 'select',
                    'columns': columns,
                    'data': rows,
                    'row_count': len(rows),
                    'execution_time': elapsed,
                }
            affected = result.rowcount
            elapsed = (datetime.utcnow() - start).total_seconds()
            if not is_read:
                _audit_ddl(db_key, 'sql_execute', query[:200], {'query': query})
            return {
                'success': True,
                'type': 'modification',
                'affected_rows': affected,
                'execution_time': elapsed,
            }
    except Exception as exc:
        return {'success': False, 'error': str(exc)}


def get_schema_activity(limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 200))
    logs = (
        AuditLog.query.filter_by(entity_type='schema_ddl')
        .order_by(AuditLog.occurred_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            'id': log.id,
            'occurred_at': log.occurred_at.isoformat() if log.occurred_at else None,
            'action': log.action,
            'db_key': log.entity_id,
            'label': log.entity_label,
            'actor': log.actor_username,
            'snapshot': log.snapshot,
        }
        for log in logs
    ]
