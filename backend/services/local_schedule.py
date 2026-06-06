"""
Local wall-clock scheduling for repeating reminders.

Repeating reminders fire at local_time in the user's *current* timezone (users.timezone),
so travel from Asia/Karachi to Asia/Dubai keeps 09:00 on the local clock.

One-time reminders use absolute UTC datetime (unchanged).
"""

from __future__ import annotations

import calendar
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from services.repeat_schedule import normalize_repeat

logger = logging.getLogger(__name__)


def resolve_timezone(tz_name: Optional[str]) -> ZoneInfo:
    if not tz_name or not str(tz_name).strip():
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(str(tz_name).strip())
    except ZoneInfoNotFoundError:
        logger.warning("Invalid timezone %r — using UTC", tz_name)
        return ZoneInfo("UTC")


def utc_to_local(dt_utc: datetime, tz_name: Optional[str]) -> datetime:
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(resolve_timezone(tz_name))


def format_local_time(dt_local: datetime) -> str:
    return f"{dt_local.hour:02d}:{dt_local.minute:02d}"


def extract_local_schedule(
    dt_utc: datetime,
    tz_name: Optional[str],
) -> Tuple[str, int, int]:
    """Return (HH:MM, weekday 0=Mon..6=Sun, day of month)."""
    local = utc_to_local(dt_utc, tz_name)
    return format_local_time(local), local.weekday(), local.day


def apply_local_schedule_to_reminder(reminder, user_timezone: Optional[str]) -> None:
    """Set local_time / anchor fields from reminder.datetime and user TZ."""
    if reminder.datetime is None:
        return
    local_time, weekday, dom = extract_local_schedule(
        reminder.datetime, user_timezone
    )
    reminder.local_time = local_time
    if normalize_repeat(reminder.repeat):
        reminder.local_weekday = weekday
        reminder.local_day_of_month = dom


def local_now(now_utc: datetime, tz_name: Optional[str]) -> datetime:
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    return now_utc.astimezone(resolve_timezone(tz_name))


def repeating_matches_local_clock(
    *,
    repeat: Optional[str],
    local_time: Optional[str],
    local_weekday: Optional[int],
    local_day_of_month: Optional[int],
    user_tz: Optional[str],
    now_utc: datetime,
) -> bool:
    """True when user's current local clock matches this repeating reminder."""
    rule = normalize_repeat(repeat)
    if rule is None or not local_time:
        return False

    local = local_now(now_utc, user_tz)
    if format_local_time(local) != local_time:
        return False

    if rule == "daily":
        return True

    if rule == "weekdays":
        return local.weekday() < 5

    if rule == "weekly":
        if local_weekday is None:
            return True
        return local.weekday() == int(local_weekday)

    if rule == "monthly":
        if local_day_of_month is None:
            return True
        target = int(local_day_of_month)
        last_day = calendar.monthrange(local.year, local.month)[1]
        return local.day == min(target, last_day)

    return False


def is_one_time_due(dt_utc: datetime, now_utc: datetime) -> bool:
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc <= now_utc


def is_snooze_due(snoozed_until: Optional[datetime], now_utc: datetime) -> bool:
    if snoozed_until is None:
        return False
    if snoozed_until.tzinfo is None:
        snoozed_until = snoozed_until.replace(tzinfo=timezone.utc)
    return snoozed_until <= now_utc


def has_active_snooze(snoozed_until: Optional[datetime], now_utc: datetime) -> bool:
    if snoozed_until is None:
        return False
    if snoozed_until.tzinfo is None:
        snoozed_until = snoozed_until.replace(tzinfo=timezone.utc)
    return snoozed_until > now_utc


def delivery_dedupe_key_local(
    reminder_id,
    device_id,
    local_date: str,
    local_time: str,
) -> str:
    return f"{reminder_id}:{device_id}:{local_date}:{local_time}"


def is_reminder_due(
    *,
    repeat: Optional[str],
    datetime_utc: datetime,
    local_time: Optional[str],
    local_weekday: Optional[int],
    local_day_of_month: Optional[int],
    snoozed_until: Optional[datetime],
    user_tz: Optional[str],
    now_utc: datetime,
) -> bool:
    """Whether a pending reminder should fire on this scheduler tick."""
    if normalize_repeat(repeat):
        if is_snooze_due(snoozed_until, now_utc):
            return True
        if has_active_snooze(snoozed_until, now_utc):
            return False
        return repeating_matches_local_clock(
            repeat=repeat,
            local_time=local_time,
            local_weekday=local_weekday,
            local_day_of_month=local_day_of_month,
            user_tz=user_tz,
            now_utc=now_utc,
        )
    return is_one_time_due(datetime_utc, now_utc)


def compute_display_datetime_utc(
    *,
    repeat: Optional[str],
    local_time: Optional[str],
    local_weekday: Optional[int],
    local_day_of_month: Optional[int],
    user_tz: Optional[str],
    reference_utc: datetime,
) -> datetime:
    """Next/approx UTC instant for sorting and API responses."""
    rule = normalize_repeat(repeat)
    if rule is None or not local_time:
        return reference_utc
    try:
        hour, minute = map(int, local_time.split(":"))
    except ValueError:
        return reference_utc

    tz = resolve_timezone(user_tz)
    if reference_utc.tzinfo is None:
        reference_utc = reference_utc.replace(tzinfo=timezone.utc)
    local = reference_utc.astimezone(tz)

    for day_offset in range(400):
        candidate = (local + timedelta(days=day_offset)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if candidate <= local and day_offset == 0:
            continue
        if rule == "daily":
            return candidate.astimezone(timezone.utc)
        if rule == "weekdays" and candidate.weekday() < 5:
            return candidate.astimezone(timezone.utc)
        if rule == "weekly" and (
            local_weekday is None or candidate.weekday() == int(local_weekday)
        ):
            return candidate.astimezone(timezone.utc)
        if rule == "monthly":
            target = int(local_day_of_month or candidate.day)
            last_day = calendar.monthrange(candidate.year, candidate.month)[1]
            if candidate.day == min(target, last_day):
                return candidate.astimezone(timezone.utc)

    return reference_utc
