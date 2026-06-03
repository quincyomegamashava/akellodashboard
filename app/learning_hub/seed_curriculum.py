"""Seed structured explorer curriculum: one quiz track slice per category + Python coding warmup."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from app import db
from app.learning_hub.admin_audit import log_staff_action
from app.learning_hub.models import (
    LearnBadge,
    LearnChallenge,
    LearnChallengeQuestion,
    LearnLearningTrack,
    LearnQuestion,
    LearnQuestionOption,
    LearnTrackChallenge,
)

# Tagline-aligned categories — at least one published challenge each.
QUIZ_DATA: Sequence[Tuple[str, Sequence[Tuple[str, Sequence[Tuple[str, bool]]]]]] = (
    (
        "Python Programming",
        (
            ("Which keyword defines a function in Python?", (("def", True), ("function", False), ("fn", False))),
            ("Which type is immutable in Python?", (("tuple", True), ("list", False), ("dict", False))),
        ),
    ),
    (
        "JavaScript",
        (
            ("Which keyword declares a block-scoped variable?", (("let", True), ("var", False), ("global", False))),
            ("typeof [] in JavaScript returns?", (("object", True), ("array", False), ("list", False))),
        ),
    ),
    (
        "Web Development",
        (
            ("Which protocol delivers web pages securely?", (("HTTPS", True), ("FTP", False), ("SMTP", False))),
            ("HTML stands for?", (("HyperText Markup Language", True), ("High Transfer Meta Language", False))),
        ),
    ),
    (
        "Artificial Intelligence",
        (
            ("Machine learning models learn from?", (("Data", True), ("Electricity alone", False))),
            ("A labelled dataset is used for?", (("Supervised learning", True), ("Random guessing", False))),
        ),
    ),
    (
        "Robotics",
        (
            ("A robot often uses sensors to?", (("Sense the environment", True), ("Cook food", False))),
            ("Actuators typically?", (("Move parts", True), ("Store Wi‑Fi passwords", False))),
        ),
    ),
    (
        "Scratch Programming",
        (
            ("Scratch scripts are built from?", (("Blocks", True), ("Binary files only", False))),
            ("Sprites in Scratch are?", (("Characters or objects on stage", True), ("Only backgrounds", False))),
        ),
    ),
    (
        "Cybersecurity",
        (
            ("A strong password should be?", (("Long and unique", True), ("Your birthday", False))),
            ("Phishing tries to?", (("Trick you into revealing secrets", True), ("Speed up Wi‑Fi", False))),
        ),
    ),
    (
        "Data Science",
        (
            ("Which is commonly used for tables of rows/columns?", (("Spreadsheet / dataframe idea", True), ("JPEG", False))),
            ("Mean is another word for?", (("Average", True), ("Median always", False))),
        ),
    ),
    (
        "ICT Fundamentals",
        (
            ("CPU mainly?", (("Processes instructions", True), ("Stores files forever", False))),
            ("RAM is?", (("Volatile memory", True), ("Permanent disk storage", False))),
        ),
    ),
    (
        "Computer Literacy",
        (
            ("Double-click usually?", (("Opens an item", True), ("Deletes instantly without warning always", False))),
            ("Folders help you?", (("Organize files", True), ("Increase monitor brightness only", False))),
        ),
    ),
)

PYTHON_CODING: Dict[str, Any] = {
    "title": "Explorer: Python — coding warmup",
    "category": "Python Programming",
    "description": "Write a tiny Python program that reads two integers and prints their sum.",
    "instructions": "Submit code that reads two integers from stdin (one per line) and prints their sum.",
    "starter_code": "a = int(input())\nb = int(input())\nprint(a + b)",
    # Shown for "Run sample" only — full suite stays hidden until final submit.
    "public_tests": [{"stdin": "2\n3\n", "expected_stdout": "5"}],
    "tests": [{"stdin": "2\n3\n", "expected_stdout": "5"}, {"stdin": "10\n-4\n", "expected_stdout": "6"}],
}


def explorer_curriculum_seeded() -> bool:
    return (
        db.session.query(LearnLearningTrack.id).filter_by(title="Akello Explorer Path").first()
        is not None
    )


def seed_explorer_curriculum(actor_staff_user_id: Optional[int]) -> Dict[str, Any]:
    """Idempotent seeding for quizzes + coding + umbrella track."""
    if explorer_curriculum_seeded():
        return {"skipped": True, "reason": "already_seeded"}

    badge = LearnBadge(
        slug="akello-explorer",
        title="Akello Explorer",
        description="Completed intro challenges across core STEM categories.",
    )
    db.session.add(badge)
    db.session.flush()

    challenge_ids: List[int] = []
    sort_order = 0

    for category, questions in QUIZ_DATA:
        title = f"Explorer: {category}"
        ch = LearnChallenge(
            title=title,
            description=f"Introductory quiz for {category}.",
            challenge_category=category,
            challenge_type="quiz",
            difficulty="beginner",
            base_points=20,
            time_limit_seconds=600,
            suitable_categories=[],
            suitable_age_bands=[],
            suitable_skill_levels=[],
            instructions="Pick the best answer for each question.",
            is_published=True,
        )
        db.session.add(ch)
        db.session.flush()

        q_sort = 0
        for stem, options in questions:
            q = LearnQuestion(stem=stem, question_type="mcq", difficulty="beginner", explanation=None)
            db.session.add(q)
            db.session.flush()
            o_order = 0
            for text, ok in options:
                db.session.add(LearnQuestionOption(question_id=q.id, text=text, is_correct=ok, sort_order=o_order))
                o_order += 1
            db.session.add(LearnChallengeQuestion(challenge_id=ch.id, question_id=q.id, sort_order=q_sort, points_override=10))
            q_sort += 1

        challenge_ids.append(ch.id)
        sort_order += 1

    # Python coding challenge (uses sandbox runner + optional Judge0)
    code_ch = LearnChallenge(
        title=PYTHON_CODING["title"],
        description=PYTHON_CODING["description"],
        challenge_category=PYTHON_CODING["category"],
        challenge_type="coding",
        difficulty="beginner",
        base_points=35,
        time_limit_seconds=120,
        suitable_categories=[],
        suitable_age_bands=[],
        suitable_skill_levels=[],
        instructions=PYTHON_CODING["instructions"],
        content_json={
            "language": "python",
            "starter_code": PYTHON_CODING["starter_code"],
            "public_tests": PYTHON_CODING["public_tests"],
            "tests": PYTHON_CODING["tests"],
        },
        is_published=True,
    )
    db.session.add(code_ch)
    db.session.flush()
    challenge_ids.insert(1, code_ch.id)

    track = LearnLearningTrack(
        title="Akello Explorer Path",
        description="Structured tracks, quizzes, challenges, and XP — built for primary through tertiary learners.",
        difficulty="beginner",
        category="cross_cutting",
        estimated_duration_minutes=180,
        badge_reward_id=badge.id,
        suitable_age_bands=["6-8", "9-12", "13-15", "16-18", "18+"],
        suitable_skill_levels=["beginner", "intermediate", "advanced"],
        is_published=True,
    )
    db.session.add(track)
    db.session.flush()

    for idx, cid in enumerate(challenge_ids):
        prev_id = challenge_ids[idx - 1] if idx > 0 else None
        db.session.add(
            LearnTrackChallenge(
                track_id=track.id,
                challenge_id=cid,
                sort_order=idx,
                unlock_after_challenge_id=prev_id if idx > 0 else None,
            )
        )

    log_staff_action(
        actor_staff_user_id=actor_staff_user_id,
        action="learn_seed_explorer_curriculum",
        entity_type="learn_learning_track",
        entity_id=track.id,
        after={"challenge_ids": challenge_ids},
    )
    db.session.commit()
    return {"skipped": False, "track_id": track.id, "challenge_ids": challenge_ids}
