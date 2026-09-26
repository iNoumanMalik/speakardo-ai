"""reminder_events: every reminder action and delivered push is logged once."""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

import models
from services.notifications import NotificationResult
from services.reminder_events import log_reminder_event
from services.scheduler import _process_reminder, check_due_reminders

T = models.ReminderEventType


def _events(db, reminder_id=None, user=None):
    query = db.query(models.ReminderEvent)
    if reminder_id is not None:
        query = query.filter(models.ReminderEvent.reminder_id == reminder_id)
    if user is not None:
        query = query.filter(models.ReminderEvent.user_id == user.id)
    return query.order_by(models.ReminderEvent.occurred_at.asc()).all()


def _future(minutes=60):
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def _add_reminder(db, user, **fields):
    values = {
        "id": uuid4(),
        "user_id": user.id,
        "task": "take medicine",
        "datetime": _future(),
        "status": models.ReminderStatus.PENDING.value,
        "attempt_count": 0,
    }
    values.update(fields)
    reminder = models.Reminder(**values)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def _create_via_api(client, headers, **fields):
    payload = {"task": "take medicine", "datetime": _future().isoformat()}
    payload.update(fields)
    response = client.post("/reminders", json=payload, headers=headers)
    assert response.status_code == 200
    return response.json()


# --- log_reminder_event ------------------------------------------------------


def test_local_time_and_weekday_use_the_users_timezone(db_session, make_user):
    user = make_user(timezone="Asia/Karachi")
    reminder = _add_reminder(db_session, user)
    # 20:30 UTC on Saturday 26 Sep is 01:30 on Sunday 27 Sep in Karachi (UTC+5).
    now = datetime(2026, 9, 26, 20, 30, tzinfo=timezone.utc)

    log_reminder_event(db_session, reminder, T.CREATED, user_timezone=user.timezone, now=now)
    db_session.commit()

    (event,) = _events(db_session, reminder.id)
    assert (event.local_time, event.weekday) == ("01:30", 6)
    assert event.occurred_at == now


def test_invalid_event_type_is_rejected_by_the_database(db_session, make_user):
    from sqlalchemy.exc import IntegrityError

    user = make_user()
    reminder = _add_reminder(db_session, user)
    log_reminder_event(db_session, reminder, "exploded", user_timezone="UTC")
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --- Router hooks ------------------------------------------------------------


def test_create_logs_created(client, db_session, make_user, auth_headers):
    user = make_user()
    body = _create_via_api(client, auth_headers(user))

    (event,) = _events(db_session, body["id"])
    assert event.event == T.CREATED
    assert event.user_id == user.id
    assert event.scheduled_for == datetime.fromisoformat(body["datetime"])


def test_patch_logs_edited_only_when_something_changes(client, db_session, make_user, auth_headers):
    user = make_user()
    headers = auth_headers(user)
    body = _create_via_api(client, headers)
    new_time = _future(120)

    client.patch(f"/reminders/{body['id']}", json={}, headers=headers)
    client.patch(f"/reminders/{body['id']}", json={"datetime": new_time.isoformat()}, headers=headers)

    events = _events(db_session, body["id"])
    assert [e.event for e in events] == [T.CREATED, T.EDITED]
    assert events[1].scheduled_for == new_time


def test_republish_logs_edited(client, db_session, make_user, auth_headers):
    user = make_user()
    headers = auth_headers(user)
    body = _create_via_api(client, headers)

    response = client.post(
        f"/reminders/{body['id']}/republish",
        json={"datetime": _future(30).isoformat()},
        headers=headers,
    )

    assert response.status_code == 200
    assert [e.event for e in _events(db_session, body["id"])] == [T.CREATED, T.EDITED]


def test_snooze_logs_snoozed_with_new_fire_time(client, db_session, make_user, auth_headers):
    user = make_user()
    headers = auth_headers(user)
    body = _create_via_api(client, headers)

    before = datetime.now(timezone.utc)
    client.post(f"/reminders/{body['id']}/snooze", json={"minutes": 10}, headers=headers)
    after = datetime.now(timezone.utc)

    snoozed = _events(db_session, body["id"])[-1]
    assert snoozed.event == T.SNOOZED
    assert before + timedelta(minutes=10) <= snoozed.scheduled_for <= after + timedelta(minutes=10)


def test_complete_one_time_logs_completed_slot(client, db_session, make_user, auth_headers):
    user = make_user()
    headers = auth_headers(user)
    body = _create_via_api(client, headers)

    client.patch(f"/reminders/{body['id']}/complete", headers=headers)

    completed = _events(db_session, body["id"])[-1]
    assert completed.event == T.COMPLETED
    assert completed.scheduled_for == datetime.fromisoformat(body["datetime"])


def test_complete_repeating_logs_slot_before_advancing(client, db_session, make_user, auth_headers):
    user = make_user()
    slot = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=3)
    reminder = _add_reminder(db_session, user, repeat="daily", datetime=slot, local_time="09:00")

    client.patch(f"/reminders/{reminder.id}/complete", headers=auth_headers(user))

    (event,) = _events(db_session, reminder.id)
    assert event.event == T.COMPLETED
    assert event.scheduled_for == slot


def test_deleted_event_outlives_the_reminder(client, db_session, make_user, auth_headers):
    user = make_user()
    headers = auth_headers(user)
    body = _create_via_api(client, headers)

    response = client.delete(f"/reminders/{body['id']}", headers=headers)

    assert response.status_code == 200
    assert db_session.get(models.Reminder, body["id"]) is None
    assert [e.event for e in _events(db_session, body["id"])] == [T.CREATED, T.DELETED]


# --- Scheduler: fired ----------------------------------------------------------


def _delivered(monkeypatch):
    monkeypatch.setattr(
        "services.scheduler.send_push_notification",
        lambda **_: NotificationResult(success=True, provider_message_id="msg-1"),
    )


def _claimed(db, user, now, **fields):
    reminder = _add_reminder(
        db,
        user,
        status=models.ReminderStatus.PROCESSING.value,
        processing_started_at=now,
        **fields,
    )
    db.add(models.DeviceToken(user_id=user.id, token=f"token-{uuid4().hex}"))
    db.commit()
    return reminder


def test_scheduler_logs_fired_for_one_time_reminder(db_session, make_user, monkeypatch):
    _delivered(monkeypatch)
    user = make_user()
    due_at = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=1)
    reminder = _add_reminder(db_session, user, datetime=due_at)
    db_session.add(models.DeviceToken(user_id=user.id, token="token-fired"))
    db_session.commit()

    asyncio.run(check_due_reminders())

    (event,) = _events(db_session, reminder.id)
    assert event.event == T.FIRED
    assert event.scheduled_for == due_at


def test_scheduler_logs_fired_slot_for_repeating_reminder(db_session, make_user, monkeypatch):
    _delivered(monkeypatch)
    user = make_user(timezone="Asia/Karachi")
    now = datetime(2026, 9, 26, 4, 0, 20, tzinfo=timezone.utc)  # 09:00:20 in Karachi
    reminder = _claimed(db_session, user, now, repeat="daily", datetime=now, local_time="09:00")

    _process_reminder(db_session, reminder, now, user_timezone=user.timezone)
    db_session.commit()

    (event,) = _events(db_session, reminder.id)
    assert event.event == T.FIRED
    assert event.scheduled_for == datetime(2026, 9, 26, 4, 0, tzinfo=timezone.utc)
    assert (event.local_time, event.weekday) == ("09:00", 5)


def test_scheduler_logs_snooze_time_when_a_snooze_fires(db_session, make_user, monkeypatch):
    _delivered(monkeypatch)
    user = make_user()
    now = datetime(2026, 9, 26, 12, 0, 30, tzinfo=timezone.utc)
    snoozed_until = now - timedelta(seconds=30)
    reminder = _claimed(
        db_session,
        user,
        now,
        repeat="daily",
        datetime=now - timedelta(hours=3),
        local_time="09:00",
        snoozed_until=snoozed_until,
    )

    _process_reminder(db_session, reminder, now, user_timezone="UTC")
    db_session.commit()

    (event,) = _events(db_session, reminder.id)
    assert event.scheduled_for == snoozed_until


def test_failed_push_logs_nothing(db_session, make_user, block_real_push):
    user = make_user()
    now = datetime.now(timezone.utc)
    reminder = _claimed(db_session, user, now, datetime=now - timedelta(minutes=1))

    _process_reminder(db_session, reminder, now, user_timezone="UTC")
    db_session.commit()

    assert block_real_push.called
    assert _events(db_session, reminder.id) == []


def test_notifications_off_logs_nothing(db_session, make_user, monkeypatch):
    _delivered(monkeypatch)
    user = make_user(notifications_enabled=False)
    now = datetime.now(timezone.utc)
    reminder = _claimed(db_session, user, now, datetime=now - timedelta(minutes=1))

    _process_reminder(db_session, reminder, now, user_timezone="UTC")
    db_session.commit()

    assert _events(db_session, reminder.id) == []
