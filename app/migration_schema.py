"""Shared schema inspection helpers for migrations and admin preflight checks."""

from __future__ import annotations

import re
from typing import Any

import sqlalchemy as sa
from sqlalchemy import inspect as sa_inspect


def table_exists(bind, table_name: str) -> bool:
    try:
        return table_name in sa_inspect(bind).get_table_names()
    except Exception:
        return False


def column_exists(bind, table_name: str, column_name: str) -> bool:
    try:
        if not table_exists(bind, table_name):
            return False
        columns = {col['name'] for col in sa_inspect(bind).get_columns(table_name)}
        return column_name in columns
    except Exception:
        return False


def index_exists(bind, table_name: str, index_name: str) -> bool:
    try:
        if not table_exists(bind, table_name):
            return False
        indexes = sa_inspect(bind).get_indexes(table_name)
        return any(idx.get('name') == index_name for idx in indexes)
    except Exception:
        return False


def fk_exists(bind, table_name: str, fk_name: str) -> bool:
    try:
        if not table_exists(bind, table_name):
            return False
        fks = sa_inspect(bind).get_foreign_keys(table_name)
        return any(fk.get('name') == fk_name for fk in fks)
    except Exception:
        return False


def duplicate_non_null_values(bind, table_name: str, column_name: str) -> list[Any]:
    """Return non-null column values that appear more than once."""
    if not table_exists(bind, table_name) or not column_exists(bind, table_name, column_name):
        return []
    try:
        query = sa.text(
            f'SELECT "{column_name}" AS val FROM "{table_name}" '
            f'WHERE "{column_name}" IS NOT NULL '
            f'GROUP BY "{column_name}" HAVING COUNT(*) > 1 LIMIT 10'
        )
        rows = bind.execute(query).fetchall()
        return [row[0] for row in rows]
    except Exception:
        return []


def _migration_source_has_guard(source: str, pattern: str) -> bool:
    return bool(re.search(pattern, source, re.MULTILINE))


def migration_source_guards_table_create(source: str, table_name: str) -> bool:
    return _migration_source_has_guard(
        source,
        rf'if\s+not\s+_table_exists\(\s*["\']{re.escape(table_name)}["\']\s*\)',
    )


def migration_source_guards_column_add(source: str, table_name: str, column_name: str) -> bool:
    return bool(
        re.search(
            rf'_column_exists\(\s*["\']{re.escape(table_name)}["\']\s*,\s*["\']{re.escape(column_name)}["\']\s*\)',
            source,
        )
    )


def migration_source_guards_index_create(source: str, index_name: str) -> bool:
    return bool(
        re.search(rf'_index_exists\([^)]*["\']{re.escape(index_name)}["\']', source)
    )


def parse_migration_schema_operations(source: str) -> list[dict[str, Any]]:
    """Best-effort static scan of common Alembic operations in a migration file."""
    operations: list[dict[str, Any]] = []
    batch_table: str | None = None

    for line in source.splitlines():
        stripped = line.strip()
        batch_match = re.search(
            r'batch_alter_table\(\s*["\']([\w]+)["\']',
            stripped,
        )
        if batch_match:
            batch_table = batch_match.group(1)

        table_match = re.search(r'create_table\(\s*["\']([\w]+)["\']', stripped)
        if table_match:
            operations.append({
                'type': 'create_table',
                'table': table_match.group(1),
            })

        col_match = re.search(
            r'add_column\(\s*sa\.Column\(\s*["\']([\w]+)["\']',
            stripped,
        )
        if col_match and batch_table:
            operations.append({
                'type': 'add_column',
                'table': batch_table,
                'column': col_match.group(1),
            })

        idx_match = re.search(
            r'create_index\(\s*["\']([\w]+)["\']\s*,\s*["\']([\w]+)["\']'
            r'(?:\s*,\s*\[([^\]]+)\])?',
            stripped,
        )
        if idx_match:
            columns_raw = idx_match.group(3) or ''
            columns = re.findall(r'["\']([\w]+)["\']', columns_raw)
            operations.append({
                'type': 'create_index',
                'index': idx_match.group(1),
                'table': idx_match.group(2),
                'columns': columns,
                'unique': 'unique=True' in stripped,
            })

        fk_match = re.search(
            r'create_foreign_key\(\s*["\']([\w]+)["\']\s*,\s*["\']([\w]+)["\']',
            stripped,
        )
        if fk_match and batch_table:
            operations.append({
                'type': 'create_foreign_key',
                'table': batch_table,
                'name': fk_match.group(1),
                'referred_table': fk_match.group(2),
            })

    return operations


def evaluate_operation_preflight(
    bind,
    source: str,
    revision: str,
    operation: dict[str, Any],
) -> dict[str, Any] | None:
    """Return a preflight finding for a single parsed operation, or None if clear."""
    op_type = operation.get('type')
    table = operation.get('table')
    column = operation.get('column')

    if op_type == 'create_table' and table:
        exists = table_exists(bind, table)
        guarded = migration_source_guards_table_create(source, table)
        if exists and not guarded:
            return {
                'revision': revision,
                'severity': 'blocker',
                'code': 'table_exists',
                'message': f'Table "{table}" already exists but migration is not guarded.',
            }
        if exists and guarded:
            return {
                'revision': revision,
                'severity': 'info',
                'code': 'table_exists_idempotent',
                'message': f'Table "{table}" already exists; migration should skip safely.',
            }
        if not exists:
            return {
                'revision': revision,
                'severity': 'info',
                'code': 'table_will_be_created',
                'message': f'Table "{table}" will be created.',
            }

    if op_type == 'add_column' and table and column:
        exists = column_exists(bind, table, column)
        guarded = migration_source_guards_column_add(source, table, column)
        if exists and not guarded:
            return {
                'revision': revision,
                'severity': 'blocker',
                'code': 'column_exists',
                'message': (
                    f'Column "{table}.{column}" already exists but migration is not guarded.'
                ),
            }
        if exists and guarded:
            return {
                'revision': revision,
                'severity': 'info',
                'code': 'column_exists_idempotent',
                'message': f'Column "{table}.{column}" already exists; migration should skip safely.',
            }
        if not table_exists(bind, table):
            return {
                'revision': revision,
                'severity': 'warning',
                'code': 'missing_table',
                'message': f'Table "{table}" is missing; column "{column}" cannot be added yet.',
            }
        return {
            'revision': revision,
            'severity': 'info',
            'code': 'column_will_be_added',
            'message': f'Column "{table}.{column}" will be added.',
        }

    if op_type == 'create_index':
        index_name = operation.get('index')
        table = operation.get('table')
        columns = operation.get('columns') or []
        if not index_name or not table:
            return None
        exists = index_exists(bind, table, index_name)
        guarded = migration_source_guards_index_create(source, index_name)
        if exists:
            severity = 'info' if guarded else 'warning'
            return {
                'revision': revision,
                'severity': severity,
                'code': 'index_exists',
                'message': f'Index "{index_name}" on "{table}" already exists.',
            }
        if operation.get('unique') and len(columns) == 1:
            duplicates = duplicate_non_null_values(bind, table, columns[0])
            if duplicates:
                return {
                    'revision': revision,
                    'severity': 'blocker',
                    'code': 'unique_index_duplicates',
                    'message': (
                        f'Unique index "{index_name}" on "{table}.{columns[0]}" would fail: '
                        f'duplicate values found (e.g. {duplicates[:3]}).'
                    ),
                }
        return {
            'revision': revision,
            'severity': 'info',
            'code': 'index_will_be_created',
            'message': f'Index "{index_name}" on "{table}" will be created.',
        }

    if op_type == 'create_foreign_key':
        fk_table = operation.get('table')
        fk_name = operation.get('name')
        referred = operation.get('referred_table')
        guarded = bool(
            fk_name
            and re.search(rf'_fk_exists\([^)]*["\']{re.escape(fk_name)}["\']', source)
        )
        if fk_table and fk_name and fk_exists(bind, fk_table, fk_name):
            severity = 'info' if guarded else 'warning'
            return {
                'revision': revision,
                'severity': severity,
                'code': 'fk_exists',
                'message': f'Foreign key "{fk_name}" on "{fk_table}" already exists.',
            }
        if referred and not table_exists(bind, referred):
            return {
                'revision': revision,
                'severity': 'blocker',
                'code': 'missing_referred_table',
                'message': f'Referred table "{referred}" is missing for FK "{fk_name}".',
            }

    return None
