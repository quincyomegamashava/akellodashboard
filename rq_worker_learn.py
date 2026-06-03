#!/usr/bin/env python3
"""RQ worker for the Learning Hub queue ``learn_hub``.

Grades coding submissions asynchronously when ``REDIS_URL`` is set.

Run from the ``akellodashboard`` directory with the app on ``PYTHONPATH`` (or same
layout as ``flask run``), with dependencies installed::

    pip install -r requirements.txt
    set REDIS_URL=redis://127.0.0.1:6379/0
    python rq_worker_learn.py

Equivalent one-liner::

    rq worker learn_hub --url "$REDIS_URL"

``grade_learn_coding_attempt`` pushes a Flask application context internally.
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    redis_url = os.environ.get("REDIS_URL") or os.environ.get("CELERY_BROKER_URL")
    if not redis_url:
        print("Set REDIS_URL (or CELERY_BROKER_URL) to start the learn_hub worker.", file=sys.stderr)
        sys.exit(1)

    from redis import Redis
    from rq import Connection, Queue, Worker

    conn = Redis.from_url(redis_url)
    with Connection(conn):
        worker = Worker([Queue("learn_hub", connection=conn)])
        worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
