"""Adaptive recommendations (stub hooks for richer analytics later)."""

from __future__ import annotations

from typing import Any, Dict, List

from app.learning_hub.models import LearnChallenge, LearnChallengeAttempt


def recent_performance_summary(learner_id: int, limit: int = 10) -> Dict[str, Any]:
    rows = (
        LearnChallengeAttempt.query.filter_by(learner_id=learner_id)
        .order_by(LearnChallengeAttempt.submitted_at.desc().nullslast())
        .limit(limit)
        .all()
    )
    if not rows:
        return {"avg_ratio": None, "attempt_count": 0}

    ratios = []
    for r in rows:
        if r.max_score and r.max_score > 0 and r.score is not None:
            ratios.append(float(r.score) / float(r.max_score))

    avg_ratio = sum(ratios) / len(ratios) if ratios else None
    return {"avg_ratio": avg_ratio, "attempt_count": len(rows)}


def suggest_next_challenge_ids(learner_id: int, category: str | None = None, limit: int = 5) -> List[int]:
    """
    MVP heuristic:
    - If struggling (avg_ratio < 0.55): prefer beginner difficulty in category.
    - Else: prefer intermediate.
    """
    summary = recent_performance_summary(learner_id)
    avg = summary.get("avg_ratio")
    prefer = "beginner" if avg is not None and avg < 0.55 else "intermediate"

    q = LearnChallenge.query.filter_by(is_published=True)
    if category:
        q = q.filter(LearnChallenge.challenge_category == category)
    q = q.filter(LearnChallenge.difficulty == prefer)

    ids = [c.id for c in q.order_by(LearnChallenge.id).limit(limit).all()]
    if len(ids) < limit:
        q2 = LearnChallenge.query.filter_by(is_published=True)
        if category:
            q2 = q2.filter(LearnChallenge.challenge_category == category)
        extra = [c.id for c in q2.order_by(LearnChallenge.id).limit(limit).all() if c.id not in ids]
        ids.extend(extra[: limit - len(ids)])

    return ids[:limit]
