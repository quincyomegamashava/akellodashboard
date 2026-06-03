"""Learner session authentication (separate from Flask-Login staff users)."""

from __future__ import annotations

from functools import wraps

from flask import g, redirect, request, session, url_for

SESSION_LEARNER_ID = "lh_learner_id"


def login_learner(learner_id: int) -> None:
    session[SESSION_LEARNER_ID] = int(learner_id)
    session.permanent = True


def logout_learner() -> None:
    session.pop(SESSION_LEARNER_ID, None)


def current_learner_id() -> int | None:
    lid = session.get(SESSION_LEARNER_ID)
    if lid is None:
        return None
    try:
        return int(lid)
    except (TypeError, ValueError):
        return None


def learner_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        from app.learning_hub.models import LearnLearner

        lid = current_learner_id()
        if not lid:
            return redirect(url_for("learn_portal.login", next=request.path))

        learner = LearnLearner.query.filter_by(id=lid, is_active=True).first()
        if not learner:
            logout_learner()
            return redirect(url_for("learn_portal.login"))

        g.learn_learner = learner
        return view_func(*args, **kwargs)

    return wrapped


def attach_current_learner() -> None:
    """Populate g.learn_learner when session present (optional for public pages)."""
    from app.learning_hub.models import LearnLearner

    lid = current_learner_id()
    g.learn_learner = None
    if lid:
        g.learn_learner = LearnLearner.query.filter_by(id=lid, is_active=True).first()


SESSION_GUARDIAN_ID = "lh_guardian_id"


def login_guardian(guardian_id: int) -> None:
    session[SESSION_GUARDIAN_ID] = int(guardian_id)
    session.permanent = True


def logout_guardian() -> None:
    session.pop(SESSION_GUARDIAN_ID, None)


def current_guardian_id() -> int | None:
    gid = session.get(SESSION_GUARDIAN_ID)
    if gid is None:
        return None
    try:
        return int(gid)
    except (TypeError, ValueError):
        return None


def guardian_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        from app.learning_hub.models import LearnGuardianAccount

        gid = current_guardian_id()
        if not gid:
            return redirect(url_for("learn_guardian.login", next=request.path))

        account = LearnGuardianAccount.query.filter_by(id=gid).first()
        if not account:
            logout_guardian()
            return redirect(url_for("learn_guardian.login"))

        g.guardian_account = account
        return view_func(*args, **kwargs)

    return wrapped


def attach_current_guardian() -> None:
    from app.learning_hub.models import LearnGuardianAccount

    gid = current_guardian_id()
    g.guardian_account = None
    if gid:
        g.guardian_account = LearnGuardianAccount.query.filter_by(id=gid).first()
