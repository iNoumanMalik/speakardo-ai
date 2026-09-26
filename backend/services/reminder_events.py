"""Append-only reminder event log (reminder_events), the raw data for 8B habit mining."""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

import models
from services.local_schedule import extract_local_schedule

logger = logging.getLogger(__name__)


def log_reminder_event(
    db: Session,
    reminder: models.Reminder,
    event: str,
    *,
    user_timezone: Optional[str],
    scheduled_for: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> models.ReminderEvent:
    """Add an event to the caller's transaction; it commits with the action it records."""
    occurred_at = now or datetime.now(timezone.utc)
    local_time, weekday, _ = extract_local_schedule(occurred_at, user_timezone)
    row = models.ReminderEvent(
        reminder_id=reminder.id,
        user_id=reminder.user_id,
        event=event,
        scheduled_for=scheduled_for,
        occurred_at=occurred_at,
        local_time=local_time,
        weekday=weekday,
    )
    db.add(row)
    logger.info(
        "event=reminder_event_logged reminder_id=%s user_id=%s type=%s",
        reminder.id,
        reminder.user_id,
        event,
    )
    return row
