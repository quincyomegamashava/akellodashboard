"""SQL safety checks for the admin query UI.

Blocks DDL / DCL / filesystem and stacked statements using word-boundary
matches (so ``created_at`` is not treated as ``CREATE``). Read-only is the
default. DML can be enabled only by the server, never by a client flag alone.

Residual risk: the query UI still sends raw SQL strings (not bound
parameters) for ad-hoc SELECT. Visual-builder values are quote-escaped, not
fully parameterized.
"""

from __future__ import annotations

import re
from typing import Iterable

# Always blocked, including when DML is allowed.
_ALWAYS_BLOCKED = (
    r'DROP',
    r'ALTER',
    r'TRUNCATE',
    r'CREATE',
    r'GRANT',
    r'REVOKE',
    r'RENAME',
    r'LOAD\s+DATA',
    r'INTO\s+OUTFILE',
    r'INTO\s+DUMPFILE',
    r'CREATE\s+USER',
    r'DROP\s+USER',
    r'SET\s+PASSWORD',
    r'SET\s+GLOBAL',
    r'FLUSH',
    r'KILL',
    r'SHUTDOWN',
    r'HANDLER',
    r'CALL',
    r'LOCK\s+TABLES',
    r'UNLOCK\s+TABLES',
    r'PREPARE',
    r'EXECUTE',
    r'DEALLOCATE',
)

# Blocked unless the server explicitly allows DML (super-admin + env flag).
_DML_BLOCKED = (
    r'INSERT',
    r'UPDATE',
    r'DELETE',
    r'REPLACE',
    r'MERGE',
)

_ALWAYS_RE = re.compile(r'(?:' + '|'.join(rf'\b{p}\b' for p in _ALWAYS_BLOCKED) + r')', re.IGNORECASE)
_DML_RE = re.compile(r'(?:' + '|'.join(rf'\b{p}\b' for p in _DML_BLOCKED) + r')', re.IGNORECASE)

_READ_ONLY_LEADERS = frozenset({
    'SELECT',
    'WITH',
    'SHOW',
    'DESCRIBE',
    'DESC',
    'EXPLAIN',
    'TABLE',  # MySQL 8 TABLE t is a read
})

_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_SAFE_OPERATORS = frozenset({
    '=', '!=', '<>', '<', '>', '<=', '>=',
    'LIKE', 'NOT LIKE', 'IN', 'NOT IN',
    'IS', 'IS NOT', 'IS NULL', 'IS NOT NULL',
})


def strip_sql_comments(sql: str) -> str:
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
    sql = re.sub(r'--.*?$', ' ', sql, flags=re.MULTILINE)
    sql = re.sub(r'#.*?$', ' ', sql, flags=re.MULTILINE)
    return sql


def strip_string_literals(sql: str) -> str:
    """Replace quoted literals so keyword scans ignore user strings."""
    sql = re.sub(r"'(?:''|\\'|[^'])*'", "''", sql)
    sql = re.sub(r'"(?:""|\\"|[^"])*"', '""', sql)
    sql = re.sub(r'`[^`]*`', '``', sql)
    return sql


def split_sql_statements(sql: str) -> list[str]:
    """Split on semicolons that are not inside quotes."""
    statements: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    in_backtick = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'" and not in_double and not in_backtick:
            if in_single and i + 1 < len(sql) and sql[i + 1] == "'":
                buf.append("''")
                i += 2
                continue
            in_single = not in_single
            buf.append(ch)
        elif ch == '"' and not in_single and not in_backtick:
            in_double = not in_double
            buf.append(ch)
        elif ch == '`' and not in_single and not in_double:
            in_backtick = not in_backtick
            buf.append(ch)
        elif ch == ';' and not in_single and not in_double and not in_backtick:
            stmt = ''.join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = ''.join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _first_keyword(sql: str) -> str:
    cleaned = strip_string_literals(strip_sql_comments(sql)).strip()
    match = re.match(r'[\(\s]*([A-Za-z_]+)', cleaned)
    return (match.group(1) if match else '').upper()


def is_safe_identifier(name: str) -> bool:
    return bool(name) and bool(_IDENTIFIER_RE.match(name))


def sql_literal(value) -> str:
    """Quote a visual-builder value. Not a substitute for bound parameters."""
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    text = str(value).replace('\\', '\\\\').replace("'", "''")
    return f"'{text}'"


def is_safe_operator(op: str) -> bool:
    return (op or '').strip().upper() in _SAFE_OPERATORS


def validate_query_ui_sql(sql: str, *, allow_dml: bool = False) -> tuple[bool, str]:
    """Return ``(ok, error_message)``. ``error_message`` is empty when ok."""
    if not sql or not str(sql).strip():
        return False, 'Query cannot be empty'

    statements = split_sql_statements(sql)
    if len(statements) > 1:
        return False, 'Multiple SQL statements are not allowed'

    statement = statements[0] if statements else ''
    leader = _first_keyword(statement)
    if not leader:
        return False, 'Query could not be parsed'

    scan_target = strip_string_literals(strip_sql_comments(statement))
    always_hit = _ALWAYS_RE.search(scan_target)
    if always_hit:
        token = re.sub(r'\s+', ' ', always_hit.group(0)).upper()
        return False, f'Operation {token} is not allowed'

    dml_hit = _DML_RE.search(scan_target)
    if dml_hit and not allow_dml:
        token = re.sub(r'\s+', ' ', dml_hit.group(0)).upper()
        return False, (
            f'Operation {token} is not allowed. The query UI is read-only '
            'unless ALLOW_QUERY_UI_WRITES is enabled for a Super-admin.'
        )

    if not allow_dml and leader not in _READ_ONLY_LEADERS:
        return False, f'Statement type {leader} is not allowed in read-only mode'

    return True, ''


def assert_safe_identifiers(names: Iterable[str], *, kind: str = 'identifier') -> None:
    for name in names:
        if not is_safe_identifier(name):
            raise ValueError(f'Invalid {kind}: {name!r}')
