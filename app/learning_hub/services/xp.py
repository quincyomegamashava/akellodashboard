"""Weighted XP calculation for attempts."""

from __future__ import annotations

DIFFICULTY_MULTIPLIER = {
    "beginner": 1.0,
    "intermediate": 1.25,
    "advanced": 1.5,
}


def streak_bonus_multiplier(streak_days: int) -> float:
    if streak_days <= 0:
        return 1.0
    # Cap bonus to avoid runaway XP
    return min(1.0 + 0.02 * min(streak_days, 14), 1.28)


def compute_awarded_xp(
    *,
    base_points: int,
    difficulty: str,
    streak_days: int,
    first_attempt_bonus: bool,
) -> int:
    dm = DIFFICULTY_MULTIPLIER.get(difficulty, 1.0)
    streak_m = streak_bonus_multiplier(streak_days)
    first_m = 1.15 if first_attempt_bonus else 1.0
    raw = float(base_points) * dm * streak_m * first_m
    return max(1, int(round(raw)))
