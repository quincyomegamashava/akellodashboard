"""Unified schema introspection for Database Schema Studio."""

from __future__ import annotations

import csv
import io
import os
import time
from typing import Any

import sqlalchemy as sa
from flask import current_app
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import Engine

from app import db
from app.database_manager import get_db_manager
from app.migration_schema import table_exists

APP_DB_KEY = 'app'
EXTERNAL_DB_KEYS = ('ruzivo', 'library')
ALL_DB_KEYS = (APP_DB_KEY,) + EXTERNAL_DB_KEYS

DB_LABELS = {
    APP_DB_KEY: 'Application Database',
    'ruzivo': 'Ruzivo Database',
    'library': 'Library Database',
}

_schema_cache: dict[str, dict[str, Any]] = {}


def invalidate_schema_cache(db_key: str | None = None) -> None:
    if db_key:
        _schema_cache.pop(db_key, None)
    else:
        _schema_cache.clear()


def _cache_get(db_key: str, key: str) -> Any | None:
    ttl = current_app.config.get('SCHEMA_STUDIO_CACHE_TTL', 45)
    entry = _schema_cache.get(db_key, {})
    item = entry.get(key)
    if not item:
        return None
    if time.time() - item['ts'] > ttl:
        return None
    return item['data']


def _cache_set(db_key: str, key: str, data: Any) -> None:
    _schema_cache.setdefault(db_key, {})[key] = {'ts': time.time(), 'data': data}


def _quote_ident(name: str, dialect: str) -> str:
    if dialect == 'mysql':
        return f'`{name}`'
    return f'"{name}"'


def get_engine(db_key: str) -> Engine:
    if db_key == APP_DB_KEY:
        return db.engine
    manager = get_db_manager()
    if db_key not in manager.engines:
        raise ValueError(f'Database {db_key} is not connected')
    return manager.engines[db_key]


def _db_status(db_key: str) -> str:
    if db_key == APP_DB_KEY:
        try:
            with db.engine.connect() as conn:
                conn.execute(sa.text('SELECT 1'))
            return 'connected'
        except Exception:
            return 'disconnected'
    result = get_db_manager().test_connection(db_key)
    return 'connected' if result.get('success') else 'disconnected'


def _sqlite_file_size() -> int | None:
    url = db.engine.url
    if not url.drivername.startswith('sqlite'):
        return None
    path = url.database
    if not path or path == ':memory:':
        return None
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def _format_column(col: dict[str, Any]) -> dict[str, Any]:
    col_type = col.get('type')
    type_str = str(col_type) if col_type is not None else 'unknown'
    default = col.get('default')
    if default is not None and hasattr(default, 'arg'):
        default = str(default.arg)
    elif default is not None:
        default = str(default)
    return {
        'name': col['name'],
        'type': type_str,
        'nullable': col.get('nullable', True),
        'default': default,
        'primary_key': col.get('primary_key', False),
        'autoincrement': col.get('autoincrement', False),
    }


def _table_row_count(bind, table_name: str, dialect: str) -> int:
    try:
        q = sa.text(f'SELECT COUNT(*) FROM {_quote_ident(table_name, dialect)}')
        return bind.execute(q).scalar() or 0
    except Exception:
        return 0


def _mysql_approximate_row_counts(engine: Engine, table_names: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    if not table_names:
        return counts
    try:
        db_name = engine.url.database
        placeholders = ', '.join(f':t{i}' for i in range(len(table_names)))
        params = {f't{i}': name for i, name in enumerate(table_names)}
        sql = sa.text(
            f'SELECT TABLE_NAME, TABLE_ROWS FROM information_schema.TABLES '
            f'WHERE TABLE_SCHEMA = :schema AND TABLE_NAME IN ({placeholders})'
        )
        params['schema'] = db_name
        with engine.connect() as conn:
            for row in conn.execute(sql, params):
                counts[row[0]] = int(row[1] or 0)
    except Exception:
        pass
    return counts


def list_databases() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    app_engine = db.engine
    app_dialect = app_engine.dialect.name
    app_status = _db_status(APP_DB_KEY)
    app_tables = 0
    if app_status == 'connected':
        try:
            app_tables = len(sa_inspect(app_engine).get_table_names())
        except Exception:
            pass
    items.append({
        'key': APP_DB_KEY,
        'name': DB_LABELS[APP_DB_KEY],
        'dialect': app_dialect,
        'status': app_status,
        'table_count': app_tables,
        'is_external': False,
        'size_bytes': _sqlite_file_size(),
        'external_ddl_allowed': True,
    })

    external_ddl = current_app.config.get('ALLOW_EXTERNAL_SCHEMA_CHANGES', False)
    for db_key in EXTERNAL_DB_KEYS:
        status = _db_status(db_key)
        dialect = 'mysql'
        table_count = 0
        host = ''
        database = ''
        manager = get_db_manager()
        cfg = manager.database_configs.get(db_key, {})
        host = cfg.get('host', '')
        database = cfg.get('database', '')
        if status == 'connected':
            try:
                engine = get_engine(db_key)
                dialect = engine.dialect.name
                table_count = len(sa_inspect(engine).get_table_names())
            except Exception:
                pass
        items.append({
            'key': db_key,
            'name': DB_LABELS.get(db_key, db_key),
            'dialect': dialect,
            'status': status,
            'table_count': table_count,
            'is_external': True,
            'host': host,
            'database': database,
            'external_ddl_allowed': external_ddl,
        })
    return items


def get_overview(db_key: str, *, exact_counts: bool = False) -> dict[str, Any]:
    cache_key = f'overview:{exact_counts}'
    cached = _cache_get(db_key, cache_key)
    if cached is not None:
        return cached

    engine = get_engine(db_key)
    dialect = engine.dialect.name
    inspector = sa_inspect(engine)
    table_names = inspector.get_table_names()
    total_rows: int | None = 0
    index_count = 0
    fk_count = 0
    row_count_approximate = False

    if db_key != APP_DB_KEY and dialect == 'mysql' and not exact_counts:
        approx = _mysql_approximate_row_counts(engine, table_names)
        total_rows = sum(approx.get(n, 0) for n in table_names)
        row_count_approximate = True
    elif exact_counts or db_key == APP_DB_KEY:
        with engine.connect() as bind:
            for name in table_names:
                total_rows += _table_row_count(bind, name, dialect)
    else:
        total_rows = None
        row_count_approximate = True

    for name in table_names:
        try:
            index_count += len(inspector.get_indexes(name))
            fk_count += len(inspector.get_foreign_keys(name))
        except Exception:
            pass

    overview: dict[str, Any] = {
        'db_key': db_key,
        'name': DB_LABELS.get(db_key, db_key),
        'dialect': dialect,
        'status': _db_status(db_key),
        'table_count': len(table_names),
        'total_rows': total_rows,
        'row_count_approximate': row_count_approximate,
        'index_count': index_count,
        'fk_count': fk_count,
        'is_external': db_key != APP_DB_KEY,
        'external_ddl_allowed': db_key == APP_DB_KEY or current_app.config.get(
            'ALLOW_EXTERNAL_SCHEMA_CHANGES', False
        ),
    }

    if db_key == APP_DB_KEY:
        overview['size_bytes'] = _sqlite_file_size()
        try:
            from app.migration_service import get_status
            mig = get_status()
            overview['migration_revision'] = mig.get('current_revision')
            overview['migration_heads'] = mig.get('head_revisions', [])
            overview['migration_pending'] = len(mig.get('pending_revisions', []))
            overview['migration_healthy'] = mig.get('is_healthy', False)
        except Exception as exc:
            overview['migration_error'] = str(exc)

    _cache_set(db_key, cache_key, overview)
    return overview


def list_tables(db_key: str, search: str = '', *, include_counts: bool = False) -> list[dict[str, Any]]:
    cache_key = f'tables:{search}:{include_counts}'
    cached = _cache_get(db_key, cache_key)
    if cached is not None:
        return cached

    engine = get_engine(db_key)
    dialect = engine.dialect.name
    inspector = sa_inspect(engine)
    needle = (search or '').strip().lower()
    names = sorted(inspector.get_table_names())
    if needle:
        names = [n for n in names if needle in n.lower()]

    approx_counts: dict[str, int] = {}
    if include_counts and dialect == 'mysql' and db_key != APP_DB_KEY:
        approx_counts = _mysql_approximate_row_counts(engine, names)

    tables: list[dict[str, Any]] = []
    with engine.connect() as bind:
        for name in names:
            col_count = len(inspector.get_columns(name))
            row_count: int | None = None
            if include_counts:
                if approx_counts:
                    row_count = approx_counts.get(name, 0)
                else:
                    row_count = _table_row_count(bind, name, dialect)
            tables.append({
                'name': name,
                'column_count': col_count,
                'row_count': row_count,
            })

    _cache_set(db_key, cache_key, tables)
    return tables


def get_table_detail(db_key: str, table_name: str) -> dict[str, Any]:
    engine = get_engine(db_key)
    dialect = engine.dialect.name
    if not table_exists(engine, table_name):
        raise ValueError(f'Table {table_name} does not exist')

    inspector = sa_inspect(engine)
    columns = [_format_column(c) for c in inspector.get_columns(table_name)]
    pks = inspector.get_pk_constraint(table_name).get('constrained_columns') or []
    indexes = inspector.get_indexes(table_name)
    fks = inspector.get_foreign_keys(table_name)

    with engine.connect() as bind:
        row_count = _table_row_count(bind, table_name, dialect)

    return {
        'name': table_name,
        'columns': columns,
        'primary_keys': pks,
        'indexes': indexes,
        'foreign_keys': fks,
        'row_count': row_count,
        'dialect': dialect,
    }


def get_table_rows(
    db_key: str,
    table_name: str,
    page: int = 1,
    per_page: int = 50,
    order_by: str | None = None,
    column_filter: str | None = None,
) -> dict[str, Any]:
    engine = get_engine(db_key)
    dialect = engine.dialect.name
    if not table_exists(engine, table_name):
        raise ValueError(f'Table {table_name} does not exist')

    page = max(1, page)
    per_page = max(1, min(per_page, 500))
    offset = (page - 1) * per_page
    qt = _quote_ident(table_name, dialect)

    where_clause = ''
    params: dict[str, Any] = {'limit': per_page, 'offset': offset}
    if column_filter:
        parts = column_filter.strip().split(':', 1)
        if len(parts) == 2:
            col, val = parts[0].strip(), parts[1].strip()
            inspector = sa_inspect(engine)
            valid_cols = {c['name'] for c in inspector.get_columns(table_name)}
            if col in valid_cols:
                where_clause = f' WHERE {_quote_ident(col, dialect)} LIKE :filter_val'
                params['filter_val'] = f'%{val}%'

    order_clause = ''
    if order_by:
        parts = order_by.strip().split()
        col = parts[0]
        direction = 'DESC' if len(parts) > 1 and parts[1].upper() == 'DESC' else 'ASC'
        inspector = sa_inspect(engine)
        valid_cols = {c['name'] for c in inspector.get_columns(table_name)}
        if col in valid_cols:
            order_clause = f' ORDER BY {_quote_ident(col, dialect)} {direction}'

    count_sql = sa.text(f'SELECT COUNT(*) FROM {qt}{where_clause}')
    data_sql = sa.text(f'SELECT * FROM {qt}{where_clause}{order_clause} LIMIT :limit OFFSET :offset')

    with engine.connect() as bind:
        total = bind.execute(count_sql, params).scalar() or 0
        result = bind.execute(data_sql, params)
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

    return {
        'columns': columns,
        'rows': rows,
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': max(1, (total + per_page - 1) // per_page),
    }


def export_table_csv(db_key: str, table_name: str, limit: int = 10000) -> str:
    limit = max(1, min(limit, 50000))
    data = get_table_rows(db_key, table_name, page=1, per_page=limit)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(data['columns'])
    for row in data['rows']:
        writer.writerow([row.get(c, '') for c in data['columns']])
    return output.getvalue()


def get_relations(db_key: str, table_prefix: str = '') -> dict[str, Any]:
    engine = get_engine(db_key)
    inspector = sa_inspect(engine)
    prefix = (table_prefix or '').strip().lower()
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()

    table_names = inspector.get_table_names()
    if prefix:
        table_names = [t for t in table_names if t.lower().startswith(prefix)]

    for table_name in table_names:
        if table_name not in seen_nodes:
            seen_nodes.add(table_name)
            nodes.append({'id': table_name, 'label': table_name})

        for fk in inspector.get_foreign_keys(table_name):
            ref_table = fk.get('referred_table')
            if ref_table and ref_table not in seen_nodes:
                if not prefix or ref_table.lower().startswith(prefix):
                    seen_nodes.add(ref_table)
                    nodes.append({'id': ref_table, 'label': ref_table})
            if ref_table and ref_table in seen_nodes:
                edges.append({
                    'from': table_name,
                    'to': ref_table,
                    'label': ','.join(fk.get('constrained_columns') or []),
                })

    node_ids = {n['id'] for n in nodes}
    edges = [e for e in edges if e['from'] in node_ids and e['to'] in node_ids]
    return {'nodes': nodes, 'edges': edges}


def get_column_types_for_dialect(dialect: str) -> list[str]:
    if dialect == 'mysql':
        return [
            'INT', 'BIGINT', 'SMALLINT', 'TINYINT', 'BOOLEAN',
            'VARCHAR(255)', 'TEXT', 'LONGTEXT', 'MEDIUMTEXT',
            'DATETIME', 'DATE', 'TIME', 'TIMESTAMP',
            'DECIMAL(10,2)', 'FLOAT', 'DOUBLE', 'JSON',
        ]
    if dialect == 'postgresql':
        return [
            'INTEGER', 'BIGINT', 'SMALLINT', 'BOOLEAN',
            'VARCHAR(255)', 'TEXT', 'TIMESTAMP', 'DATE', 'TIME',
            'NUMERIC(10,2)', 'REAL', 'DOUBLE PRECISION', 'JSONB', 'UUID',
        ]
    return [
        'INTEGER', 'BIGINT', 'BOOLEAN',
        'TEXT', 'VARCHAR(255)', 'REAL', 'NUMERIC',
        'DATETIME', 'DATE', 'JSON',
    ]
