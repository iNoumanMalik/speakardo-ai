"""Tests for reminder scheduler claim/recovery logic."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

import models
from services.scheduler import (
    PROCESSING_TIMEOUT_SECONDS,
    _claim_due_reminder,
    _recover_stale_processing,
    _utcnow,
    delivery_dedupe_key,
)


@pytest.fixture()
def db_session(db_session):
    """Postgres session from conftest.py, plus one user: yields (session, user)."""
    user = models.User(
        id=uuid4(),
        email="test@example.com",
        password="hashed",
    )
    db_session.add(user)
    db_session.commit()
    return db_session, user


def _add_reminder(session, user_id, **kwargs):
    now = _utcnow()
    fields = {
        "id": uuid4(),
        "user_id": user_id,
        "task": "test task",
        "datetime": now - timedelta(minutes=5),
        "status": models.ReminderStatus.PENDING.value,
        "attempt_count": 0,
    }
    fields.update(kwargs)
    reminder = models.Reminder(**fields)
    session.add(reminder)
    session.commit()
    session.refresh(reminder)
    return reminder


def test_recover_stale_processing_resets_old_processing_rows(db_session):
    session, user = db_session
    now = _utcnow()
    stale = _add_reminder(
        session,
        user.id,
        status=models.ReminderStatus.PROCESSING.value,
        processing_started_at=now - timedelta(seconds=PROCESSING_TIMEOUT_SECONDS + 60),
    )

    count = _recover_stale_processing(session, now)
    session.refresh(stale)

    assert count == 1
    assert stale.status == models.ReminderStatus.PENDING.value
    assert stale.processing_started_at is None


def test_claim_does_not_commit_until_caller_commits(db_session):
    session, user = db_session
    now = _utcnow()
    reminder = _add_reminder(session, user.id)

    claimed = _claim_due_reminder(session, reminder.id, now)
    assert claimed is True
    session.rollback()
    session.refresh(reminder)
    assert reminder.status == models.ReminderStatus.PENDING.value

    assert _claim_due_reminder(session, reminder.id, now) is True
    session.commit()
    session.refresh(reminder)
    assert reminder.status == models.ReminderStatus.PROCESSING.value


def test_dedupe_key_changes_when_scheduled_time_changes():
    reminder_id = uuid4()
    device_id = uuid4()
    t1 = datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 5, 24, 10, 5, tzinfo=timezone.utc)
    assert delivery_dedupe_key(reminder_id, device_id, t1) != delivery_dedupe_key(
        reminder_id, device_id, t2
    )


def test_claim_only_applies_to_pending_reminders(db_session):
    session, user = db_session
    now = _utcnow()
    processing = _add_reminder(
        session,
        user.id,
        status=models.ReminderStatus.PROCESSING.value,
        processing_started_at=now - timedelta(seconds=PROCESSING_TIMEOUT_SECONDS + 10),
    )

    assert _claim_due_reminder(session, processing.id, now) is False
