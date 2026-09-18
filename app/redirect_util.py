"""Safe internal redirect targets (login ``next`` / logout)."""

from __future__ import annotations

from urllib.parse import urlsplit


def is_safe_internal_redirect(target: str | None) -> bool:
    """True only for same-origin relative paths. Rejects open redirects."""
    if not target or not isinstance(target, str):
        return False
    candidate = target.strip()
    if not candidate.startswith('/') or candidate.startswith('//'):
        return False
    if '\\' in candidate or '\n' in candidate or '\r' in candidate:
        return False
    parts = urlsplit(candidate)
    if parts.scheme or parts.netloc:
        return False
    if parts.path.startswith('//'):
        return False
    return True
