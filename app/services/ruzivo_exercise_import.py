"""Import Smart Learning / Ruzivo exercises as playable Game Portal quizzes."""

from __future__ import annotations

import json
import re
from html import unescape
from typing import Any

from app import db
from app.games.render_ruzivo_quiz import render_ruzivo_quiz_html
from app.games.quiz_titles import format_bank_title, format_learner_title
from app.models import Game, GameBankItem

# Ruzivo grade (4-7 primary, 8-13 HS) → portal age_range bands
GRADE_TO_AGE_RANGE: dict[int, str] = {
    4: "9-10",
    5: "9-10",
    6: "11-12",
    7: "11-12",
    8: "13-14",
    9: "13-14",
    10: "15-16",
    11: "15-16",
    12: "17-19",
    13: "17-19",
}

SUBJECT_NAME_MAP: dict[str, str] = {
    "english": "English Language",
    "english language": "English Language",
    "mathematics": "Mathematics",
    "maths": "Mathematics",
    "math": "Mathematics",
    "social science": "Social Science",
    "social studies": "Social Science",
    "science and technology": "Science and Technology",
    "science": "Combined Science",
    "combined science": "Combined Science",
    "geography": "Geography",
    "ict": "ICT",
    "information communication technology": "ICT",
    "shona": "Shona",
    "ndebele": "Ndebele",
}


def grade_to_age_range(grade: int | None) -> str | None:
    if grade is None:
        return None
    try:
        g = int(grade)
    except (TypeError, ValueError):
        return None
    return GRADE_TO_AGE_RANGE.get(g)


def map_subject_name(raw: str | None) -> str:
    text = unescape(str(raw or "").strip())
    if not text:
        return "General"
    key = text.lower()
    return SUBJECT_NAME_MAP.get(key, text.title())


_BARE_MATH = re.compile(
    r"(\\frac\s*\{[^{}]*\}\s*\{[^{}]*\}"
    r"|\\sqrt\s*(?:\[[^\]]*\])?\s*\{[^{}]*\}"
    r"|\\(?:times|div|pm|cdot|leq|geq|neq|pi)\b)"
)


def _strip_html(text: str) -> str:
    text = unescape(str(text or ""))
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def ensure_math_delimiters(text: str) -> str:
    """Wrap bare LaTeX commands (e.g. \\frac) so KaTeX can render fractions."""
    t = str(text or "")
    if not t:
        return t
    if "$" in t or r"\(" in t or r"\[" in t:
        return t
    if re.search(r"\\(frac|sqrt|times|div|pm|cdot|over)", t):
        return _BARE_MATH.sub(r"$\1$", t)
    return t


def parse_options(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw).strip()
    if not text:
        return []
    if text.startswith("[") or text.startswith("{"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
            if isinstance(parsed, dict):
                opts = parsed.get("options") or parsed.get("choices") or []
                return [str(x).strip() for x in opts if str(x).strip()]
        except json.JSONDecodeError:
            pass
    if "||" in text:
        return [p.strip() for p in text.split("||") if p.strip()]
    if "~|~" in text:
        return [p.strip() for p in text.split("~|~") if p.strip()]
    if "|" in text and text.count("|") >= 2:
        return [p.strip() for p in text.split("|") if p.strip()]
    if "\n" in text:
        return [p.strip() for p in text.splitlines() if p.strip()]
    return [text]


def parse_correct_index(options: list[str], answer_raw) -> int | None:
    if not options:
        return None
    answer = _strip_html(str(answer_raw or ""))
    if not answer:
        return None
    # Numeric index (0-based or 1-based)
    if answer.isdigit():
        idx = int(answer)
        if 0 <= idx < len(options):
            return idx
        if 1 <= idx <= len(options):
            return idx - 1
    # Letter A-D
    letter = answer.strip().upper()
    if len(letter) == 1 and letter.isalpha():
        idx = ord(letter) - ord("A")
        if 0 <= idx < len(options):
            return idx
    # Match option text
    norm_answer = answer.lower()
    for i, opt in enumerate(options):
        if _strip_html(opt).lower() == norm_answer:
            return i
    for i, opt in enumerate(options):
        if norm_answer and norm_answer in _strip_html(opt).lower():
            return i
    return None


def _fetch_subjects(conn, hs: bool) -> dict[int, str]:
    table = "tblsubjects_hs" if hs else "tblsubjects"
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT subject_id, subject_name FROM {table}")
        rows = cur.fetchall()
    finally:
        cur.close()
    out: dict[int, str] = {}
    for row in rows:
        if isinstance(row, dict):
            out[int(row["subject_id"])] = row.get("subject_name") or ""
        else:
            out[int(row[0])] = str(row[1] or "")
    return out


def fetch_exercises(hs: bool = False, grade: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
    from app.routes import get_ruzivo_conn

    ex_table = "tblexercise_hs" if hs else "tblexercise"
    q_table = "tblquestions_hs" if hs else "tblquestions"
    source = "hs" if hs else "primary"
    conn = get_ruzivo_conn()
    subjects = _fetch_subjects(conn, hs)
    grade_clause = ""
    ex_params: list[Any] = []
    if grade is not None:
        grade_clause = " AND e.grade = %s "
        ex_params.append(int(grade))

    ex_sql = f"""
        SELECT e.ex_id, e.grade, e.subject, e.exercise, e.qstn_type, e.instruction
        FROM {ex_table} e
        WHERE e.flag != 'D' AND e.active = 'Yes'
          AND e.qstn_type != 'Open'
          {grade_clause}
        ORDER BY e.ex_id
        LIMIT %s
    """
    ex_params.append(int(limit))
    cur = conn.cursor()
    try:
        cur.execute(ex_sql, ex_params)
        exercises = cur.fetchall()
        if not exercises:
            return []
        ex_ids = [int(row["ex_id"] if isinstance(row, dict) else row[0]) for row in exercises]
        placeholders = ",".join(["%s"] * len(ex_ids))
        q_sql = f"""
            SELECT q.qstn_id, q.category_id, q.question, q.ans_type, q.options, q.answer, q.hint
            FROM {q_table} q
            WHERE q.flag != 'D' AND q.active = 'Yes'
              AND q.category = 'Exercise'
              AND q.category_id IN ({placeholders})
              AND q.ans_type NOT IN ('OpenText', 'Open')
        """
        cur.execute(q_sql, ex_ids)
        question_rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    questions_by_ex: dict[int, list] = {eid: [] for eid in ex_ids}
    for row in question_rows:
        if not isinstance(row, dict):
            continue
        ex_id = int(row["category_id"])
        options = parse_options(row.get("options"))
        correct = parse_correct_index(options, row.get("answer"))
        if len(options) < 2 or correct is None:
            continue
        questions_by_ex.setdefault(ex_id, []).append({
            "qstn_id": int(row["qstn_id"]),
            "prompt": ensure_math_delimiters(_strip_html(row.get("question") or "")),
            "options": [ensure_math_delimiters(_strip_html(o)) for o in options],
            "correctIndex": correct,
            "explain": ensure_math_delimiters(_strip_html(row.get("hint") or "")) or "Review this topic on Smart Learning.",
        })

    grouped: list[dict[str, Any]] = []
    for row in exercises:
        if not isinstance(row, dict):
            continue
        ex_id = int(row["ex_id"])
        qs = questions_by_ex.get(ex_id) or []
        if not qs:
            continue
        subj_id = int(row.get("subject") or 0)
        grouped.append({
            "ex_id": ex_id,
            "grade": int(row.get("grade") or 0),
            "subject_id": subj_id,
            "subject_name": map_subject_name(subjects.get(subj_id, "")),
            "exercise": _strip_html(row.get("exercise") or ""),
            "qstn_type": row.get("qstn_type"),
            "instruction": _strip_html(row.get("instruction") or ""),
            "ruzivo_source": source,
            "questions": qs,
        })
    return grouped


def upsert_ruzivo_game(spec: dict[str, Any]) -> tuple[Game, bool]:
    """Create or update a Game from a grouped exercise spec. Returns (game, created)."""
    age_range = grade_to_age_range(spec.get("grade"))
    if not age_range:
        raise ValueError(f"Unsupported grade: {spec.get('grade')}")

    render_spec = dict(spec)
    render_spec["age_range"] = age_range
    title = format_learner_title(spec.get("exercise") or "Quiz", spec.get("grade"))
    html = render_ruzivo_quiz_html(render_spec)
    q_count = min(len(spec["questions"]), 10)
    max_score = q_count

    game = Game.query.filter_by(
        ruzivo_ex_id=spec["ex_id"],
        ruzivo_source=spec["ruzivo_source"],
    ).first()
    created = game is None
    if game is None:
        game = Game(
            title=title,
            description=spec.get("instruction") or f"Smart Learning exercise for grade {spec['grade']}.",
            html_content=html,
            max_score=max_score,
            age_range=age_range,
            subject=spec.get("subject_name"),
            grade=int(spec.get("grade") or 0),
            content_source="ruzivo",
            ruzivo_ex_id=int(spec["ex_id"]),
            ruzivo_source=spec["ruzivo_source"],
            difficulty_level="medium",
            is_active=True,
        )
        db.session.add(game)
        db.session.flush()
    else:
        game.title = title
        game.description = spec.get("instruction") or game.description
        game.html_content = html
        game.max_score = max_score
        game.age_range = age_range
        game.subject = spec.get("subject_name")
        game.grade = int(spec.get("grade") or 0)
        game.content_source = "ruzivo"
        game.is_active = True

    # Bank item from first question
    q0 = spec["questions"][0]
    bank = GameBankItem.query.filter_by(game_id=game.id, slug="featured").first()
    if bank is None:
        bank = GameBankItem(game_id=game.id, slug="featured")
        db.session.add(bank)
    bank.subject = game.subject
    bank.age_range = game.age_range
    bank.item_kind = "quiz"
    bank.title = format_bank_title(spec.get("exercise") or "Quiz")
    bank.prompt = q0["prompt"]
    bank.payload_json = {
        "options": q0["options"],
        "correct_index": q0["correctIndex"],
        "explain": q0.get("explain") or "",
    }
    bank.points_default = 5
    bank.is_active = True
    return game, created


def sync_ruzivo_exercises(
    *,
    grade: int | None = None,
    hs: bool | None = None,
    limit_per_band: int = 100,
) -> dict[str, int]:
    """Import/update Ruzivo exercises into Game catalog."""
    stats = {"created": 0, "updated": 0, "skipped": 0, "fetched": 0}
    bands: list[bool] = []
    if hs is True:
        bands = [True]
    elif hs is False:
        bands = [False]
    else:
        bands = [False, True]

    for is_hs in bands:
        specs = fetch_exercises(hs=is_hs, grade=grade, limit=limit_per_band)
        stats["fetched"] += len(specs)
        for spec in specs:
            try:
                _, created = upsert_ruzivo_game(spec)
                if created:
                    stats["created"] += 1
                else:
                    stats["updated"] += 1
            except Exception:
                stats["skipped"] += 1
    db.session.commit()
    return stats
