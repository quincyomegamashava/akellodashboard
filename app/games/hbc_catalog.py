"""HBC subject map and ≥5 topic specs per age × subject."""

from __future__ import annotations

HBC_SUBJECTS_BY_AGE = {
    "Infants": ["English Language", "Mathematics"],
    "9-10": ["English Language", "Mathematics", "Social Science", "Science and Technology"],
    "11-12": ["English Language", "Mathematics", "Social Science", "Science and Technology"],
    "13-14": ["English Language", "Mathematics", "Geography", "Combined Science", "ICT"],
    "15-16": ["English Language", "Mathematics", "Geography", "Combined Science", "ICT"],
    "17-19": ["English Language", "Mathematics", "Geography", "Combined Science", "ICT"],
    "9-19": ["English Language", "Mathematics", "Science and Technology", "Geography", "ICT"],
    "Youths & older": ["English Language", "Mathematics", "Geography", "Combined Science", "ICT"],
}

# Five topic titles per subject (reused across ages; prompts adapt by age band).
SUBJECT_TOPICS = {
    "English Language": [
        ("nouns_verbs", "Nouns & Verbs"),
        ("sentence_sense", "Sentence Sense"),
        ("vocab_context", "Vocabulary in Context"),
        ("reading_clues", "Reading Clues"),
        ("punctuation", "Punctuation Power"),
    ],
    "Mathematics": [
        ("number_sense", "Number Sense"),
        ("operations", "Operations Lab"),
        ("fractions_ratio", "Fractions & Ratio"),
        ("measure_money", "Measure & Money"),
        ("patterns_data", "Patterns & Data"),
    ],
    "Social Science": [
        ("zimbabwe_places", "Zimbabwe Places"),
        ("community_roles", "Community Roles"),
        ("heritage_sites", "Heritage Sites"),
        ("map_basics", "Map Basics"),
        ("local_economy", "Local Economy"),
    ],
    "Science and Technology": [
        ("living_things", "Living Things"),
        ("materials", "Materials"),
        ("energy_force", "Energy & Force"),
        ("simple_circuits", "Simple Circuits"),
        ("environment", "Our Environment"),
    ],
    "Geography": [
        ("map_scale", "Map Scale"),
        ("landforms", "Landforms"),
        ("weather_climate", "Weather & Climate"),
        ("settlements", "Settlements"),
        ("resources_trade", "Resources & Trade"),
    ],
    "Combined Science": [
        ("kinematics", "Motion Basics"),
        ("forces_energy", "Forces & Energy"),
        ("matter_moles", "Matter & Moles"),
        ("electricity", "Electricity"),
        ("ecosystems", "Ecosystems"),
    ],
    "ICT": [
        ("hardware_parts", "Hardware Parts"),
        ("software_apps", "Software & Apps"),
        ("networks_safety", "Networks & Safety"),
        ("data_files", "Data & Files"),
        ("logic_algo", "Logic & Algorithms"),
    ],
}


def subject_slug(subject: str) -> str:
    return (
        subject.lower()
        .replace("&", "and")
        .replace("(", "")
        .replace(")", "")
        .replace(" ", "_")
    )


def age_slug(age_range: str) -> str:
    return (
        age_range.lower()
        .replace("&", "and")
        .replace(" ", "_")
    )


def difficulty_for_age(age_range: str) -> str:
    if age_range in ("Infants", "9-10"):
        return "easy"
    if age_range in ("11-12", "13-14", "9-19"):
        return "medium"
    return "hard"


def build_hbc_game_specs() -> list[dict]:
    """Return one spec dict per age × subject × topic (≥5 per subject×age)."""
    specs = []
    for age, subjects in HBC_SUBJECTS_BY_AGE.items():
        for subject in subjects:
            topics = SUBJECT_TOPICS.get(subject) or SUBJECT_TOPICS["Mathematics"]
            for topic_slug, topic_title in topics[:5]:
                title = f"{subject} — {topic_title}"
                filename = f"{age_slug(age)}/{subject_slug(subject)}/{topic_slug}.html"
                specs.append({
                    "title": title,
                    "subject": subject,
                    "age_range": age,
                    "topic_slug": topic_slug,
                    "topic_title": topic_title,
                    "filename": filename,
                    "difficulty_level": difficulty_for_age(age),
                    "max_score": 10,
                    "description": (
                        f"{subject} ({age}) — {topic_title}. "
                        "HBC-aligned interactive quiz with Fisher-Yates non-repeating rounds."
                    ),
                })
    return specs


HBC_GAME_SPECS = build_hbc_game_specs()

# Backward-compatible alias used by older seed imports
STEM_GAMES = HBC_GAME_SPECS
