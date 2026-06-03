"""XP eligibility: only the first passing graded attempt per (learner, challenge) earns XP."""

from __future__ import annotations

from app.learning_hub.models import LearnChallengeAttempt


def learner_already_has_prior_passing_attempt(
    learner_id: int,
    challenge_id: int,
    *,
    exclude_attempt_id: int | None = None,
) -> bool:
    """True if the learner already has a graded, passing attempt for this challenge."""
    q = LearnChallengeAttempt.query.filter(
        LearnChallengeAttempt.learner_id == learner_id,
        LearnChallengeAttempt.challenge_id == challenge_id,
        LearnChallengeAttempt.passed.is_(True),
        LearnChallengeAttempt.status == "graded",
    )
    if exclude_attempt_id is not None:
        q = q.filter(LearnChallengeAttempt.id != exclude_attempt_id)
    return q.first() is not None
