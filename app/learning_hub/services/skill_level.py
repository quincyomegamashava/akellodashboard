"""Adjust learner skill_level from recent graded attempts."""

from __future__ import annotations

from typing import Optional

from app import db
from app.learning_hub.models import LearnChallengeAttempt, LearnLearner


def refresh_learner_skill_level(learner_id: int) -> Optional[str]:
    """
    Uses last up to 20 graded attempts with positive max_score.

    Rules (after enough samples):
      - avg >= 0.85 and n >= 12 -> advanced
      - avg >= 0.68 and n >= 6  -> intermediate
      - avg < 0.40 and n >= 8   -> beginner
    """
    attempts = (
        LearnChallengeAttempt.query.filter_by(learner_id=learner_id, status="graded")
        .filter(LearnChallengeAttempt.max_score.isnot(None))
        .filter(LearnChallengeAttempt.max_score > 0)
        .order_by(LearnChallengeAttempt.submitted_at.desc())
        .limit(20)
        .all()
    )
    ratios: list[float] = []
    for a in attempts:
        if a.score is None:
            continue
        ratios.append(float(a.score) / float(a.max_score))

    n = len(ratios)
    if n < 5:
        return None

    avg = sum(ratios) / n
    learner = db.session.get(LearnLearner, learner_id)
    if not learner:
        return None

    old = learner.skill_level or "beginner"
    new = old

    if n >= 12 and avg >= 0.85:
        new = "advanced"
    elif n >= 6 and avg >= 0.68:
        new = "intermediate"
    elif n >= 8 and avg < 0.40:
        new = "beginner"

    if new != old:
        learner.skill_level = new
        db.session.add(learner)
        return new
    return None
