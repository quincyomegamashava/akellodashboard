"""Caimex OpenAI-compatible client for Quiz Galaxy pacing and AI quizzes."""

from __future__ import annotations

import json
import re
from typing import Any

import requests
from flask import current_app


def _config(key: str, default: str | None = None) -> str | None:
    try:
        return current_app.config.get(key) or default
    except RuntimeError:
        return default


def caimex_configured() -> bool:
    key = (_config("CAIMEX_API_KEY") or "").strip()
    return bool(key)


def generate_quiz_questions(
    *,
    age: int | None,
    subject: str,
    difficulty: str,
    level: int,
    count: int = 10,
    seed_examples: list[dict[str, Any]] | None = None,
    avoid_prompts: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Ask Caimex for MCQ quizzes related to subject/level.
    Returns normalized dicts: id, prompt, options, correctIndex, explain, source=ai.
    """
    count = max(1, min(20, int(count or 10)))
    difficulty = (difficulty or "medium").lower()
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"
    if not caimex_configured():
        return []

    base = (_config("CAIMEX_BASE_URL") or "https://caimex.econetai.co.zw:2052/v1").rstrip("/")
    model = (_config("CAIMEX_MODEL") or "caimex/auto").strip()
    api_key = (_config("CAIMEX_API_KEY") or "").strip()

    examples = []
    for ex in (seed_examples or [])[:3]:
        examples.append({
            "prompt": ex.get("prompt") or ex.get("q"),
            "options": ex.get("options") or ex.get("choices"),
            "correctIndex": ex.get("correctIndex", ex.get("answer", 0)),
        })

    avoid = []
    for p in (avoid_prompts or [])[:40]:
        s = str(p or "").strip()
        if s and s not in avoid:
            avoid.append(s[:160])

    system = (
        "You write multiple-choice school quiz questions for African learners. "
        "Return ONLY a JSON object: {\"questions\":[{\"prompt\":str,\"options\":[str,str,str,str],"
        "\"correctIndex\":int,\"explain\":str}]}. "
        "Exactly 4 options per question. correctIndex is 0-based. "
        "Questions must match the subject and difficulty. Keep language age-appropriate. "
        "Every question must be NEW — never repeat or paraphrase avoided prompts."
    )
    user = (
        f"Create {count} brand-new {difficulty} {subject} quiz questions for age {age or '10-14'}, "
        f"progression level {level}. Cover varied topics within the subject. "
        "Do not reuse earlier quiz wording."
    )
    if examples:
        user += " Style examples (do not repeat): " + json.dumps(examples)[:1000]
    if avoid:
        user += " Forbidden prompts (do not repeat or lightly rephrase): " + json.dumps(avoid)[:1800]

    try:
        resp = requests.post(
            f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.75,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=35,
        )
        resp.raise_for_status()
        data = resp.json()
        content = (
            ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
            or ""
        )
        parsed = _parse_json_object(content)
        raw_list: list[Any] = []
        if isinstance(parsed, dict):
            raw_list = parsed.get("questions") or parsed.get("items") or []
        elif isinstance(parsed, list):
            raw_list = parsed
        if not isinstance(raw_list, list):
            return []

        avoid_l = {a.lower() for a in avoid}
        out: list[dict[str, Any]] = []
        for i, raw in enumerate(raw_list):
            if not isinstance(raw, dict):
                continue
            prompt = str(raw.get("prompt") or raw.get("q") or "").strip()
            options = raw.get("options") or raw.get("choices") or []
            if not prompt or not isinstance(options, list) or len(options) < 2:
                continue
            if prompt.lower() in avoid_l:
                continue
            options = [str(o) for o in options[:4]]
            while len(options) < 4:
                options.append(f"Option {len(options) + 1}")
            try:
                ci = int(raw.get("correctIndex", raw.get("answer", 0)))
            except (TypeError, ValueError):
                ci = 0
            if ci < 0 or ci >= len(options):
                ci = 0
            try:
                from app.games.galaxy_questions import shuffle_mcq_options
                options, ci = shuffle_mcq_options(options, ci)
            except Exception:
                pass
            out.append({
                "id": f"ai-{level}-{i}-{abs(hash(prompt)) % 10_000_000}",
                "prompt": prompt,
                "options": options,
                "correctIndex": ci,
                "explain": str(raw.get("explain") or "")[:300],
                "difficulty": difficulty,
                "subject": subject,
                "source": "ai",
            })
            avoid_l.add(prompt.lower())
        return out[:count]
    except Exception as exc:
        try:
            current_app.logger.warning("Caimex generate_quiz_questions failed: %s", exc)
        except Exception:
            pass
        return []


def suggest_next_progress(
    *,
    age: int | None,
    subject: str,
    shell: str,
    current_level: int,
    current_difficulty: str,
    score_pct: float,
) -> dict[str, Any]:
    """
    Ask Caimex for next level + difficulty. Falls back to deterministic rules
    when unset/unreachable. Never used for multiplayer/races.
    """
    difficulty = (current_difficulty or "medium").lower()
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"
    level = max(1, int(current_level or 1))

    fallback = _fallback(level, difficulty, score_pct)
    if not caimex_configured():
        fallback["source"] = "fallback_no_key"
        return fallback

    base = (_config("CAIMEX_BASE_URL") or "https://caimex.econetai.co.zw:2052/v1").rstrip("/")
    model = (_config("CAIMEX_MODEL") or "caimex/auto").strip()
    api_key = (_config("CAIMEX_API_KEY") or "").strip()

    system = (
        "You pace educational quiz difficulty for African school learners. "
        "Return ONLY compact JSON with keys: next_level (int >= 1), "
        "difficulty (easy|medium|hard), coaching_blurb (short kid-friendly string). "
        "Do not invent quiz questions."
    )
    user = (
        f"age={age}, subject={subject}, shell={shell}, "
        f"current_level={level}, current_difficulty={difficulty}, "
        f"last_score_percent={round(score_pct, 1)}. "
        "If score >= 80 raise challenge slightly; if <= 40 ease slightly; else hold."
    )

    try:
        resp = requests.post(
            f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()
        content = (
            ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
            or ""
        )
        parsed = _parse_json_object(content)
        if not isinstance(parsed, dict):
            fallback["source"] = "fallback_parse"
            return fallback
        next_level = int(parsed.get("next_level") or level)
        next_diff = str(parsed.get("difficulty") or difficulty).lower()
        if next_diff not in ("easy", "medium", "hard"):
            next_diff = difficulty
        passed = score_pct >= 70
        if passed:
            next_level = max(next_level, level + 1)
        else:
            next_level = level
        return {
            "next_level": max(1, next_level),
            "difficulty": next_diff,
            "coaching_blurb": str(parsed.get("coaching_blurb") or fallback["coaching_blurb"])[:240],
            "passed": passed,
            "source": "caimex",
        }
    except Exception as exc:
        try:
            current_app.logger.warning("Caimex suggest_next_progress failed: %s", exc)
        except Exception:
            pass
        fallback["source"] = "fallback_error"
        return fallback


def _fallback(level: int, difficulty: str, score_pct: float) -> dict[str, Any]:
    order = ["easy", "medium", "hard"]
    idx = order.index(difficulty) if difficulty in order else 1
    next_level = level
    passed = score_pct >= 70
    if passed:
        next_level = level + 1
        idx = min(2, idx + 1)
        blurb = "Level cleared! Ready for the next challenge."
    elif score_pct <= 40:
        idx = max(0, idx - 1)
        blurb = "Keep going — try this level again. You can do it!"
    else:
        blurb = "Close one! Play this level again to clear it."
    return {
        "next_level": max(1, next_level),
        "difficulty": order[idx],
        "coaching_blurb": blurb,
        "passed": passed,
        "source": "fallback",
    }


def _parse_json_object(text: str) -> dict[str, Any] | list[Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    # Strip markdown fences if present
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, (dict, list)):
            return obj
    except json.JSONDecodeError:
        pass
    # Find outermost JSON object/array
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start >= 0 and end > start:
            try:
                obj = json.loads(text[start : end + 1])
                if isinstance(obj, (dict, list)):
                    return obj
            except json.JSONDecodeError:
                continue
    return None
