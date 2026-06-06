"""
Layer 2 — smart date/time parsing.

Uses dateparser (chrono-style NL dates) and parsedatetime as a secondary parser.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .layer1_rules import clean_task_text
from .types import ParseResult

logger = logging.getLogger(__name__)

_NAMED_TIMES: dict[str, str] = {
    "noon": "12:00",
    "midnight": "00:00",
    "after lunch": "13:30",
    "after dinner": "20:30",
    "after breakfast": "08:30",
    "tonight": "20:00",
    "this evening": "18:30",
    "this morning": "09:00",
    "evening": "18:30",
    "morning": "09:00",
}

_RELATIVE_HOURS = re.compile(r"\bin\s+(\d+)\s+hours?\b", re.I)
_RELATIVE_MINUTES = re.compile(r"\bin\s+(\d+)\s+minutes?\b", re.I)
_CLOCK_24 = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_CLOCK_12 = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
    re.I,
)
_NEXT_WEEKDAY = re.compile(
    r"\bnext\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.I,
)
_ON_WEEKDAY = re.compile(
    r"\b(?:on\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.I,
)
_EVERY_WEEKDAY = re.compile(
    r"\bevery\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.I,
)

_WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _resolve_tz(tz_name: Optional[str]) -> ZoneInfo:
    if not tz_name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(tz_name.strip())
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _reference_now(tz_name: Optional[str]) -> datetime:
    return datetime.now(_resolve_tz(tz_name))


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def _fmt_time(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def _parse_named_times(lower: str) -> Optional[str]:
    for phrase, value in sorted(_NAMED_TIMES.items(), key=lambda x: -len(x[0])):
        if phrase in lower:
            return value
    return None


def _parse_clock(lower: str, message: str) -> tuple[Optional[str], list[str]]:
    spans: list[str] = []
    m = _CLOCK_12.search(message)
    if m:
        spans.append(m.group(0))
        h = int(m.group(1))
        minute = int(m.group(2) or 0)
        mer = (m.group(3) or "").lower()
        if mer == "pm" and h != 12:
            h += 12
        if mer == "am" and h == 12:
            h = 0
        return f"{h:02d}:{minute:02d}", spans
    m = _CLOCK_24.search(message)
    if m:
        spans.append(m.group(0))
        return f"{int(m.group(1)):02d}:{m.group(2)}", spans
    return None, spans


def _parse_relative(lower: str, now: datetime) -> tuple[Optional[str], Optional[str], list[str]]:
    spans: list[str] = []
    m = _RELATIVE_HOURS.search(lower)
    if m:
        spans.append(m.group(0))
        dt = now + timedelta(hours=int(m.group(1)))
        return _fmt_date(dt), _fmt_time(dt), spans
    m = _RELATIVE_MINUTES.search(lower)
    if m:
        spans.append(m.group(0))
        dt = now + timedelta(minutes=int(m.group(1)))
        return _fmt_date(dt), _fmt_time(dt), spans
    return None, None, spans


def _next_weekday(weekday: int, now: datetime, *, force_next: bool) -> datetime:
    days_ahead = (weekday - now.weekday()) % 7
    if force_next and days_ahead == 0:
        days_ahead = 7
    elif not force_next and days_ahead == 0:
        return now
    return now + timedelta(days=days_ahead)


def _parse_weekday_phrases(
    lower: str,
    message: str,
    now: datetime,
) -> tuple[Optional[str], list[str]]:
    spans: list[str] = []
    m = _NEXT_WEEKDAY.search(lower)
    if m:
        spans.append(m.group(0))
        wd = _WEEKDAY_INDEX[m.group(1).lower()]
        dt = _next_weekday(wd, now, force_next=True)
        return _fmt_date(dt.replace(
            hour=now.hour, minute=now.minute, second=0, microsecond=0
        )), spans
    m = _EVERY_WEEKDAY.search(lower)
    if m:
        spans.append(m.group(0))
        wd = _WEEKDAY_INDEX[m.group(1).lower()]
        dt = _next_weekday(wd, now, force_next=False)
        if dt.date() == now.date():
            dt = _next_weekday(wd, now, force_next=True)
        return _fmt_date(dt.replace(
            hour=now.hour, minute=now.minute, second=0, microsecond=0
        )), spans
    m = _ON_WEEKDAY.search(lower)
    if m:
        spans.append(m.group(0))
        wd = _WEEKDAY_INDEX[m.group(1).lower()]
        dt = _next_weekday(wd, now, force_next=False)
        if dt.date() < now.date():
            dt = _next_weekday(wd, now, force_next=True)
        return _fmt_date(dt.replace(
            hour=now.hour, minute=now.minute, second=0, microsecond=0
        )), spans
    return None, spans


def _parse_with_dateparser(
    message: str,
    now: datetime,
    tz_name: Optional[str],
) -> tuple[Optional[str], Optional[str], list[str]]:
    try:
        import dateparser
        from dateparser.search import search_dates
    except ImportError:
        return None, None, []

    settings = {
        "TIMEZONE": str(now.tzinfo or "UTC"),
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": now.replace(tzinfo=now.tzinfo or timezone.utc),
        "DATE_ORDER": "MDY",
    }
    spans: list[str] = []
    date_value: Optional[str] = None
    time_value: Optional[str] = None

    try:
        found = search_dates(message, settings=settings, languages=["en"])
    except Exception as exc:
        logger.debug("dateparser search failed: %s", exc)
        found = None

    if found:
        # Use the last match — usually the most specific scheduling phrase.
        for phrase, dt in found:
            spans.append(phrase)
            if dt is None:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=now.tzinfo or timezone.utc)
            date_value = _fmt_date(dt)
            if dt.hour != 0 or dt.minute != 0 or re.search(
                r"\d|am|pm|noon|midnight|morning|evening|tonight|:\d{2}",
                phrase,
                re.I,
            ):
                time_value = _fmt_time(dt)

    if date_value is None and time_value is None:
        dt = dateparser.parse(
            message,
            settings=settings,
            languages=["en"],
        )
        if dt:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=now.tzinfo or timezone.utc)
            date_value = _fmt_date(dt)
            if dt.hour != 0 or dt.minute != 0:
                time_value = _fmt_time(dt)

    return date_value, time_value, spans


def _parse_with_parsedatetime(
    message: str,
    now: datetime,
) -> tuple[Optional[str], Optional[str]]:
    try:
        import parsedatetime
    except ImportError:
        return None, None

    cal = parsedatetime.Calendar()
    try:
        struct, status = cal.parseDT(datetimeString=message, sourceTime=now)
    except Exception as exc:
        logger.debug("parsedatetime failed: %s", exc)
        return None, None

    if status == 0:
        return None, None
    if struct.tzinfo is None:
        struct = struct.replace(tzinfo=now.tzinfo or timezone.utc)
    date_value = _fmt_date(struct)
    time_value = None
    if status in (2, 3) or struct.hour != 0 or struct.minute != 0:
        time_value = _fmt_time(struct)
    return date_value, time_value


def parse_layer2(
    message: str,
    layer1: ParseResult,
    *,
    user_timezone: Optional[str] = None,
) -> ParseResult:
    """Enrich a Layer 1 result with date/time fields."""
    result = ParseResult(
        intent=layer1.intent,
        task=layer1.task,
        date=layer1.date,
        time=layer1.time,
        repeat=layer1.repeat,
        editable_reminder_id=layer1.editable_reminder_id,
        ambiguities=list(layer1.ambiguities),
        parser_layer="layer2",
    )

    now = _reference_now(user_timezone)
    lower = message.lower()
    temporal_spans: list[str] = []

    # Relative offsets (high confidence).
    rel_date, rel_time, rel_spans = _parse_relative(lower, now)
    temporal_spans.extend(rel_spans)
    if rel_date:
        result.date = rel_date
    if rel_time:
        result.time = rel_time

    # Named times.
    named = _parse_named_times(lower)
    if named:
        result.time = named
        if "tonight" in lower or "this evening" in lower:
            result.date = result.date or _fmt_date(now)

    # Clock patterns.
    clock_time, clock_spans = _parse_clock(lower, message)
    temporal_spans.extend(clock_spans)
    if clock_time:
        result.time = clock_time

    # Weekday phrases.
    wd_date, wd_spans = _parse_weekday_phrases(lower, message, now)
    temporal_spans.extend(wd_spans)
    if wd_date:
        result.date = wd_date

    if "tomorrow" in lower and not result.date:
        result.date = _fmt_date(now + timedelta(days=1))
        temporal_spans.append("tomorrow")
    if "today" in lower and not result.date:
        result.date = _fmt_date(now)
        temporal_spans.append("today")

    # dateparser — broad NL coverage.
    dp_date, dp_time, dp_spans = _parse_with_dateparser(
        message, now, user_timezone
    )
    temporal_spans.extend(dp_spans)
    if dp_date and not result.date:
        result.date = dp_date
    if dp_time and not result.time:
        result.time = dp_time

    # parsedatetime — fill gaps only.
    if not result.date or not result.time:
        pd_date, pd_time = _parse_with_parsedatetime(message, now)
        if pd_date and not result.date:
            result.date = pd_date
        if pd_time and not result.time:
            result.time = pd_time

    # Refine draft: preserve task from pending context; only update time/date.
    if layer1.intent == "refine_draft":
        result.task = layer1.task
        result.date = result.date or layer1.date
        result.repeat = result.repeat or layer1.repeat
        if result.time and not result.date:
            result.date = layer1.date
        result.confidence = _score_layer2(result, layer1)
        return result

    # Clean task text after removing temporal spans.
    if result.task:
        from .layer1_rules import strip_task_prefixes

        stripped = strip_task_prefixes(message)
        result.task = clean_task_text(stripped, temporal_spans=temporal_spans)
        if not result.task or len(result.task) < 2:
            result.task = layer1.task

    result.confidence = _score_layer2(result, layer1)
    return result


def _score_layer2(result: ParseResult, layer1: ParseResult) -> float:
    score = layer1.confidence
    if result.task and len(result.task) >= 2:
        score += 0.25
    if result.date:
        score += 0.2
    if result.time:
        score += 0.2
    if result.intent == "refine_draft" and result.time:
        score += 0.15
    if result.ambiguities:
        score -= 0.25 * len(result.ambiguities)
    return min(1.0, max(0.0, score))
