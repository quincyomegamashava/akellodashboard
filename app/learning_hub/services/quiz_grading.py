"""Grade quiz attempts using question bank (server-side only)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.learning_hub.models import LearnChallengeQuestion, LearnQuestionOption


def grade_quiz_challenge(challenge_id: int, answers: Dict[str, Any]) -> Tuple[float, float, List[int]]:
    """
    answers: question_id -> selected LearnQuestionOption.id (int or str).

    Returns (score, max_score, correct_question_ids).
    """
    links = (
        LearnChallengeQuestion.query.filter_by(challenge_id=challenge_id)
        .order_by(LearnChallengeQuestion.sort_order)
        .all()
    )
    correct_ids: List[int] = []
    score = 0.0
    max_score = 0.0

    for link in links:
        points = float(link.points_override if link.points_override is not None else 10)
        max_score += points

        qid = str(link.question_id)
        raw = answers.get(qid)
        try:
            picked_id = int(raw)
        except (TypeError, ValueError):
            continue

        opt = LearnQuestionOption.query.filter_by(id=picked_id, question_id=link.question_id).first()
        if opt and opt.is_correct:
            score += points
            correct_ids.append(link.question_id)

    return score, max_score, correct_ids
