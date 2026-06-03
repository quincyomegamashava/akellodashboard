"""Unlock / prerequisite checks for challenges."""

from __future__ import annotations

from typing import List, Tuple

from app import db
from app.learning_hub.models import (
    LearnBadge,
    LearnChallengeAttempt,
    LearnLearner,
    LearnLearnerBadge,
)


def learner_meets_challenge_prereqs(learner_id: int, challenge) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    prereq_ids = challenge.prerequisite_challenge_ids or []
    for pid in prereq_ids:
        ok = (
            LearnChallengeAttempt.query.filter_by(
                learner_id=learner_id,
                challenge_id=int(pid),
                passed=True,
            ).first()
            is not None
        )
        if not ok:
            reasons.append(f"Complete prerequisite challenge #{pid} first.")

    if challenge.required_level is not None:
        learner = db.session.get(LearnLearner, learner_id)
        xp = learner.total_xp if learner else 0
        tier = max(1, xp // 500 + 1)
        if tier < int(challenge.required_level):
            reasons.append(f"Reach learner level {challenge.required_level} (currently ~{tier}).")

    req_badges = challenge.required_badge_ids or []
    if req_badges:
        earned = {
            row.badge_id
            for row in LearnLearnerBadge.query.filter_by(learner_id=learner_id).all()
        }
        for bid in req_badges:
            if int(bid) not in earned:
                badge = db.session.get(LearnBadge, int(bid))
                label = badge.title if badge else f"Badge #{bid}"
                reasons.append(f"Requires badge: {label}")

    return (len(reasons) == 0, reasons)


def challenge_visible_for_profile(challenge, *, category: str, age_band: str, skill_level: str) -> bool:
    """Filter catalog by suitability lists (empty list = open to all)."""
    cats = challenge.suitable_categories or []
    bands = challenge.suitable_age_bands or []
    skills = challenge.suitable_skill_levels or []

    if cats and category not in cats:
        return False
    if bands and age_band not in bands:
        return False
    if skills and skill_level not in skills:
        return False
    return True
