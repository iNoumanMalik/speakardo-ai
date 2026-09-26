"""Chat history retention: per-user setting, immediate purge on change, daily job."""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import models
from services import scheduler as scheduler_module
from services.chat_history import purge_expired_messages
from services.scheduler import purge_expired_chat_history

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)


def _add_message(db, user, *, age_days, content=None, now=NOW):
    msg = models.ConversationMessage(
        user_id=user.id,
        session_id=uuid4(),
        role=models.ChatRole.USER,
        content=content or f"{age_days} days old",
        created_at=now - timedelta(days=age_days),
    )
    db.add(msg)
    db.commit()
    return msg


def _contents(db, user):
    rows = (
        db.query(models.ConversationMessage.content)
        .filter(models.ConversationMessage.user_id == user.id)
        .order_by(models.ConversationMessage.created_at.desc())
        .all()
    )
    return [r.content for r in rows]


# --- purge_expired_messages ----------------------------------------------------


def _keep_forever(db, user):
    # Set after insert: on INSERT, None falls back to the column default (90).
    user.chat_retention_days = None
    db.commit()
    return user


def test_purge_uses_each_users_own_retention(db_session, make_user):
    short, default, forever = (
        make_user(chat_retention_days=30),
        make_user(),
        _keep_forever(db_session, make_user()),
    )
    for user in (short, default, forever):
        for age in (10, 45, 120):
            _add_message(db_session, user, age_days=age)

    deleted = purge_expired_messages(db_session, NOW)
    db_session.commit()

    assert deleted == 3  # short: 45 + 120; default: 120; forever: none
    assert _contents(db_session, short) == ["10 days old"]
    assert _contents(db_session, default) == ["10 days old", "45 days old"]
    assert _contents(db_session, forever) == ["10 days old", "45 days old", "120 days old"]


def test_purge_can_be_scoped_to_one_user(db_session, make_user):
    alice, bob = make_user(chat_retention_days=30), make_user(chat_retention_days=30)
    _add_message(db_session, alice, age_days=60)
    _add_message(db_session, bob, age_days=60)

    purge_expired_messages(db_session, NOW, user_id=alice.id)
    db_session.commit()

    assert _contents(db_session, alice) == []
    assert _contents(db_session, bob) == ["60 days old"]


def test_daily_job_purges_through_its_own_session(db_session, make_user):
    user = make_user(chat_retention_days=30)
    now = datetime.now(timezone.utc)
    _add_message(db_session, user, age_days=40, now=now)
    _add_message(db_session, user, age_days=1, now=now)

    deleted = asyncio.run(purge_expired_chat_history())

    db_session.expire_all()
    assert deleted == 1
    assert _contents(db_session, user) == ["1 days old"]


def test_scheduler_registers_the_daily_purge(monkeypatch):
    class RecordingScheduler:
        def __init__(self):
            self.jobs = []

        def add_job(self, func, trigger, **kwargs):
            self.jobs.append((func, trigger, kwargs))

        def start(self):
            pass

    monkeypatch.setattr(scheduler_module, "AsyncIOScheduler", RecordingScheduler)

    scheduler = scheduler_module.start_scheduler()

    jobs = {func: (trigger, kwargs) for func, trigger, kwargs in scheduler.jobs}
    assert scheduler_module.check_due_reminders in jobs
    trigger, kwargs = jobs[purge_expired_chat_history]
    assert (trigger, kwargs["hours"]) == ("interval", 24)
    assert kwargs["next_run_time"] > datetime.now(timezone.utc)


# --- API ---------------------------------------------------------------------


def test_new_users_keep_90_days_by_default(client, make_user, auth_headers):
    user = make_user()
    body = client.get("/users/me", headers=auth_headers(user)).json()
    assert body["chat_retention_days"] == 90


def test_shortening_retention_deletes_old_messages_now(client, db_session, make_user, auth_headers):
    user, other = make_user(), make_user()
    now = datetime.now(timezone.utc)
    _add_message(db_session, user, age_days=60, now=now)
    _add_message(db_session, user, age_days=5, now=now)
    _add_message(db_session, other, age_days=60, now=now)

    response = client.patch(
        "/users/me/preferences", json={"chat_retention_days": 30}, headers=auth_headers(user)
    )

    assert response.status_code == 200
    assert response.json()["chat_retention_days"] == 30
    db_session.expire_all()
    assert _contents(db_session, user) == ["5 days old"]
    assert _contents(db_session, other) == ["60 days old"]


def test_null_keeps_history_forever(client, db_session, make_user, auth_headers):
    user = make_user(chat_retention_days=30)
    _add_message(db_session, user, age_days=400, now=datetime.now(timezone.utc))

    response = client.patch(
        "/users/me/preferences", json={"chat_retention_days": None}, headers=auth_headers(user)
    )

    assert response.status_code == 200
    assert response.json()["chat_retention_days"] is None
    db_session.refresh(user)
    assert user.chat_retention_days is None
    assert purge_expired_messages(db_session, datetime.now(timezone.utc)) == 0
    assert _contents(db_session, user) == ["400 days old"]


def test_invalid_retention_is_rejected(client, make_user, auth_headers):
    response = client.patch(
        "/users/me/preferences", json={"chat_retention_days": 45}, headers=auth_headers(make_user())
    )
    assert response.status_code == 422


def test_empty_preferences_body_is_still_rejected(client, make_user, auth_headers):
    response = client.patch("/users/me/preferences", json={}, headers=auth_headers(make_user()))
    assert response.status_code == 400


def test_other_preferences_leave_retention_unchanged(client, make_user, auth_headers):
    user = make_user(chat_retention_days=365)

    response = client.patch(
        "/users/me/preferences", json={"notifications_enabled": False}, headers=auth_headers(user)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["notifications_enabled"] is False
    assert body["chat_retention_days"] == 365
