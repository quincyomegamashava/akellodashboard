"""Dialect-aware DDL builder and executor for Database Schema Studio."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from flask import current_app, has_request_context, request
from flask_login import current_user
from sqlalchemy.engine import Engine

from app import db
from app.migration_schema import column_exists, table_exists
from app.migration_service import backup_app_database
from app.models import AuditLog
from app.schema_studio_service import APP_DB_KEY, get_engine, invalidate_schema_cache

IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
DANGEROUS_SQL_PATTERNS = re.compile(
    r'\b(DROP\s+DATABASE|DROP\s+SCHEMA|TRUNCATE\s+DATABASE|'
    r'GRANT\s+|REVOKE\s+|CREATE\s+USER|DROP\s+USER|'
    r'LOAD\s+DATA|INTO\s+OUTFILE|INTO\s+DUMPFILE)\b',
    re.IGNORECASE,
)


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


def validate_identifier(name: str, label: str = 'Identifier') -> str:
    name = (name or '').strip()
    if not name or not IDENTIFIER_RE.match(name):
        raise ValueError(f'{label} must match [A-Za-z_][A-Za-z0-9_]*')
    return name


def _check_schema_changes_enabled(db_key: str | None = None) -> dict[str, Any] | None:
    if not current_app.config.get('ALLOW_WEB_SCHEMA_CHANGES', True):
        return {
            'success': False,
            'error': 'Web schema changes are disabled (ALLOW_WEB_SCHEMA_CHANGES=false).',
        }
    if db_key and db_key != APP_DB_KEY:
        if not current_app.config.get('ALLOW_EXTERNAL_SCHEMA_CHANGES', False):
            return {
                'success': False,
                'error': (
                    'External database DDL is disabled (ALLOW_EXTERNAL_SCHEMA_CHANGES=false). '
                    'Enable only when you intend to modify production MySQL databases.'
                ),
            }
    return None


def _validate_sql_query(query: str, db_key: str, *, allow_write: bool) -> dict[str, Any] | None:
    stripped = query.strip().rstrip(';')
    if ';' in stripped:
        return {
            'success': False,
            'error': 'Multiple SQL statements are not allowed. Run one statement at a time.',
        }
    if DANGEROUS_SQL_PATTERNS.search(query):
        return {'success': False, 'error': 'This query pattern is blocked for safety.'}
    if db_key != APP_DB_KEY and allow_write:
        upper = query.upper()
        if any(kw in upper for kw in ('DROP TABLE', 'DROP COLUMN', 'TRUNCATE', 'ALTER TABLE')):
            ext_ok = current_app.config.get('ALLOW_EXTERNAL_SCHEMA_CHANGES', False)
            if not ext_ok:
                return {
                    'success': False,
                    'error': 'DDL on external databases requires ALLOW_EXTERNAL_SCHEMA_CHANGES=true.',
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
    return backup_app_database()


def _execute_statements(engine: Engine, statements: list[str]) -> None:
    with engine.begin() as conn:
        for sql in statements:
            conn.execute(sa.text(sql))


def build_create_table_sql(db_key: str, payload: dict[str, Any]) -> list[str]:
    engine = get_engine(db_key)
    dialect = engine.dialect.name
    table_name = validate_identifier(payload.get('name'), 'Table name')
    if table_exists(engine, table_name):
        raise ValueError(f'Table {table_name} already exists')

    columns = payload.get('columns') or []
    if not columns:
        raise ValueError('At least one column is required')

    col_defs: list[str] = []
    pk_cols: list[str] = []
    for col in columns:
        name = validate_identifier(col.get('name'), 'Column name')
        col_type = (col.get('type') or 'TEXT').strip()
        if not re.match(r'^[A-Za-z0-9_(),.\s]+$', col_type):
            raise ValueError(f'Invalid column type: {col_type}')
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
    table_name = validate_identifier(table_name, 'Table name')
    new_name = validate_identifier(new_name, 'New table name')
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
    table_name = validate_identifier(table_name, 'Table name')
    if not table_exists(engine, table_name):
        raise ValueError(f'Table {table_name} does not exist')
    qt = _quote_ident(table_name, dialect)
    return [f'DROP TABLE {qt}']


def build_add_column_sql(db_key: str, table_name: str, col: dict[str, Any]) -> list[str]:
    engine = get_engine(db_key)
    dialect = engine.dialect.name
    table_name = validate_identifier(table_name, 'Table name')
    if not table_exists(engine, table_name):
        raise ValueError(f'Table {table_name} does not exist')

    name = validate_identifier(col.get('name'), 'Column name')
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
    table_name = validate_identifier(table_name, 'Table name')
    column_name = validate_identifier(column_name, 'Column name')
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
    table_name = validate_identifier(table_name, 'Table name')
    column_name = validate_identifier(column_name, 'Column name')
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


def build_create_index_sql(db_key: str, table_name: str, payload: dict[str, Any]) -> list[str]:
    engine = get_engine(db_key)
    dialect = engine.dialect.name
    table_name = validate_identifier(table_name, 'Table name')
    index_name = validate_identifier(payload.get('name') or f'idx_{table_name}', 'Index name')
    columns = payload.get('columns') or []
    if not columns:
        raise ValueError('At least one column is required for an index')
    for col in columns:
        validate_identifier(col, 'Column name')
    unique = 'UNIQUE ' if payload.get('unique') else ''
    cols = ', '.join(_quote_ident(c, dialect) for c in columns)
    qt = _quote_ident(table_name, dialect)
    qi = _quote_ident(index_name, dialect)
    return [f'CREATE {unique}INDEX {qi} ON {qt} ({cols})']


def build_drop_index_sql(db_key: str, table_name: str, index_name: str) -> list[str]:
    engine = get_engine(db_key)
    dialect = engine.dialect.name
    table_name = validate_identifier(table_name, 'Table name')
    index_name = validate_identifier(index_name, 'Index name')
    qt = _quote_ident(table_name, dialect)
    qi = _quote_ident(index_name, dialect)
    if dialect == 'mysql':
        return [f'DROP INDEX {qi} ON {qt}']
    return [f'DROP INDEX {qi}']


def build_add_foreign_key_sql(db_key: str, table_name: str, payload: dict[str, Any]) -> list[str]:
    engine = get_engine(db_key)
    dialect = engine.dialect.name
    table_name = validate_identifier(table_name, 'Table name')
    fk_name = validate_identifier(payload.get('name') or 'fk_studio', 'Foreign key name')
    local_cols = payload.get('columns') or []
    ref_table = validate_identifier(payload.get('referred_table'), 'Referenced table')
    ref_cols = payload.get('referred_columns') or []
    if not local_cols or not ref_cols:
        raise ValueError('Local and referenced columns are required')
    for col in local_cols + ref_cols:
        validate_identifier(col, 'Column name')
    on_delete = (payload.get('on_delete') or 'NO ACTION').upper()
    qt = _quote_ident(table_name, dialect)
    local = ', '.join(_quote_ident(c, dialect) for c in local_cols)
    ref = _quote_ident(ref_table, dialect)
    remote = ', '.join(_quote_ident(c, dialect) for c in ref_cols)
    return [
        f'ALTER TABLE {qt} ADD CONSTRAINT {_quote_ident(fk_name, dialect)} '
        f'FOREIGN KEY ({local}) REFERENCES {ref} ({remote}) ON DELETE {on_delete}'
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
        'create_index': lambda: build_create_index_sql(db_key, payload['table'], payload),
        'drop_index': lambda: build_drop_index_sql(
            db_key, payload['table'], payload['index_name']
        ),
        'add_foreign_key': lambda: build_add_foreign_key_sql(db_key, payload['table'], payload),
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
    disabled = _check_schema_changes_enabled(db_key)
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
    elif operation == 'drop_index':
        confirm_key = f'DROP INDEX {db_key}.{table}.{payload.get("index_name", "")}'
    elif operation == 'rename_table':
        confirm_key = f'RENAME {db_key}.{table}'

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
        invalidate_schema_cache(db_key)
        result: dict[str, Any] = {
            'success': True,
            'operation': operation,
            'sql': preview['sql'],
            'backup_path': backup.get('backup_path') if backup else None,
        }
        if db_key == APP_DB_KEY:
            result['suggest_generate_migration'] = True
        return result
    except Exception as exc:
        current_app.logger.exception('DDL operation failed: %s', operation)
        return {'success': False, 'error': str(exc), 'sql': preview.get('sql')}


def execute_sql_query(
    db_key: str,
    query: str,
    *,
    allow_write: bool = False,
    limit: int = 1000,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    query = (query or '').strip()
    if not query:
        return {'success': False, 'error': 'Query is required'}

    sql_err = _validate_sql_query(query, db_key, allow_write=allow_write)
    if sql_err:
        return sql_err

    limit = max(1, min(int(limit), 5000))
    upper = query.upper().lstrip()
    is_select = upper.startswith('SELECT') or upper.startswith('WITH') or upper.startswith('PRAGMA')
    is_read = is_select or upper.startswith('SHOW') or upper.startswith('DESCRIBE')

    if not is_read and not allow_write:
        disabled = _check_schema_changes_enabled(db_key)
        if disabled:
            return disabled

    if db_key != APP_DB_KEY:
        from app.database_manager import get_db_manager
        if not is_read and allow_write:
            ext = _check_schema_changes_enabled(db_key)
            if ext:
                return ext
        return get_db_manager().execute_query(db_key, query, limit=limit)

    start = datetime.utcnow()
    try:
        engine = get_engine(db_key)
        with engine.begin() as conn:
            conn.execute(sa.text(f'PRAGMA busy_timeout = {timeout_seconds * 1000}'))
            exec_query = query
            if is_select and 'LIMIT' not in upper:
                exec_query = f'{query.rstrip(";")} LIMIT {limit}'
            result = conn.execute(sa.text(exec_query))
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
