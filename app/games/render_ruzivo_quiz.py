"""Render a deferred-feedback quiz HTML game from imported Smart Learning exercise content."""

from __future__ import annotations

import json
from typing import Any

from app.games.render_hbc_game import render_hbc_game_html
from app.games.quiz_titles import format_learner_title


def render_ruzivo_quiz_html(spec: dict[str, Any]) -> str:
    questions = spec.get("questions") or []
    pool = []
    for i, q in enumerate(questions[:12], 1):
        pool.append({
            "id": f"sl_{spec.get('ex_id')}_{q.get('qstn_id', i)}",
            "prompt": q.get("prompt") or f"Question {i}",
            "options": list(q.get("options") or []),
            "correctIndex": int(q.get("correctIndex") or 0),
            "explain": q.get("explain") or "Review this topic on Smart Learning.",
            "hintKey": "generic",
        })
    total = min(len(pool), 10)
    content = {
        "learningArea": spec.get("subject_name") or "Smart Learning",
        "topic": spec.get("exercise") or "Smart Learning Quiz",
        "ageRange": spec.get("age_range") or "",
        "totalRounds": total,
        "maxScore": total,
        "questionPool": pool,
        "hints": {"generic": "Think about what you learned in class."},
    }
    content_json = json.dumps(content, ensure_ascii=False)
    title = format_learner_title(spec.get("exercise") or "Quiz", spec.get("grade"))
    pseudo = {
        "title": title,
        "subject": spec.get("subject_name") or "Smart Learning",
        "topic_title": spec.get("exercise") or "Quiz",
        "topic_slug": "smart_learning",
        "age_range": spec.get("age_range") or "9-19",
    }
    base = render_hbc_game_html({
        **pseudo,
        "description": "",
        "max_score": total,
        "difficulty_level": "medium",
    })
    marker = "const CONTENT = "
    start = base.find(marker)
    if start == -1:
        return base
    end = base.find(";\n\n    function initializeGameSession", start)
    if end == -1:
        return base
    return base[: start + len(marker)] + content_json + base[end:]
