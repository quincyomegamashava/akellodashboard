"""Recompute learner progress percentage per enrolled track."""

from __future__ import annotations

from datetime import datetime

from app import db
from app.learning_hub.models import LearnChallengeAttempt, LearnLearnerTrackProgress, LearnTrackChallenge


def recompute_learner_track_progress(learner_id: int, track_id: int) -> None:
    """Set percent_complete from count of passed graded attempts vs challenges linked to the track."""
    progress = LearnLearnerTrackProgress.query.filter_by(learner_id=learner_id, track_id=track_id).first()
    if not progress:
        return

    tc_rows = LearnTrackChallenge.query.filter_by(track_id=track_id).order_by(LearnTrackChallenge.sort_order).all()
    if not tc_rows:
        progress.percent_complete = 0.0
        progress.last_challenge_id = None
        db.session.add(progress)
        return

    total = len(tc_rows)
    passed_pairs: list[tuple[int, int]] = []

    for tc in tc_rows:
        cid = tc.challenge_id
        ok = (
            LearnChallengeAttempt.query.filter_by(
                learner_id=learner_id,
                challenge_id=cid,
                passed=True,
                status="graded",
            ).first()
            is not None
        )
        if ok:
            passed_pairs.append((tc.sort_order, cid))

    done = len(passed_pairs)
    progress.percent_complete = round(100.0 * done / total, 1)

    if passed_pairs:
        passed_pairs.sort(key=lambda x: x[0])
        progress.last_challenge_id = passed_pairs[-1][1]
    else:
        progress.last_challenge_id = None

    if done >= total:
        progress.status = "completed"
        if progress.completed_at is None:
            progress.completed_at = datetime.utcnow()
    else:
        if progress.status == "completed":
            progress.status = "active"
        progress.completed_at = None

    db.session.add(progress)


def refresh_tracks_touching_challenge(learner_id: int, challenge_id: int) -> None:
    """After grading an attempt, update every enrolled track that lists this challenge."""
    rows = db.session.query(LearnTrackChallenge.track_id).filter(LearnTrackChallenge.challenge_id == challenge_id).distinct().all()
    for (tid,) in rows:
        recompute_learner_track_progress(learner_id, tid)


def refresh_all_tracks_for_learner(learner_id: int) -> None:
    """Refresh progress for all tracks the learner is enrolled in (fixes stale rows)."""
    for row in LearnLearnerTrackProgress.query.filter_by(learner_id=learner_id).all():
        recompute_learner_track_progress(learner_id, row.track_id)
