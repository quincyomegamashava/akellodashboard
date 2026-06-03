"""RQ queue helpers for Learning Hub."""

from __future__ import annotations

from typing import Any, Callable, Optional

from flask import current_app

_queue_singleton: Optional[Any] = None  # rq.Queue instance
_queue_disabled = False


def get_learn_queue():
    """Lazy-init RQ queue; returns None if Redis URL missing or connection fails."""
    global _queue_singleton, _queue_disabled

    if _queue_disabled:
        return None
    if _queue_singleton is not None:
        return _queue_singleton

    url = current_app.config.get("REDIS_URL")
    if not url:
        _queue_disabled = True
        return None

    try:
        from redis import Redis
        from rq import Queue

        conn = Redis.from_url(url)
        _queue_singleton = Queue("learn_hub", connection=conn)
        return _queue_singleton
    except Exception:
        _queue_disabled = True
        return None


def enqueue_or_run(job_fn: Callable[..., Any], *args, **kwargs) -> Optional[Any]:
    """Enqueue async job or run synchronously inside current app context."""
    q = get_learn_queue()
    if q:
        return q.enqueue(job_fn, *args, **kwargs)
    job_fn(*args, **kwargs)
    return None
