"""Upsert STEM/HBC HTML games into the Game Events catalog."""

from app.games.seed_hbc_games import seed_hbc_games, seed_stem_games

__all__ = ["seed_hbc_games", "seed_stem_games"]
