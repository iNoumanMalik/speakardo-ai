"""Tests for local wall-clock reminder scheduling."""

from datetime import datetime, timezone

from services.local_schedule import (
    extract_local_schedule,
    is_reminder_due,
    repeating_matches_local_clock,
)


def test_extract_local_time_karachi():
    # 09:00 PKT = 04:00 UTC (May, no DST)
    dt = datetime(2026, 5, 25, 4, 0, tzinfo=timezone.utc)
    local_time, weekday, dom = extract_local_schedule(dt, "Asia/Karachi")
    assert local_time == "09:00"
    assert weekday == 0  # Monday May 25 2026
    assert dom == 25


def test_repeating_fires_at_nine_am_in_current_timezone_not_creation_tz():
    """Same local_time fires at 9am local wherever the user is now."""
    local_time = "09:00"
    # User now in Dubai — 05:00 UTC is 09:00 GST
    now_dubai = datetime(2026, 5, 25, 5, 0, tzinfo=timezone.utc)
    assert repeating_matches_local_clock(
        repeat="daily",
        local_time=local_time,
        local_weekday=0,
        local_day_of_month=25,
        user_tz="Asia/Dubai",
        now_utc=now_dubai,
    )
    # Same reminder must NOT fire at 10:00 Dubai (06:00 UTC)
    now_too_late = datetime(2026, 5, 25, 6, 0, tzinfo=timezone.utc)
    assert not repeating_matches_local_clock(
        repeat="daily",
        local_time=local_time,
        local_weekday=0,
        local_day_of_month=25,
        user_tz="Asia/Dubai",
        now_utc=now_too_late,
    )


def test_one_time_uses_absolute_utc():
    appt = datetime(2026, 6, 20, 4, 0, tzinfo=timezone.utc)
    before = datetime(2026, 6, 20, 3, 59, tzinfo=timezone.utc)
    after = datetime(2026, 6, 20, 4, 0, tzinfo=timezone.utc)
    assert not is_reminder_due(
        repeat=None,
        datetime_utc=appt,
        local_time=None,
        local_weekday=None,
        local_day_of_month=None,
        snoozed_until=None,
        user_tz="Asia/Dubai",
        now_utc=before,
    )
    assert is_reminder_due(
        repeat=None,
        datetime_utc=appt,
        local_time=None,
        local_weekday=None,
        local_day_of_month=None,
        snoozed_until=None,
        user_tz="Asia/Dubai",
        now_utc=after,
    )


def test_travel_karachi_to_dubai_same_wall_clock():
    """Created in Karachi at 9am; after travel fires at 9am Dubai, not 10am."""
    local_time = "09:00"
    # In Dubai at 9am local = 05:00 UTC
    assert repeating_matches_local_clock(
        repeat="daily",
        local_time=local_time,
        local_weekday=None,
        local_day_of_month=None,
        user_tz="Asia/Dubai",
        now_utc=datetime(2026, 5, 25, 5, 0, tzinfo=timezone.utc),
    )
    # Would have been 10:00 in Dubai if we locked to Karachi UTC offset
    assert not repeating_matches_local_clock(
        repeat="daily",
        local_time=local_time,
        local_weekday=None,
        local_day_of_month=None,
        user_tz="Asia/Dubai",
        now_utc=datetime(2026, 5, 25, 4, 0, tzinfo=timezone.utc),
    )
