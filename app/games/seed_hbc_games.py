"""Upsert HBC subject-titled games + bank items into the Game Events catalog."""

from __future__ import annotations

from pathlib import Path

from app import db
from app.games.hbc_catalog import HBC_GAME_SPECS
from app.games.render_hbc_game import generate_game_bundle
from app.models import Game, GameBankItem

HBC_HTML_DIR = Path(__file__).resolve().parent.parent / "static" / "games" / "hbc"

LEGACY_TITLE_PREFIXES = ("STEM:", "HBC:")


def _write_html(spec: dict, html: str) -> Path:
    path = HBC_HTML_DIR / spec["filename"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def _upsert_bank_items(game: Game, bank_items: list[dict]) -> int:
    count = 0
    for row in bank_items:
        item = GameBankItem.query.filter_by(game_id=game.id, slug=row["slug"]).first()
        if item is None:
            item = GameBankItem(game_id=game.id, slug=row["slug"])
            db.session.add(item)
        item.subject = game.subject
        item.age_range = game.age_range
        item.item_kind = row.get("item_kind") or "quiz"
        item.title = row["title"]
        item.prompt = row.get("prompt")
        item.payload_json = row.get("payload_json") or {}
        item.points_default = int(row.get("points_default") or 5)
        item.sort_order = int(row.get("sort_order") or 0)
        item.is_active = True
        count += 1
    return count


def seed_hbc_games() -> dict:
    """Generate/write HTML, upsert games by title+age+subject, seed bank items."""
    created = 0
    updated = 0
    skipped = 0
    bank_upserted = 0
    legacy_deactivated = 0

    for spec in HBC_GAME_SPECS:
        try:
            bundle = generate_game_bundle(spec)
            _write_html(spec, bundle["html"])
        except Exception:
            skipped += 1
            continue

        html_content = bundle["html"]
        game = Game.query.filter_by(
            title=spec["title"],
            age_range=spec["age_range"],
            subject=spec["subject"],
        ).first()
        if game is None:
            # Also match by title alone if subject was null historically
            game = Game.query.filter_by(title=spec["title"], age_range=spec["age_range"]).first()

        if game is None:
            game = Game(
                title=spec["title"],
                description=spec["description"],
                html_content=html_content,
                max_score=spec["max_score"],
                age_range=spec["age_range"],
                subject=spec["subject"],
                difficulty_level=spec["difficulty_level"],
                content_source="general_knowledge",
                is_active=True,
                created_by=None,
            )
            db.session.add(game)
            db.session.flush()
            created += 1
        else:
            game.description = spec["description"]
            game.html_content = html_content
            game.max_score = spec["max_score"]
            game.age_range = spec["age_range"]
            game.subject = spec["subject"]
            game.difficulty_level = spec["difficulty_level"]
            game.content_source = "general_knowledge"
            game.is_active = True
            updated += 1

        bank_upserted += _upsert_bank_items(game, bundle["bank_items"])

    # Deactivate old STEM:/HBC: one-off titles not in the new subject catalog
    catalog_titles = {s["title"] for s in HBC_GAME_SPECS}
    legacy = Game.query.filter(Game.title.isnot(None)).all()
    for game in legacy:
        title = game.title or ""
        if title in catalog_titles:
            continue
        if title.startswith(LEGACY_TITLE_PREFIXES):
            if game.is_active:
                game.is_active = False
                legacy_deactivated += 1

    db.session.commit()
    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "bank_upserted": bank_upserted,
        "legacy_deactivated": legacy_deactivated,
        "catalog_size": len(HBC_GAME_SPECS),
    }


# Keep old import path working
def seed_stem_games() -> dict:
    return seed_hbc_games()
