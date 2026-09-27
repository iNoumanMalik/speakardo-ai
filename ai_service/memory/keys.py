"""Memory vocabulary: kinds, categories, and the normalised keys used for exact lookup.

Kinds and categories mirror the CHECK constraints in backend/models.py
(tests keep them in sync). A key names a slot ("birthday", "work_location") so
"What's my office?" can be answered with SQL and "I moved to Lahore" can replace
the old value instead of adding a second one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

KINDS = ("fact", "preference", "important_date", "relationship", "note", "event")
CATEGORIES = ("personal", "work", "people", "health", "finance", "places", "routine", "other")

# Importance by kind when the key doesn't say otherwise (design §6.1).
KIND_IMPORTANCE = {
    "important_date": 0.9,
    "relationship": 0.8,
    "fact": 0.5,
    "preference": 0.4,
    "note": 0.4,
    "event": 0.3,
}


@dataclass(frozen=True)
class KeySpec:
    kind: str
    category: str
    importance: float
    # How to phrase it in a question ("your office").
    label: str
    # The slot always describes the user themself ("my dentist is Dr. Khan" is the
    # user's dentist, not a memory about Dr. Khan), so it never has a subject.
    users_own: bool = False


KEYS: dict[str, KeySpec] = {
    "preferred_name": KeySpec("fact", "personal", 0.8, "name"),
    "birthday": KeySpec("important_date", "personal", 0.9, "birthday"),
    "anniversary": KeySpec("important_date", "personal", 0.9, "anniversary"),
    "relationship": KeySpec("relationship", "people", 0.8, "relationship"),
    "work_location": KeySpec("fact", "work", 0.6, "office"),
    "employer": KeySpec("fact", "work", 0.6, "employer"),
    "job_title": KeySpec("fact", "work", 0.5, "job"),
    "home_city": KeySpec("fact", "places", 0.6, "city"),
    "wake_time": KeySpec("preference", "routine", 0.6, "wake-up time"),
    "sleep_time": KeySpec("preference", "routine", 0.5, "bedtime"),
    "workout_time": KeySpec("preference", "routine", 0.5, "workout time"),
    "meeting_preference": KeySpec("preference", "work", 0.6, "meeting preference"),
    "reminder_preference": KeySpec("preference", "routine", 0.6, "reminder preference"),
    "doctor": KeySpec("fact", "people", 0.6, "doctor", users_own=True),
    "dentist": KeySpec("fact", "people", 0.6, "dentist", users_own=True),
    "pet_name": KeySpec("fact", "personal", 0.5, "pet's name"),
    "favorite_food": KeySpec("preference", "personal", 0.3, "favourite food"),
    "favorite_drink": KeySpec("preference", "personal", 0.3, "favourite drink"),
}

# Words people use in questions → key. Longest phrases are matched first.
KEY_SYNONYMS: dict[str, str] = {
    "name": "preferred_name",
    "preferred name": "preferred_name",
    "nickname": "preferred_name",
    "birthday": "birthday",
    "bday": "birthday",
    "b-day": "birthday",
    "date of birth": "birthday",
    "anniversary": "anniversary",
    "wedding anniversary": "anniversary",
    "office": "work_location",
    "workplace": "work_location",
    "work location": "work_location",
    "office location": "work_location",
    "employer": "employer",
    "company": "employer",
    "job": "job_title",
    "job title": "job_title",
    "role": "job_title",
    "city": "home_city",
    "home city": "home_city",
    "wake up time": "wake_time",
    "wake-up time": "wake_time",
    "wake time": "wake_time",
    "bedtime": "sleep_time",
    "bed time": "sleep_time",
    "sleep time": "sleep_time",
    "workout time": "workout_time",
    "gym time": "workout_time",
    "doctor": "doctor",
    "dentist": "dentist",
    "pet": "pet_name",
    "pet's name": "pet_name",
    "pets name": "pet_name",
    "dog's name": "pet_name",
    "cat's name": "pet_name",
    "favorite food": "favorite_food",
    "favourite food": "favorite_food",
    "favorite drink": "favorite_drink",
    "favourite drink": "favorite_drink",
}


def key_for(phrase: str) -> Optional[str]:
    """Map a question phrase ("office", "wake-up time") to a key, or None."""
    cleaned = re.sub(r"[?.!]+$", "", phrase.strip().lower())
    cleaned = re.sub(r"^(?:my|your|the)\s+", "", cleaned)
    if cleaned in KEYS:
        return cleaned
    return KEY_SYNONYMS.get(cleaned)


def normalise_key(key: Optional[str]) -> Optional[str]:
    """Accept only vocabulary keys (from the AI or rules); anything else is None."""
    if not key:
        return None
    cleaned = key.strip().lower().replace(" ", "_")
    return cleaned if cleaned in KEYS else None


def normalise_subject(subject: Optional[str]) -> Optional[str]:
    """Interim person label: lowercase, no "my"/possessive. "My Mother's" → "mother".

    Returns None for the user themself ("me", "I", "myself").
    """
    if not subject:
        return None
    cleaned = subject.strip().lower()
    cleaned = re.sub(r"['’]s$", "", cleaned)
    cleaned = re.sub(r"^(?:my|the|our)\s+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,!?")
    if cleaned in {"", "me", "i", "myself", "user", "the user"}:
        return None
    return cleaned[:80]


def importance_for(kind: str, key: Optional[str]) -> float:
    if key and key in KEYS:
        return KEYS[key].importance
    return KIND_IMPORTANCE.get(kind, 0.5)
