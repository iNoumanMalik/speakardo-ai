"""Memory engine logic (pure): vocabulary, save policy, AI extraction.

Database reads and writes live in backend/services/memory_store.py.
"""

from .keys import CATEGORIES, KEYS, KINDS, key_for, normalise_key, normalise_subject
from .policy import (
    Decision,
    MemoryCandidate,
    MemorySettings,
    PolicyResult,
    decide,
    is_instruction_text,
    is_sensitive_text,
)

__all__ = [
    "CATEGORIES",
    "Decision",
    "KEYS",
    "KINDS",
    "MemoryCandidate",
    "MemorySettings",
    "PolicyResult",
    "decide",
    "is_instruction_text",
    "is_sensitive_text",
    "key_for",
    "normalise_key",
    "normalise_subject",
]
