"""Export/import General Knowledge games as a JSON pack (no Ruzivo/Smart Learning)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_

from app import db
from app.models import Game, GameBankItem

PACK_FORMAT = "akello_game_pack"
PACK_VERSION = 1


def _is_ruzivo_game(game: Game | None = None, payload: dict[str, Any] | None = None) -> bool:
    if game is not None:
        source = (getattr(game, "content_source", None) or "").strip().lower()
        if source == "ruzivo":
            return True
        if getattr(game, "ruzivo_ex_id", None):
            return True
    if payload:
        source = str(payload.get("content_source") or "").strip().lower()
        if source == "ruzivo":
            return True
        if payload.get("ruzivo_ex_id"):
            return True
    return False


def _serialize_bank_item(item: GameBankItem) -> dict[str, Any]:
    return {
        "slug": item.slug,
        "subject": item.subject,
        "age_range": item.age_range,
        "item_kind": item.item_kind or "quiz",
        "title": item.title,
        "prompt": item.prompt,
        "payload_json": item.payload_json or {},
        "points_default": item.points_default,
        "sort_order": item.sort_order,
        "is_active": bool(item.is_active),
    }


def _serialize_game(game: Game) -> dict[str, Any]:
    return {
        "title": game.title,
        "description": game.description or "",
        "html_content": game.html_content or "",
        "max_score": game.max_score,
        "age_range": game.age_range,
        "subject": game.subject,
        "content_source": "general_knowledge",
        "grade": getattr(game, "grade", None),
        "difficulty_level": game.difficulty_level,
        "is_active": bool(game.is_active),
        "bank_items": [_serialize_bank_item(item) for item in (game.bank_items or [])],
    }


def query_general_knowledge_games() -> list[Game]:
    source_col = Game.content_source
    query = Game.query.filter(
        or_(source_col.is_(None), source_col != "ruzivo"),
        Game.ruzivo_ex_id.is_(None),
    )
    return query.order_by(Game.subject.asc(), Game.title.asc(), Game.id.asc()).all()


def build_game_pack(games: list[Game] | None = None) -> dict[str, Any]:
    rows = games if games is not None else query_general_knowledge_games()
    pack_games = [_serialize_game(g) for g in rows if not _is_ruzivo_game(game=g)]
    return {
        "format": PACK_FORMAT,
        "version": PACK_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "games": pack_games,
    }


def _find_existing_game(title: str, age_range: str | None, subject: str | None) -> Game | None:
    game = Game.query.filter_by(title=title, age_range=age_range, subject=subject).first()
    if game is None and subject:
        game = Game.query.filter_by(title=title, age_range=age_range).first()
    return game


def _upsert_bank_items(game: Game, bank_items: list[dict[str, Any]]) -> int:
    count = 0
    for row in bank_items or []:
        slug = (row.get("slug") or "").strip()
        item_title = (row.get("title") or "").strip()
        if not slug or not item_title:
            continue
        item = GameBankItem.query.filter_by(game_id=game.id, slug=slug).first()
        if item is None:
            item = GameBankItem(game_id=game.id, slug=slug)
            db.session.add(item)
        item.subject = row.get("subject") or game.subject
        item.age_range = row.get("age_range") or game.age_range
        item.item_kind = row.get("item_kind") or "quiz"
        item.title = item_title
        item.prompt = row.get("prompt")
        item.payload_json = row.get("payload_json") or {}
        item.points_default = int(row.get("points_default") or 5)
        item.sort_order = int(row.get("sort_order") or 0)
        item.is_active = bool(row.get("is_active", True))
        count += 1
    return count


def import_game_pack(pack: dict[str, Any], *, created_by: int | None = None) -> dict[str, Any]:
    if not isinstance(pack, dict):
        raise ValueError("Pack must be a JSON object.")
    if pack.get("format") != PACK_FORMAT:
        raise ValueError('Invalid pack: expected format "akello_game_pack".')
    version = pack.get("version")
    if version not in (None, PACK_VERSION, 1):
        raise ValueError(f"Unsupported pack version: {version}")

    games = pack.get("games")
    if not isinstance(games, list):
        raise ValueError('Pack must include a "games" array.')

    stats = {"created": 0, "updated": 0, "skipped": 0, "errors": []}
    for index, payload in enumerate(games):
        if not isinstance(payload, dict):
            stats["skipped"] += 1
            stats["errors"].append({"index": index, "error": "Game entry is not an object."})
            continue
        if _is_ruzivo_game(payload=payload):
            stats["skipped"] += 1
            stats["errors"].append({
                "index": index,
                "title": payload.get("title"),
                "error": "Skipped Ruzivo/Smart Learning game.",
            })
            continue

        title = (payload.get("title") or "").strip()
        html_content = (payload.get("html_content") or "").strip()
        if not title or not html_content:
            stats["skipped"] += 1
            stats["errors"].append({"index": index, "title": title, "error": "Title and HTML content are required."})
            continue

        age_range = (payload.get("age_range") or "").strip() or None
        subject = (payload.get("subject") or "").strip() or None
        description = (payload.get("description") or "").strip()
        difficulty = (payload.get("difficulty_level") or "").strip() or None
        grade = payload.get("grade")
        try:
            grade = int(grade) if grade is not None and str(grade).strip() != "" else None
        except (TypeError, ValueError):
            grade = None
        max_score = payload.get("max_score")
        try:
            max_score = int(max_score) if max_score not in (None, "") else None
        except (TypeError, ValueError):
            max_score = None

        try:
            nested = db.session.begin_nested()
            existing = _find_existing_game(title, age_range, subject)
            if existing is not None and _is_ruzivo_game(game=existing):
                nested.rollback()
                stats["skipped"] += 1
                stats["errors"].append({
                    "index": index,
                    "title": title,
                    "error": "Skipped: matching production game is a Ruzivo import.",
                })
                continue

            if existing is None:
                game = Game(
                    title=title,
                    description=description,
                    html_content=html_content,
                    max_score=max_score,
                    age_range=age_range,
                    subject=subject,
                    content_source="general_knowledge",
                    grade=grade,
                    difficulty_level=difficulty,
                    is_active=bool(payload.get("is_active", True)),
                    created_by=created_by,
                )
                db.session.add(game)
                db.session.flush()
                stats["created"] += 1
            else:
                game = existing
                game.description = description
                game.html_content = html_content
                game.max_score = max_score
                game.age_range = age_range
                game.subject = subject
                game.content_source = "general_knowledge"
                game.grade = grade
                game.difficulty_level = difficulty
                game.is_active = bool(payload.get("is_active", True))
                stats["updated"] += 1

            _upsert_bank_items(game, payload.get("bank_items") or [])
            nested.commit()
        except Exception as exc:
            nested.rollback()
            stats["skipped"] += 1
            stats["errors"].append({"index": index, "title": title, "error": str(exc)})

    db.session.commit()
    return stats
