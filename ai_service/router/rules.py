"""Rule-based memory intents: no AI call needed to recognise these (design §7 step 2).

Patterns are anchored and conservative. Anything they don't recognise falls
through to the reminder parser (8.1a) or the turn router (8.1b). "Remember to
call mom" and "don't forget to buy milk" are reminders, not memories.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ..memory.keys import key_for, normalise_subject

MEMORY_SAVE = "memory_save"
MEMORY_FORGET = "memory_forget"
MEMORY_LIST = "memory_list"
MEMORY_QUERY = "memory_query"


@dataclass(frozen=True)
class RuleMatch:
    intent: str
    # The fact to save, the thing to forget, or the question.
    text: str
    key: Optional[str] = None
    subject: Optional[str] = None


_I = re.IGNORECASE

_LIST = [
    re.compile(r"^(?:what|tell me what)\s+do\s+you\s+(?:know|remember)\s+about\s+me$", _I),
    re.compile(r"^what\s+(?:have\s+you|did\s+you)\s+(?:saved|save|remembered|remember)(?:\s+about\s+me)?$", _I),
    re.compile(r"^(?:show|list)\s+(?:me\s+)?(?:my|your|all)?\s*memories$", _I),
    re.compile(r"^what\s+do\s+you\s+remember$", _I),
]

_SAVE = [
    # "Remember that my office is in Blue Area", "Please note that …"
    re.compile(
        r"^(?:please\s+)?(?:remember|note|keep in mind|don'?t forget|do not forget)\s+that\s+(?P<fact>.+)$",
        _I,
    ),
    # "Remember: my office is in Blue Area"
    re.compile(r"^(?:please\s+)?remember\s*[:\-–]\s*(?P<fact>.+)$", _I),
    # "My office is in Blue Area, remember that"
    re.compile(r"^(?P<fact>.+?)[\s,.;:-]*(?:please\s+)?remember\s+(?:that|this)(?:\s+please)?$", _I),
]

_FORGET = [
    re.compile(r"^(?:please\s+)?forget\s+(?:that\s+|about\s+|what\s+i\s+said\s+about\s+)?(?P<target>.+)$", _I),
    re.compile(
        r"^(?:please\s+)?(?:delete|remove|erase)\s+(?:the\s+)?(?:memory|memories|note)\s+(?:about\s+|of\s+|that\s+)?(?P<target>.+)$",
        _I,
    ),
]
# "Forget it" / "forget about it" cancel a conversation; they don't name a memory.
_FORGET_NOT_A_TARGET = re.compile(r"^(?:it|that|this|about it|everything|all|all of it)$", _I)

_QUERY_WHATS_MY = re.compile(r"^(?:what|when|where|who)(?:'s|\s+is|\s+was|\s+are)\s+my\s+(?P<thing>.+)$", _I)
_QUERY_PERSON = re.compile(
    r"^(?:what|when|where)(?:'s|\s+is|\s+was)\s+(?P<who>(?:my\s+)?[\w\s]+?)['’]s\s+(?P<thing>.+)$", _I
)
_QUERY_TOLD = re.compile(
    r"^(?:what\s+did\s+i\s+tell\s+you\s+about|what\s+do\s+you\s+know\s+about|do\s+you\s+remember)\s+(?P<thing>.+)$",
    _I,
)
_QUERY_WHERE_DO_I = {
    re.compile(r"^where\s+do\s+i\s+work$", _I): "work_location",
    re.compile(r"^where\s+do\s+i\s+live$", _I): "home_city",
    re.compile(r"^who\s+do\s+i\s+work\s+for$", _I): "employer",
    re.compile(r"^what\s+time\s+do\s+i\s+(?:wake\s+up|get\s+up)$", _I): "wake_time",
    re.compile(r"^what(?:'s|\s+is)\s+my\s+name$", _I): "preferred_name",
}


def _clean(message: str) -> str:
    return re.sub(r"\s+", " ", message.strip()).rstrip(" ?.!")


def _short_name(phrase: str) -> Optional[str]:
    """A person label only if the phrase looks like a name ("Sara", "my mother")."""
    person = normalise_subject(phrase)
    if person and len(person.split()) <= 2 and not key_for(person):
        return person
    return None


def _query(
    text: str, thing: str, who: Optional[str] = None, *, person_only: bool = False
) -> Optional[RuleMatch]:
    """A query only matches when it resolves to a key or a person (8.1a).

    Anything else ("When is my dentist appointment?") falls through, so the
    reminder flow and, from 8.1b, the turn router can handle it.
    """
    key = key_for(thing)
    subject = normalise_subject(who) if who else None
    if key is None and subject is None:
        # "What did I tell you about Sara?" → everything about Sara.
        person = _short_name(thing) if person_only else None
        if person:
            return RuleMatch(MEMORY_QUERY, text, key=None, subject=person)
        return None
    return RuleMatch(MEMORY_QUERY, text, key=key, subject=subject)


def match_memory_rule(message: str) -> Optional[RuleMatch]:
    text = _clean(message)
    if not text:
        return None

    for pattern in _LIST:
        if pattern.match(text):
            return RuleMatch(MEMORY_LIST, text)

    for pattern in _SAVE:
        m = pattern.match(text)
        if m:
            fact = m.group("fact").strip(" ,.;:-")
            # "remember that" alone, or "remember to …" (a reminder), isn't a fact.
            if fact and not re.match(r"^to\s", fact, _I):
                return RuleMatch(MEMORY_SAVE, fact)

    for pattern in _FORGET:
        m = pattern.match(text)
        if m:
            target = m.group("target").strip(" ,.;:-")
            if target and not _FORGET_NOT_A_TARGET.match(target) and not re.match(r"^to\s", target, _I):
                key = key_for(target)
                return RuleMatch(
                    MEMORY_FORGET,
                    target,
                    key=key,
                    subject=None if key else _short_name(target),
                )

    for pattern, key in _QUERY_WHERE_DO_I.items():
        if pattern.match(text):
            return RuleMatch(MEMORY_QUERY, text, key=key)

    m = _QUERY_PERSON.match(text)
    if m:
        return _query(text, m.group("thing"), who=m.group("who"))
    m = _QUERY_WHATS_MY.match(text)
    if m:
        return _query(text, m.group("thing"))
    m = _QUERY_TOLD.match(text)
    if m:
        return _query(text, m.group("thing"), person_only=True)
    return None


# Strong reminder signals: these messages skip the turn router and go straight
# to the reminder parser (same cost and behaviour as before 8.1b).
_REMINDER_SIGNALS = re.compile(
    r"\b(?:remind(?:er|ers)?|wake me|alert me|notify me|set (?:an? )?alarm|alarm (?:for|at)"
    r"|don'?t let me forget|remember to|don'?t forget to|do not forget to)\b",
    re.IGNORECASE,
)


def looks_like_reminder(message: str) -> bool:
    return bool(_REMINDER_SIGNALS.search(message or ""))


_GREETINGS = ("hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening")


def is_greeting(message: str) -> bool:
    """Same check the chat router has always used for its canned greeting."""
    lower = (message or "").lower().strip()
    return lower in _GREETINGS or any(lower.startswith(g + " ") for g in _GREETINGS)


_QUESTION = re.compile(
    r"\?\s*$|^(?:what|when|where|who|whom|whose|which|how|why|do|does|did|is|are|was|were"
    r"|can|could|should|would|will|have|has)\b",
    re.IGNORECASE,
)


def looks_like_question(message: str) -> bool:
    return bool(_QUESTION.search((message or "").strip()))
