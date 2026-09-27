"""Seed lightweight Game rows for Quiz Galaxy shells (score targets)."""

from __future__ import annotations

from app import db
from app.games.galaxy_config import GALAXY_WORLDS
from app.models import Game


PLACEHOLDER_HTML = """<!DOCTYPE html><html><body>
<p>Quiz Galaxy shell — play via /play-galaxy/{shell}</p>
</body></html>
"""


def seed_galaxy_shell_games() -> dict:
    created = 0
    updated = 0
    for world in GALAXY_WORLDS:
        if (world.get("kind") or "subject") == "hub":
            continue
        title = f"Galaxy — {world['name']}"
        shell = world["shell"]
        subject = world["catalog_subjects"][0] if world.get("catalog_subjects") else world["label"]
        game = Game.query.filter_by(title=title, content_source="galaxy").first()
        if game is None:
            game = Game(
                title=title,
                description=world.get("fact") or world["name"],
                html_content=PLACEHOLDER_HTML.replace("{shell}", shell),
                max_score=20,
                age_range="9-19",
                subject=subject,
                content_source="galaxy",
                difficulty_level="medium",
                is_active=True,
            )
            db.session.add(game)
            created += 1
        else:
            game.description = world.get("fact") or world["name"]
            game.subject = subject
            game.is_active = True
            game.max_score = game.max_score or 20
            updated += 1
    db.session.commit()
    return {"created": created, "updated": updated, "worlds": len(GALAXY_WORLDS)}
