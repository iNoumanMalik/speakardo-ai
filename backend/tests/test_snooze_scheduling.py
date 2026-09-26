"""Tests for snooze rescheduling and delivery dedupe."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import sessionmaker

import models
from services.reminder_state import clear_delivery_history
from services.scheduler import _utcnow, delivery_dedupe_key


@pytest.fixture()
def db_session(db_session):
    """Postgres session from conftest.py, plus one user: yields (session, user)."""
    user = models.User(
        id=uuid4(),
        email="snooze@example.com",
        password="hashed",
    )
    db_session.add(user)
    db_session.commit()
    return db_session, user


def test_snooze_clears_delivery_attempts(db_session):
    session, user = db_session
    now = _utcnow()
    reminder = models.Reminder(
        id=uuid4(),
        user_id=user.id,
        task="medicine",
        datetime=now - timedelta(minutes=1),
        status=models.ReminderStatus.TRIGGERED.value,
        attempt_count=2,
    )
    session.add(reminder)
    device = models.DeviceToken(
        id=uuid4(),
        user_id=user.id,
        token="token-abc",
    )
    session.add(device)
    session.flush()

    scheduled_at = reminder.datetime
    session.add(
        models.DeliveryAttempt(
            id=uuid4(),
            reminder_id=reminder.id,
            device_token_id=device.id,
            dedupe_key=delivery_dedupe_key(reminder.id, device.id, scheduled_at),
            status=models.DeliveryStatus.SUCCESS.value,
        )
    )
    session.commit()

    cleared = clear_delivery_history(session, reminder.id)
    session.commit()

    remaining = (
        session.query(models.DeliveryAttempt)
        .filter(models.DeliveryAttempt.reminder_id == reminder.id)
        .count()
    )
    assert cleared == 1
    assert remaining == 0


def test_scheduler_respects_external_snooze_during_processing(db_session):
    from services.scheduler import _process_reminder
    session, user = db_session
    now = _utcnow()
    
    # 1. Create a reminder in PENDING status
    reminder = models.Reminder(
        id=uuid4(),
        user_id=user.id,
        task="medicine",
        datetime=now - timedelta(minutes=5),
        status=models.ReminderStatus.PENDING.value,
        attempt_count=0,
    )
    session.add(reminder)
    
    # Add a device token
    device = models.DeviceToken(
        id=uuid4(),
        user_id=user.id,
        token="token-abc",
    )
    session.add(device)
    session.commit()

    # 2. Simulate claiming (scheduler claim status -> PROCESSING)
    reminder.status = models.ReminderStatus.PROCESSING.value
    reminder.processing_started_at = now
    session.commit()

    # 3. Simulate an external snooze click using a SEPARATE session
    Session2 = sessionmaker(bind=session.bind)
    session2 = Session2()
    
    snoozed_time = now + timedelta(minutes=5)
    session2.query(models.Reminder).filter(models.Reminder.id == reminder.id).update({
        "status": models.ReminderStatus.PENDING.value,
        "datetime": snoozed_time,
        "processing_started_at": None,
    })
    session2.commit()
    session2.close()
    
    # Now our main scheduler session still has 'reminder' in memory thinking it is PROCESSING.
    # We do NOT refresh it before calling _process_reminder, which perfectly simulates the scheduler
    # which holds the 'reminder' object in memory while the database row is updated by the snooze endpoint.
    
    # 4. Run _process_reminder
    _process_reminder(session, reminder, now)
    session.commit()
    
    # 5. Verify the DB state: it should still be PENDING (snoozed) and have the future datetime!
    session.refresh(reminder)
    assert reminder.status == models.ReminderStatus.PENDING.value
    assert reminder.datetime.replace(tzinfo=timezone.utc).timestamp() == pytest.approx(snoozed_time.timestamp(), abs=1)
    assert reminder.processing_started_at is None


def test_scheduler_respects_external_completion_during_processing(db_session):
    from services.scheduler import _process_reminder
    session, user = db_session
    now = _utcnow()
    
    reminder = models.Reminder(
        id=uuid4(),
        user_id=user.id,
        task="laundry",
        datetime=now - timedelta(minutes=5),
        status=models.ReminderStatus.PENDING.value,
        attempt_count=0,
    )
    session.add(reminder)
    
    device = models.DeviceToken(
        id=uuid4(),
        user_id=user.id,
        token="token-xyz",
    )
    session.add(device)
    session.commit()

    # Simulate claiming
    reminder.status = models.ReminderStatus.PROCESSING.value
    reminder.processing_started_at = now
    session.commit()

    # Simulate external complete click using a SEPARATE session
    Session2 = sessionmaker(bind=session.bind)
    session2 = Session2()
    
    session2.query(models.Reminder).filter(models.Reminder.id == reminder.id).update({
        "status": models.ReminderStatus.COMPLETED.value,
        "processing_started_at": None,
    })
    session2.commit()
    session2.close()
    
    # Now our main scheduler session still has 'reminder' in memory thinking it is PROCESSING.

    # Run _process_reminder
    _process_reminder(session, reminder, now)
    session.commit()
    
    # Verify DB state: should still be COMPLETED
    session.refresh(reminder)
    assert reminder.status == models.ReminderStatus.COMPLETED.value
    assert reminder.processing_started_at is None
