"""Finalize coding attempts (RQ worker + synchronous fallback)."""

from __future__ import annotations

import hashlib
from datetime import datetime

from app import db
from app.learning_hub.queue import enqueue_or_run
from app.learning_hub.models import LearnChallenge, LearnChallengeAttempt, LearnLearner
from app.learning_hub.services.attempt_xp_policy import learner_already_has_prior_passing_attempt
from app.learning_hub.services.sandbox import grade_python_tests
from app.learning_hub.services.skill_level import refresh_learner_skill_level
from app.learning_hub.services.track_progress import refresh_tracks_touching_challenge
from app.learning_hub.services.xp import compute_awarded_xp


def _update_streak(learner: LearnLearner) -> None:
    from datetime import date, timedelta

    today = date.today()
    if learner.last_activity_at:
        ld = learner.last_activity_at.date()
        if ld == today:
            return
        if ld == today - timedelta(days=1):
            learner.streak_days = (learner.streak_days or 0) + 1
        else:
            learner.streak_days = 1
    else:
        learner.streak_days = 1
    learner.last_activity_at = datetime.utcnow()


def grade_learn_coding_attempt(attempt_id: int) -> None:
    """Compute score/xp for a coding submission (called from worker or sync)."""
    from app import app as flask_app

    with flask_app.app_context():
        attempt = db.session.get(LearnChallengeAttempt, attempt_id)
        if not attempt or attempt.status != "submitted":
            return

        challenge = db.session.get(LearnChallenge, attempt.challenge_id)
        learner = db.session.get(LearnLearner, attempt.learner_id)
        if not challenge or not learner:
            attempt.status = "void"
            db.session.commit()
            return

        content = challenge.content_json or {}
        lang = (content.get("language") or "python").lower()
        tests = content.get("tests") or []
        code = (attempt.payload_json or {}).get("code") or ""

        if lang != "python":
            attempt.status = "graded"
            attempt.score = 0
            attempt.max_score = 1
            attempt.passed = False
            attempt.meta_json = {"error": "Unsupported language in MVP"}
            db.session.commit()
            return

        score, max_score, meta = grade_python_tests(code, tests)
        passed = bool(max_score > 0 and score / max_score >= 0.99)

        attempt_no = attempt.attempt_no
        prior_pass = learner_already_has_prior_passing_attempt(
            learner.id,
            challenge.id,
            exclude_attempt_id=attempt.id,
        )
        eligible_for_credit = passed and not prior_pass

        first_attempt_bonus = bool(eligible_for_credit and attempt_no == 1)
        xp_awarded = 0

        if eligible_for_credit:
            xp_awarded = compute_awarded_xp(
                base_points=challenge.base_points,
                difficulty=challenge.difficulty,
                streak_days=learner.streak_days or 0,
                first_attempt_bonus=first_attempt_bonus,
            )
            learner.total_xp = int((learner.total_xp or 0) + xp_awarded)
            _update_streak(learner)

        attempt.score = float(score)
        attempt.max_score = float(max_score)
        attempt.passed = passed
        attempt.status = "graded"
        attempt.submitted_at = datetime.utcnow()
        attempt.meta_json = meta
        attempt.first_attempt_bonus_applied = first_attempt_bonus
        attempt.xp_awarded = xp_awarded if eligible_for_credit else 0

        db.session.add(attempt)
        db.session.add(learner)
        db.session.commit()

        refresh_learner_skill_level(learner.id)
        refresh_tracks_touching_challenge(learner.id, challenge.id)
        db.session.commit()


def submit_coding_attempt(
    *,
    learner_id: int,
    challenge_id: int,
    code: str,
    ip: str | None,
) -> LearnChallengeAttempt:
    """Create submitted attempt row and enqueue grading."""
    challenge = db.session.get(LearnChallenge, challenge_id)
    if not challenge or challenge.challenge_type != "coding":
        raise ValueError("Invalid coding challenge")

    prior = LearnChallengeAttempt.query.filter_by(learner_id=learner_id, challenge_id=challenge_id).count()
    attempt_no = prior + 1

    ip_hash = None
    if ip:
        ip_hash = hashlib.sha256(ip.encode("utf-8")).hexdigest()[:32]

    attempt = LearnChallengeAttempt(
        learner_id=learner_id,
        challenge_id=challenge_id,
        attempt_no=attempt_no,
        submitted_at=None,
        payload_json={"code": code},
        status="submitted",
        ip_hash=ip_hash,
    )
    db.session.add(attempt)
    db.session.commit()

    enqueue_or_run(grade_learn_coding_attempt, attempt.id)
    db.session.refresh(attempt)
    return attempt
