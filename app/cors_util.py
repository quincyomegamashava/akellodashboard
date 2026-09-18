"""Parse Socket.IO / HTTP CORS origin allowlists from env."""

from __future__ import annotations

import os

# Safe local default — never '*'.
LOCAL_DEFAULT_ORIGINS = (
    'http://localhost:5000',
    'http://127.0.0.1:5000',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
)


def is_production_env(environ=None) -> bool:
    environ = os.environ if environ is None else environ
    value = (environ.get('FLASK_ENV') or environ.get('ENV') or '').strip().lower()
    return value in ('production', 'prod')


def parse_cors_origins(
    raw: str | None,
    *,
    production: bool | None = None,
    environ=None,
) -> list[str] | str:
    """Return an origin list, or the string ``'*'`` only when explicitly set off production.

    Empty / unset → localhost defaults. Production refuses ``*``.
    """
    environ = os.environ if environ is None else environ
    if production is None:
        production = is_production_env(environ)

    text = (raw or '').strip()
    if not text:
        return list(LOCAL_DEFAULT_ORIGINS)

    if text == '*':
        if production:
            raise RuntimeError(
                'SOCKETIO_CORS_ORIGINS/CORS_ORIGINS cannot be * when '
                'FLASK_ENV/ENV is production. Set an explicit origin allowlist.'
            )
        return '*'

    origins: list[str] = []
    seen: set[str] = set()
    for part in text.split(','):
        origin = part.strip().rstrip('/')
        if origin and origin not in seen:
            if origin == '*':
                if production:
                    raise RuntimeError(
                        'SOCKETIO_CORS_ORIGINS/CORS_ORIGINS cannot include * in production.'
                    )
                return '*'
            seen.add(origin)
            origins.append(origin)
    return origins or list(LOCAL_DEFAULT_ORIGINS)


def socketio_cors_origins(environ=None) -> list[str] | str:
    environ = os.environ if environ is None else environ
    raw = (
        environ.get('SOCKETIO_CORS_ORIGINS')
        or environ.get('CORS_ORIGINS')
        or ''
    )
    return parse_cors_origins(raw, environ=environ)
