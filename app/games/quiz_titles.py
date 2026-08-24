"""Learner-facing quiz title helpers for Smart Learning imports."""

from __future__ import annotations

import re
from html import unescape


def _strip_html(text: str) -> str:
    text = unescape(str(text or ""))
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def format_learner_title(exercise: str, grade: int | None = None) -> str:
    """Human-friendly Smart Learning quiz title (no 'Ruzivo' branding)."""
    clean = _strip_html(exercise or "Quiz")
    clean = clean.replace("-", " ").replace("_", " ")
    clean = re.sub(r"\s+", " ", clean).strip(" -·.")
    parts = []
    for w in clean.split(" "):
        if not w:
            continue
        if w.isupper() and len(w) <= 4:
            parts.append(w)
        else:
            parts.append(w[:1].upper() + w[1:].lower() if len(w) > 1 else w.upper())
    pretty = " ".join(parts) or "Quiz"
    if grade is not None:
        try:
            return f"Smart Learning: {pretty} · Grade {int(grade)}"
        except (TypeError, ValueError):
            pass
    return f"Smart Learning: {pretty}"


def format_bank_title(exercise: str) -> str:
    clean = format_learner_title(exercise, None).replace("Smart Learning: ", "", 1)
    return f"{clean} — featured"


def display_game_title(title: str | None, *, content_source: str | None = None, grade: int | None = None) -> str:
    """Learner-facing title; rewrites legacy 'Ruzivo:' prefixes to Smart Learning."""
    raw = (title or "").strip()
    if not raw:
        return raw
    src = (content_source or "").strip().lower()
    if src == "ruzivo" or raw.lower().startswith("ruzivo:"):
        rest = raw
        if ":" in rest and rest.lower().split(":", 1)[0].strip() in ("ruzivo", "smart learning"):
            rest = rest.split(":", 1)[1].strip()
        rest = re.sub(r"\s*\(G\d+\)\s*$", "", rest, flags=re.I).strip()
        rest = re.sub(r"\s*·\s*Grade\s*\d+\s*$", "", rest, flags=re.I).strip()
        return format_learner_title(rest, grade)
    return raw
