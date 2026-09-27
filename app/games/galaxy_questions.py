"""Prefer General Knowledge bank items; fill gaps with Caimex-generated quizzes."""

from __future__ import annotations

import random
from typing import Any

from app.models import Game, GameBankItem, GameUser

# UTF-8 misread as Windows-1252 / Latin-1. ASCII-only source via \\u escapes
# (literal mojibake strings contain curly quotes that break Python parsers).
_MOJIBAKE_MARKERS = ("\u00c3", "\u00e2", "\u00c2")
_MOJIBAKE_REPLACEMENTS = (
    # en-dash U+2013 → UTF-8 E2 80 93 → CP1252 â € “
    ("\u00e2\u20ac\u201c", "\u2013"),
    # em-dash U+2014 → UTF-8 E2 80 94 → CP1252 â € ”
    ("\u00e2\u20ac\u201d", "\u2014"),
    # minus U+2212 → UTF-8 E2 88 92 → CP1252 â ˆ ’
    ("\u00e2\u02c6\u2019", "\u2212"),
    # × U+00D7 → UTF-8 C3 97 → CP1252 Ã —
    ("\u00c3\u2014", "\u00d7"),
    # × as Ã + × (already half-decoded)
    ("\u00c3\u00d7", "\u00d7"),
    # ÷ U+00F7 → UTF-8 C3 B7 → CP1252 Ã ·
    ("\u00c3\u00b7", "\u00f7"),
    # ± U+00B1 → UTF-8 C2 B1 → CP1252 Â ±
    ("\u00c2\u00b1", "\u00b1"),
    # ’ ‘ “ ” …
    ("\u00e2\u20ac\u2122", "'"),
    ("\u00e2\u20ac\u2018", "'"),
    ("\u00e2\u20ac\u2019", "'"),
    ("\u00e2\u20ac\u0153", '"'),
    ("\u00e2\u20ac\u2026", "\u2026"),
    # °
    ("\u00c2\u00b0", "\u00b0"),
    ("\u00c2 ", " "),
)


def sanitize_quiz_text(value: Any) -> str:
    """Repair mojibake and return clean quiz text."""
    if value is None:
        return ""
    text = str(value)
    if not text:
        return text
    if any(m in text for m in _MOJIBAKE_MARKERS):
        for encoding in ("cp1252", "latin-1"):
            try:
                fixed = text.encode(encoding).decode("utf-8")
                if fixed and "\ufffd" not in fixed:
                    text = fixed
                    break
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        for bad, good in _MOJIBAKE_REPLACEMENTS:
            if bad in text:
                text = text.replace(bad, good)
        text = text.replace("\u00c2", "")
    return text


def shuffle_mcq_options(options: list[Any], correct_index: Any) -> tuple[list[str], int]:
    """Shuffle choices and return the new correct index (handles duplicate labels)."""
    opts = [sanitize_quiz_text(o) for o in (options or [])]
    if len(opts) < 2:
        return opts, 0
    try:
        ci = int(correct_index)
    except (TypeError, ValueError):
        ci = 0
    if ci < 0 or ci >= len(opts):
        ci = 0
    order = list(range(len(opts)))
    random.shuffle(order)
    shuffled = [opts[i] for i in order]
    new_ci = order.index(ci)
    return shuffled, new_ci


def normalize_bank_item(item: GameBankItem, game: Game | None = None) -> dict[str, Any] | None:
    payload = item.payload_json or {}
    prompt = sanitize_quiz_text((item.prompt or "").strip() or (payload.get("prompt") or "").strip())
    if not prompt:
        return None

    options = payload.get("options")
    correct_index = payload.get("correct_index")
    if correct_index is None:
        correct_index = payload.get("correctIndex")
    kind = (item.item_kind or "quiz").strip().lower()

    if kind == "question":
        accepted = payload.get("accepted_answers") or payload.get("accepted") or []
        qkind = (payload.get("kind") or "short").strip().lower()
        if qkind == "true_false":
            options = ["True", "False"]
            ans = str((accepted[0] if accepted else "True")).strip().lower()
            correct_index = 0 if ans.startswith("t") else 1
        elif accepted:
            correct = str(accepted[0])
            distractors = [str(a) for a in accepted[1:3]]
            while len(distractors) < 3:
                distractors.append(f"Option {len(distractors) + 2}")
            options = [correct] + distractors[:3]
            # shuffled below with all quiz kinds
            correct_index = 0
        else:
            return None

    if not isinstance(options, list) or len(options) < 2:
        return None
    try:
        correct_index = int(correct_index)
    except (TypeError, ValueError):
        correct_index = 0
    if correct_index < 0 or correct_index >= len(options):
        correct_index = 0

    options, correct_index = shuffle_mcq_options(options, correct_index)

    difficulty = None
    if game is not None:
        difficulty = (game.difficulty_level or "").strip().lower() or None

    return {
        "id": f"bank-{item.id}",
        "prompt": prompt,
        "options": options,
        "correctIndex": correct_index,
        "explain": sanitize_quiz_text(payload.get("explain") or ""),
        "game_id": item.game_id,
        "bank_item_id": item.id,
        "difficulty": difficulty,
        "subject": item.subject or (game.subject if game else None),
        "source": "general_knowledge",
    }


def _collect_from_query(q) -> list[dict[str, Any]]:
    rows = q.all()
    out: list[dict[str, Any]] = []
    games_cache: dict[int, Game] = {}
    for item in rows:
        game = games_cache.get(item.game_id)
        if game is None:
            game = Game.query.get(item.game_id)
            if game:
                games_cache[item.game_id] = game
        normalized = normalize_bank_item(item, game)
        if normalized:
            src = (getattr(game, "content_source", None) or "general_knowledge").strip().lower()
            normalized["source"] = src if src != "galaxy" else "catalog"
            out.append(normalized)
    return out


def fetch_galaxy_questions(
    *,
    catalog_subjects: list[str],
    age_ranges: list[str],
    difficulty: str | None = None,
    limit: int = 30,
    prefer_general_knowledge: bool = True,
) -> list[dict[str, Any]]:
    """
    Pull quiz items for subject+age.
    Prefer General Knowledge catalog first, then other non-galaxy sources.
    """
    limit = max(8, min(60, int(limit or 30)))
    subjects = [s for s in catalog_subjects if s]
    if not subjects or not age_ranges:
        return []

    base = (
        GameBankItem.query.join(Game, GameBankItem.game_id == Game.id)
        .filter(Game.is_active.is_(True))
        .filter(GameBankItem.is_active.is_(True))
        .filter(GameBankItem.item_kind.in_(("quiz", "question")))
        .filter(Game.age_range.in_(age_ranges))
        .filter(Game.subject.in_(subjects))
        .filter(Game.content_source != "galaxy")
    )

    diff = (difficulty or "").strip().lower()
    if diff in ("easy", "medium", "hard"):
        preferred_diff = base.filter(Game.difficulty_level == diff)
    else:
        preferred_diff = base

    out: list[dict[str, Any]] = []
    seen_prompts: set[str] = set()

    def _extend(rows: list[dict[str, Any]]) -> None:
        for row in rows:
            key = (row.get("prompt") or "").strip().lower()
            if not key or key in seen_prompts:
                continue
            seen_prompts.add(key)
            out.append(row)

    if prefer_general_knowledge:
        gk = preferred_diff.filter(Game.content_source == "general_knowledge")
        _extend(_collect_from_query(gk))
        if len(out) < limit:
            _extend(_collect_from_query(preferred_diff))
    else:
        _extend(_collect_from_query(preferred_diff))

    # Widen difficulty if still thin
    if len(out) < max(8, limit // 2) and diff in ("easy", "medium", "hard"):
        _extend(_collect_from_query(base))

    random.shuffle(out)
    return out[:limit]


def age_ranges_for_user(game_user: GameUser, include_cross: bool) -> list[str]:
    age = int(game_user.age or 0)
    if age < 9:
        return ["Infants"]
    if 9 <= age <= 10:
        ranges = ["9-10"]
    elif 11 <= age <= 12:
        ranges = ["11-12"]
    elif 13 <= age <= 14:
        ranges = ["13-14"]
    elif 15 <= age <= 16:
        ranges = ["15-16"]
    elif 17 <= age <= 19:
        ranges = ["17-19"]
    else:
        return ["Youths & older"]
    if include_cross:
        ranges.append("9-19")
    return ranges
