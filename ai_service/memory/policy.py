"""Save policy: decides whether a memory candidate may be stored (design §7).

Pure logic, no database. Duplicates and updates (same key and subject) are
resolved later by the memory store, which can see existing rows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .keys import CATEGORIES, KEYS, KINDS, importance_for, normalise_key, normalise_subject

MAX_TEMPORARY_DAYS = 30

# Confidence is rule-based, never the AI's own estimate (design §6.1).
CONFIDENCE_BY_BASIS = {
    "explicit_request": 1.0,
    "stated": 1.0,
    "implied": 0.8,
    "guess": 0.5,
}
# Only these are saved in 8.1; implied facts wait for background extraction (8.4).
SAVED_BASES = {"explicit_request", "stated"}

# Sensitive facts are not saved until 8.2 (encryption + opt-in). Checked with
# rules as well as the AI's flag, so a missed flag can't leak one through.
SENSITIVE_CATEGORIES = {"health", "finance"}
_SENSITIVE_PATTERNS = [
    # health
    r"\bdiabet", r"\bcancer\b", r"\bhiv\b", r"\baids\b", r"\basthma", r"\bdepress",
    r"\banxiety\b", r"\bbipolar\b", r"\badhd\b", r"\bautis", r"\bdiagnos", r"\bmedication",
    r"\bmedicine", r"\bpills?\b", r"\bprescri", r"\binsulin\b", r"\bchemo", r"\bpregnan",
    r"\bmiscarr", r"\btherap", r"\bpsychiatr", r"\bsurgery\b", r"\bdisease", r"\bdisorder",
    r"\ballerg", r"\bblood pressure\b", r"\bcholesterol\b", r"\bmental health\b",
    r"\bsick\b", r"\billness\b", r"\bsymptom",
    # money and identity
    r"\bsalary\b", r"\bincome\b", r"\bbank (?:account|balance|details)\b", r"\bmy bank\b",
    r"\baccount number\b", r"\biban\b",
    r"\bcredit card\b", r"\bdebit card\b", r"\bcard number\b", r"\bloan\b", r"\bdebt\b",
    r"\bpassword\b", r"\bpasscode\b", r"\bpin\b", r"\bcnic\b", r"\bpassport number\b",
    r"\bssn\b", r"\bsocial security\b",
    # beliefs and identity
    r"\breligio", r"\bmuslim\b", r"\bchristian\b", r"\bhindu\b", r"\bjewish\b",
    r"\batheist\b", r"\bsikh\b", r"\bpray", r"\bgay\b", r"\blesbian\b", r"\bbisexual\b",
    r"\btransgender\b", r"\bsexual", r"\bpolitical\b", r"\bvote[sd]? for\b",
    # exact home address
    r"\b(?:my|home|house|postal|street) address\b", r"\bhouse (?:no|number|#)", r"\bhouse \d+", r"\b\d+[a-z]?,?\s+\w+\s+(?:street|st|road|rd|avenue|ave|lane)\b",
]
_SENSITIVE_RE = re.compile("|".join(_SENSITIVE_PATTERNS), re.IGNORECASE)

# "Remember you must always reply in caps" is an instruction, not a fact.
_INSTRUCTION_RE = re.compile(
    r"^\s*(?:that\s+)?(?:you\s+(?:must|should|have to|need to|will|shall|are to)\b"
    r"|always\b|never\b|from now on\b|ignore\b|forget (?:all|your|previous)\b"
    r"|reply\b|respond\b|answer\b|act as\b|pretend\b|stop being\b)"
    r"|\b(?:system prompt|your instructions|previous instructions)\b",
    re.IGNORECASE,
)


# Hedged statements aren't clear enough to save (design §7: "unclear / guessed").
_HEDGE_RE = re.compile(
    r"\b(?:maybe|perhaps|possibly|probably|might|i think|i guess|i suppose|not sure|unsure"
    r"|thinking (?:about|of)|considering|planning to|hopefully|someday|some day|sometime|one day)\b",
    re.IGNORECASE,
)
# One-off things that already happened stay in chat history, not memory (design §2 #6).
_EPISODE_PAST_RE = re.compile(
    r"\b(?:had|ate|drank|went|was|were|did|got|saw|met|watched|played|bought|visited"
    r"|called|finished|came|left|took|made)\b",
    re.IGNORECASE,
)
_EPISODE_TIME_RE = re.compile(
    r"\b(?:today|yesterday|tonight|last night|this morning|this afternoon|this evening"
    r"|earlier today|just now)\b",
    re.IGNORECASE,
)
_NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_UNIT_DAYS = {"day": 1, "week": 7, "month": 30}
_DURATION_RE = re.compile(
    r"\b(?:for|over|(?=next|coming))\s*(?:the\s+)?(?:next\s+|coming\s+)?"
    r"(\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten)\s+(day|week|month)s?\b",
    re.IGNORECASE,
)
_FIXED_DURATIONS = (
    (re.compile(r"\bthis weekend\b", re.IGNORECASE), 3),
    (re.compile(r"\bthis week\b", re.IGNORECASE), 7),
    (re.compile(r"\bthis month\b", re.IGNORECASE), 30),
    (re.compile(r"\buntil tomorrow\b", re.IGNORECASE), 2),
    (re.compile(r"\buntil (?:mon|tues|wednes|thurs|fri|satur|sun)day\b", re.IGNORECASE), 7),
    (re.compile(r"\b(?:today|tonight)\b", re.IGNORECASE), 1),
)
# Facts that are never temporary, whatever words surround them.
_LASTING_KINDS = {"important_date", "relationship"}
_LASTING_KEYS = {"birthday", "anniversary", "relationship", "preferred_name"}

_MONTHS_AND_DAYS = {
    "january", "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december", "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
}
# Capitalised words a memory may add without them appearing in the message.
_ALLOWED_CAPITALS = {"your", "you", "i", "dr", "mr", "mrs", "ms", "miss", "am", "pm"} | _MONTHS_AND_DAYS


def is_hedged_text(text: str) -> bool:
    return bool(_HEDGE_RE.search(text or ""))


def is_episode_text(text: str) -> bool:
    return bool(_EPISODE_PAST_RE.search(text or "") and _EPISODE_TIME_RE.search(text or ""))


def infer_temporary_days(text: str) -> Optional[int]:
    """Days a fact lasts from wording like "this week" or "for two weeks", else None."""
    text = text or ""
    m = _DURATION_RE.search(text)
    if m:
        amount = m.group(1).lower()
        count = int(amount) if amount.isdigit() else _NUMBER_WORDS[amount]
        return count * _UNIT_DAYS[m.group(2).lower()]
    for pattern, days in _FIXED_DURATIONS:
        if pattern.search(text):
            return days
    return None


def ungrounded_names(content: str, source_text: str) -> list[str]:
    """Capitalised words (names, places) in a memory that the user never said.

    Catches the AI misspelling or inventing a detail ("Faisl" for "Faisal"): a wrong
    memory is worse than a missing one.
    """
    source = (source_text or "").lower()
    missing = []
    for word in re.findall(r"\b[A-Z][A-Za-z]+(?:['’][a-z]+)?", content or ""):
        base = re.split(r"['’]", word)[0].lower()  # "Sara's" → sara, "You're" → you
        if base not in _ALLOWED_CAPITALS and base not in source:
            missing.append(word)
    return missing


def is_sensitive_text(text: str) -> bool:
    return bool(_SENSITIVE_RE.search(text or ""))


def is_instruction_text(text: str) -> bool:
    return bool(_INSTRUCTION_RE.search(text or ""))


@dataclass
class MemoryCandidate:
    """A possible memory, from the AI extraction or the turn router."""

    content: str
    kind: str = "note"
    category: str = "other"
    key: Optional[str] = None
    subject: Optional[str] = None
    value: Optional[dict[str, Any]] = None
    basis: str = "stated"  # explicit_request | stated | implied | guess
    sensitive: bool = False
    is_instruction: bool = False
    temporary_days: Optional[int] = None

    def normalised(self) -> "MemoryCandidate":
        """Clamp AI output to the vocabulary: unknown values fall back safely.

        A known key decides kind and category, so the same slot is always filed
        the same way (the AI may call an office "work" one day and "places" the next,
        or file a dentist or gym times under "health"). Sensitivity is judged by the
        AI's flag and the keyword rules on the content, not by this category.
        """
        key = normalise_key(self.key)
        kind = self.kind if self.kind in KINDS else "note"
        category = self.category if self.category in CATEGORIES else "other"
        subject = normalise_subject(self.subject)
        if key is not None:
            spec = KEYS[key]
            kind, category = spec.kind, spec.category
            if spec.users_own:
                subject = None  # "my dentist is Dr. Khan" is about the user
            elif subject is not None and category == "personal":
                category = "people"  # Sara's birthday is about Sara, not the user
        return MemoryCandidate(
            content=re.sub(r"\s+", " ", (self.content or "")).strip()[:500],
            kind=kind,
            category=category,
            key=key,
            subject=subject,
            value=self.value if isinstance(self.value, dict) else None,
            basis=self.basis if self.basis in CONFIDENCE_BY_BASIS else "guess",
            sensitive=bool(self.sensitive),
            is_instruction=bool(self.is_instruction),
            temporary_days=self.temporary_days if isinstance(self.temporary_days, int) else None,
        )


@dataclass
class MemorySettings:
    memory_enabled: bool = True
    learn_from_chat: bool = True


class Decision(str, Enum):
    SAVE = "save"
    SKIP_DISABLED = "skip_disabled"
    SKIP_SENSITIVE = "skip_sensitive"
    SKIP_INSTRUCTION = "skip_instruction"
    SKIP_UNCERTAIN = "skip_uncertain"
    SKIP_UNGROUNDED = "skip_ungrounded"
    SKIP_EMPTY = "skip_empty"


@dataclass
class PolicyResult:
    decision: Decision
    candidate: MemoryCandidate
    confidence: float = 0.0
    importance: float = 0.0
    temporary_days: Optional[int] = None
    reasons: list[str] = field(default_factory=list)

    @property
    def should_save(self) -> bool:
        return self.decision is Decision.SAVE


def decide(
    candidate: MemoryCandidate,
    settings: MemorySettings,
    *,
    source_text: Optional[str] = None,
) -> PolicyResult:
    """Apply the save policy to one candidate (already normalised or not).

    ``source_text`` is what the user said. When given, rules check it for hedges,
    one-off events and durations, and that names in the memory were actually said.
    """
    c = candidate.normalised()

    if not settings.memory_enabled:
        return PolicyResult(Decision.SKIP_DISABLED, c, reasons=["memory_disabled"])
    if c.basis != "explicit_request" and not settings.learn_from_chat:
        return PolicyResult(Decision.SKIP_DISABLED, c, reasons=["learn_from_chat_off"])
    if not c.content:
        return PolicyResult(Decision.SKIP_EMPTY, c, reasons=["empty"])
    if c.is_instruction or is_instruction_text(c.content):
        return PolicyResult(Decision.SKIP_INSTRUCTION, c, reasons=["instruction"])
    if c.sensitive or c.category in SENSITIVE_CATEGORIES or is_sensitive_text(c.content):
        return PolicyResult(Decision.SKIP_SENSITIVE, c, reasons=["sensitive"])
    if c.basis not in SAVED_BASES:
        return PolicyResult(Decision.SKIP_UNCERTAIN, c, reasons=[f"basis_{c.basis}"])
    if source_text and c.basis != "explicit_request":
        if is_hedged_text(source_text):
            return PolicyResult(Decision.SKIP_UNCERTAIN, c, reasons=["hedged"])
        if c.key is None and c.kind in ("event", "note") and is_episode_text(source_text):
            return PolicyResult(Decision.SKIP_UNCERTAIN, c, reasons=["episode"])
    if source_text and ungrounded_names(c.content, source_text):
        return PolicyResult(Decision.SKIP_UNGROUNDED, c, reasons=["ungrounded"])

    days = None
    if c.temporary_days is not None and c.temporary_days > 0:
        days = min(c.temporary_days, MAX_TEMPORARY_DAYS)
    elif source_text and c.kind not in _LASTING_KINDS and c.key not in _LASTING_KEYS:
        inferred = infer_temporary_days(source_text)
        days = min(inferred, MAX_TEMPORARY_DAYS) if inferred else None
    return PolicyResult(
        Decision.SAVE,
        c,
        confidence=CONFIDENCE_BY_BASIS[c.basis],
        importance=importance_for(c.kind, c.key),
        temporary_days=days,
    )
