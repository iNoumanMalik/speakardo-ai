"""
Layer 1 — fast deterministic parser.

Regex, keyword extraction, intent hints, repeat detection, reminder matching.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from .types import ParseResult

# Prefixes stripped when extracting the task (order matters — longest first).
_TASK_PREFIXES = (
    r"^please\s+",
    r"^can you\s+",
    r"^could you\s+",
    r"^remind me to\s+",
    r"^remind me\s+",
    r"^set (?:a )?reminder (?:for|to)\s+",
    r"^set (?:a )?reminder\s+",
    r"^alert me to\s+",
    r"^wake me up\s+",
    r"^wake me\s+",
    r"^notify me to\s+",
    r"^notify me\s+",
)

_EDIT_KEYWORDS = re.compile(
    r"\b(change|update|edit|reschedule|move|modify|shift)\b",
    re.I,
)

_TIME_REFINE_PATTERNS = (
    re.compile(r"^(?:make it|change (?:it )?to|set (?:it )?to)\s+", re.I),
    re.compile(r"\binstead\b", re.I),
    re.compile(r"^\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*$", re.I),
    re.compile(r"^(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", re.I),
)

_REPEAT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:every day|each day|daily|everyday)\b", re.I), "daily"),
    (re.compile(r"\b(?:every week|each week|weekly)\b", re.I), "weekly"),
    (re.compile(r"\b(?:weekdays?|mon-?fri|monday to friday|every weekday)\b", re.I), "weekdays"),
    (re.compile(r"\b(?:every month|each month|monthly)\b", re.I), "monthly"),
)

# Phrases removed from task text after temporal extraction (Layer 2 also uses these).
TEMPORAL_PHRASE_PATTERNS = (
    r"\btomorrow\b",
    r"\btoday\b",
    r"\btonight\b",
    r"\bthis evening\b",
    r"\bthis morning\b",
    r"\bnext\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\bin\s+\d+\s+(?:minutes?|hours?|days?|weeks?)\b",
    r"\bafter\s+(?:lunch|dinner|breakfast)\b",
    r"\bat\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b",
    r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b",
    r"\b(?:noon|midnight)\b",
    r"\b(?:every day|each day|daily|weekly|weekdays?|monthly)\b",
    r"\bon\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\bevery\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
)


def strip_task_prefixes(text: str) -> str:
    cleaned = text.strip()
    for _ in range(4):
        before = cleaned
        for pattern in _TASK_PREFIXES:
            cleaned = re.sub(pattern, "", cleaned, flags=re.I).strip()
        if cleaned == before:
            break
    return cleaned


def _looks_like_time_refinement(message: str) -> bool:
    text = message.strip()
    return any(p.search(text) for p in _TIME_REFINE_PATTERNS)


def _extract_repeat(text: str) -> Optional[str]:
    for pattern, value in _REPEAT_PATTERNS:
        if pattern.search(text):
            return value
    return None


def _match_saved_reminder(
    message: str,
    recent_reminders: Optional[list[dict[str, Any]]],
) -> Optional[str]:
    if not recent_reminders:
        return None
    lower = message.lower()
    best_id: Optional[str] = None
    best_len = 0
    for row in recent_reminders:
        task = (row.get("task") or "").strip().lower()
        rid = row.get("id")
        if not task or not rid:
            continue
        if task in lower:
            if len(task) > best_len:
                best_len = len(task)
                best_id = str(rid)
            continue
        for word in task.split():
            w = word.strip(".,!?")
            if len(w) >= 3 and w in lower:
                if len(task) > best_len:
                    best_len = len(task)
                    best_id = str(rid)
                break
    return best_id


def _detect_ambiguous_time(text: str) -> bool:
    """Bare hour without am/pm and not HH:MM — e.g. 'at 3' or 'make it 7'."""
    return bool(
        re.search(
            r"(?:\bat\s+|make it\s+|change (?:it )?to\s+)(\d{1,2})(?!\s*(?:am|pm|:|\d))",
            text,
            re.I,
        )
    )


def clean_task_text(text: str, *, temporal_spans: Optional[list[str]] = None) -> str:
    """Remove temporal phrases and filler words from task text."""
    cleaned = text.strip()
    for span in temporal_spans or []:
        if span:
            cleaned = cleaned.replace(span, " ")
    for pattern in TEMPORAL_PHRASE_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.I)
    cleaned = re.sub(
        r"\b(?:on|at|by|for|every|each)\s*$",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    return cleaned


def parse_layer1(
    message: str,
    *,
    pending_context: Optional[dict[str, Any]] = None,
    recent_reminders: Optional[list[dict[str, Any]]] = None,
) -> ParseResult:
    text = message.strip()
    lower = text.lower()
    result = ParseResult(parser_layer="layer1")

    if pending_context and _looks_like_time_refinement(text):
        result.intent = "refine_draft"
        result.task = pending_context.get("task")
        result.date = pending_context.get("date")
        result.time = pending_context.get("time")
        result.repeat = pending_context.get("repeat")
        result.confidence = 0.5
        return result

    if _EDIT_KEYWORDS.search(text):
        matched = _match_saved_reminder(text, recent_reminders)
        if matched:
            result.intent = "edit_saved"
            result.editable_reminder_id = matched
            result.confidence = 0.45

    repeat = _extract_repeat(lower)
    if repeat:
        result.repeat = repeat

    task_body = strip_task_prefixes(text)
    if _detect_ambiguous_time(lower):
        result.ambiguities.append("ambiguous_time")

    result.task = clean_task_text(task_body) or None
    if not result.task or len(result.task) < 2:
        result.needs_clarification = True
        result.clarification_question = "What would you like to be reminded about?"
        result.confidence = 0.1
    else:
        result.confidence = max(result.confidence, 0.4)

    return result
