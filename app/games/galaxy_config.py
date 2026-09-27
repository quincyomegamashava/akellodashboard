"""Quiz Galaxy worlds: one planet per catalog subject; shared themed shells."""

from __future__ import annotations

from typing import Any

from app.games.hbc_catalog import subject_slug


# Default shell + meta per HBC catalog subject (classic games live under the same planet).
SUBJECT_WORLD_DEFS: list[dict[str, Any]] = [
    {
        "subject": "English Language",
        "shell": "climb-the-mountain",
        "challenge_name": "Climb the Mountain",
        "fact": "Climb with every correct answer. Classic English quizzes for your age are listed below.",
        "color": 0x3D9A5F,
        "accent": 0xA8E6C0,
        "preview_key": "climb",
    },
    {
        "subject": "Mathematics",
        "shell": "balloon-pop-challenge",
        "challenge_name": "Balloon Pop Challenge",
        "fact": "Pop balloons with correct maths answers. All classic maths quizzes sit in this world.",
        "color": 0xE85D75,
        "accent": 0xFFB0BC,
        "preview_key": "balloon",
    },
    {
        "subject": "Social Science",
        "shell": "animal-race",
        "challenge_name": "Animal Race",
        "fact": "Race animals with correct answers. Browse classic Social Science quizzes here too.",
        "color": 0xF0A040,
        "accent": 0xFFD080,
        "rings": True,
        "preview_key": "race",
    },
    {
        "subject": "Science and Technology",
        "shell": "rocket-to-the-moon",
        "challenge_name": "Rocket to the Moon",
        "fact": "Boost toward the moon with science answers. Classic Science & Technology quizzes included.",
        "color": 0x4A7FD4,
        "accent": 0x9EC5FF,
        "preview_key": "rocket",
    },
    {
        "subject": "Geography",
        "shell": "save-the-snowman",
        "challenge_name": "Save the Snowman",
        "fact": "Rebuild the snowman with correct answers. Classic Geography quizzes live here.",
        "color": 0x7EC8E8,
        "accent": 0xE8F6FF,
        "preview_key": "snowman",
    },
    {
        "subject": "Combined Science",
        "shell": "retrowave-racer",
        "challenge_name": "Retrowave Racer",
        "fact": "Steer into the correct neon answer on the highway. Classic Combined Science quizzes live here too.",
        "color": 0xFF2ECD,
        "accent": 0x5CFFF7,
        "rings": True,
        "preview_key": "retrowave",
    },
    {
        "subject": "ICT",
        "shell": "tug-of-war-quiz",
        "challenge_name": "Tug of War Quiz",
        "fact": "Pull the rope with correct ICT answers. Classic ICT quizzes are listed under this world.",
        "color": 0x6BB85A,
        "accent": 0xC5E8A8,
        "preview_key": "tug",
    },
]

# Optional overrides: map any extra subject string → shell slug
GALAXY_SUBJECT_SHELL_OVERRIDES: dict[str, str] = {}


GALAXY_HUB_WORLD: dict[str, Any] = {
    "id": "mission_control",
    "planet": "mission_control",
    "label": "Mission Control",
    "name": "Learner Hub",
    "shell": "mission-control",
    "fact": "Your profile, races, leaderboard, and classic library — all in one place.",
    "catalog_subjects": [],
    "color": 0xF5C542,
    "accent": 0xFFE9A8,
    "size": 2.15,
    "dist": 11,
    "speed": 0.18,
    "rings": True,
    "preview_key": "hub",
    "kind": "hub",
}

# Extra challenge planets (new interaction styles) — keep subject worlds unchanged.
GALAXY_CHALLENGE_WORLDS: list[dict[str, Any]] = [
    {
        "id": "target_arcade",
        "planet": "target_arcade",
        "label": "Target Arcade",
        "name": "Target Tap",
        "shell": "target-tap",
        "fact": "Whack the correct answer target before it ducks. Speed practice for Maths.",
        "catalog_subjects": ["Mathematics"],
        "color": 0xE85D5D,
        "accent": 0xF6AD55,
        "rings": True,
        "preview_key": "target",
    },
    {
        "id": "atlas_quest",
        "planet": "atlas_quest",
        "label": "Atlas Quest",
        "name": "Atlas Quest",
        "shell": "atlas-map",
        "fact": "Tap the map region with the right answer. Built for Geography explorers.",
        "catalog_subjects": ["Geography"],
        "color": 0x2B6CB0,
        "accent": 0x9FD4F5,
        "preview_key": "atlas",
    },
    {
        "id": "memory_nebula",
        "planet": "memory_nebula",
        "label": "Memory Nebula",
        "name": "Memory Nebula",
        "shell": "memory-match",
        "fact": "Flip cards to match the question mark with the correct answer. Great for English vocab.",
        "catalog_subjects": ["English Language"],
        "color": 0x7C3AED,
        "accent": 0xC4B5FD,
        "rings": True,
        "preview_key": "memory",
    },
    {
        "id": "beat_station",
        "planet": "beat_station",
        "label": "Beat Station",
        "name": "Beat Station",
        "shell": "rhythm-beat",
        "fact": "Tap the lane when the answer note hits the zone. Timing challenge for ICT.",
        "catalog_subjects": ["ICT"],
        "color": 0x38BDF8,
        "accent": 0xFBBF24,
        "preview_key": "rhythm",
    },
]


def _build_worlds() -> list[dict[str, Any]]:
    worlds: list[dict[str, Any]] = [dict(GALAXY_HUB_WORLD)]
    for i, defn in enumerate(SUBJECT_WORLD_DEFS):
        sub = defn["subject"]
        sid = subject_slug(sub)
        dist = 20 + i * 9
        speed = 0.52 - i * 0.05
        worlds.append({
            "id": sid,
            "planet": sid,
            "label": sub,
            "name": defn["challenge_name"],
            "shell": defn["shell"],
            "fact": defn["fact"],
            "catalog_subjects": [sub],
            "color": defn["color"],
            "accent": defn["accent"],
            "size": 1.55 + (i % 3) * 0.12,
            "dist": dist,
            "speed": max(0.12, speed),
            "rings": bool(defn.get("rings")),
            "preview_key": defn.get("preview_key") or "climb",
            "kind": "subject",
        })
    base_dist = 20 + len(SUBJECT_WORLD_DEFS) * 9
    for j, ch in enumerate(GALAXY_CHALLENGE_WORLDS):
        worlds.append({
            **ch,
            "dist": ch.get("dist") or (base_dist + (j + 1) * 8),
            "speed": ch.get("speed") or max(0.1, 0.28 - j * 0.03),
            "size": ch.get("size") or 1.48,
            "kind": "challenge",
        })
    return worlds


GALAXY_WORLDS: list[dict[str, Any]] = _build_worlds()


def world_by_shell(shell: str) -> dict[str, Any] | None:
    """First world using this shell (prefer exact subject via subject query elsewhere)."""
    shell = (shell or "").strip().lower()
    for w in GALAXY_WORLDS:
        if w["shell"] == shell or w["id"] == shell:
            return w
    return None


def world_by_subject(subject: str) -> dict[str, Any] | None:
    key = (subject or "").strip().lower()
    if not key:
        return None
    for w in GALAXY_WORLDS:
        if w["label"].lower() == key or w["id"] == key or w["planet"] == key:
            return w
        if any(s.lower() == key for s in w.get("catalog_subjects") or []):
            return w
    return None


def world_by_planet(planet: str) -> dict[str, Any] | None:
    return world_by_subject(planet)


def shell_for_subject(subject: str) -> str | None:
    sub = (subject or "").strip()
    if not sub:
        return None
    if sub in GALAXY_SUBJECT_SHELL_OVERRIDES:
        return GALAXY_SUBJECT_SHELL_OVERRIDES[sub]
    w = world_by_subject(sub)
    return w["shell"] if w else None


def catalog_subjects_for_world(world: dict[str, Any], subject_override: str | None = None) -> list[str]:
    base = list(world.get("catalog_subjects") or [world.get("label")])
    if not subject_override or not subject_override.strip():
        return base
    ov = subject_override.strip()
    # World label / id / name means "play this planet" — keep full multi-subject catalog.
    identity = {
        (world.get("label") or "").lower(),
        (world.get("id") or "").lower(),
        (world.get("planet") or "").lower(),
        (world.get("name") or "").lower(),
    }
    if ov.lower() in identity:
        return base
    return [ov]


def worlds_for_hub_json() -> list[dict[str, Any]]:
    out = []
    for w in GALAXY_WORLDS:
        kind = w.get("kind") or "subject"
        item = {
            "id": w["id"],
            "planet": w["planet"],
            "subject": w["label"],
            "name": w["name"],
            "shell": w["shell"],
            "fact": w["fact"],
            "catalog_subjects": w.get("catalog_subjects") or [],
            "color": w["color"],
            "accent": w["accent"],
            "size": w["size"],
            "dist": w["dist"],
            "speed": w["speed"],
            "rings": bool(w.get("rings")),
            "preview_key": w.get("preview_key") or w["id"],
            "kind": kind,
        }
        if kind == "hub":
            item["play_path"] = "/game-dashboard"
            item["menu"] = [
                {"label": "My profile", "href": "/game-dashboard#home"},
                {"label": "Races lobby", "href": "/game-dashboard#races"},
                {"label": "Leaderboard", "href": "/game-dashboard#leaderboard"},
                {"label": "Classic library", "href": "/game-dashboard#play"},
                {"label": "Back to Galaxy", "href": "/quiz-galaxy"},
            ]
        else:
            item["play_path"] = f"/play-galaxy/{w['shell']}?subject={w['label']}"
        out.append(item)
    return out
