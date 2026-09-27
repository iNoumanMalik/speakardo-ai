"""Memory store on Postgres: save/update/duplicate, forget and undo, erase, backfill."""

import asyncio
import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import models
from services import memory_store
from services.scheduler import backfill_memory_embeddings, erase_forgotten_memories

from ai_service.gateway.fakes import FakeEmbeddingProvider, fake_vector

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
S = models.MemoryStatus


def _save(db, user, content="Your office is in Blue Area", **fields):
    values = dict(
        content=content,
        kind="fact",
        category="work",
        key="work_location",
        subject=None,
        value=None,
        source="user_explicit",
        confidence=1.0,
        importance=0.6,
        now=NOW,
    )
    values.update(fields)
    outcome = memory_store.save_memory(db, user.id, **values)
    db.commit()
    return outcome


def _events(db, memory):
    return [
        e.action
        for e in db.query(models.MemoryEvent)
        .filter(models.MemoryEvent.memory_id == memory.id)
        .order_by(models.MemoryEvent.created_at)
    ]


def _nearby(vector, delta=0.001):
    moved = [v + delta for v in vector]
    norm = math.sqrt(sum(v * v for v in moved))
    return [v / norm for v in moved]


# --- save ----------------------------------------------------------------------


def test_save_creates_memory_and_event_without_content(db_session, make_user):
    user = make_user()
    outcome = _save(db_session, user)

    assert outcome.action == "saved"
    assert outcome.memory.status == S.ACTIVE
    event = db_session.query(models.MemoryEvent).one()
    assert event.action == "created"
    assert "Blue Area" not in json.dumps(event.detail)


def test_same_key_with_new_value_supersedes_the_old_one(db_session, make_user):
    user = make_user()
    old = _save(db_session, user, "Your office is in Blue Area").memory
    outcome = _save(db_session, user, "Your office is in F-7")

    db_session.refresh(old)
    assert outcome.action == "updated"
    assert outcome.previous.id == old.id
    assert (old.status, old.superseded_by) == (S.SUPERSEDED, outcome.memory.id)
    assert [m.content for m in memory_store.list_active(db_session, user.id)] == ["Your office is in F-7"]


def test_same_wording_is_a_duplicate(db_session, make_user):
    user = make_user()
    first = _save(db_session, user, "Your office is in Blue Area").memory
    again = _save(db_session, user, "your office is in blue area!")

    assert again.action == "duplicate"
    assert again.memory.id == first.id
    assert db_session.query(models.Memory).count() == 1


def test_nearly_identical_meaning_is_a_duplicate(db_session, make_user):
    user = make_user()
    vector = fake_vector("office")
    _save(db_session, user, "Office: Blue Area", key=None, embedding=vector, embedding_model="fake")

    near = _save(db_session, user, "My workplace is Blue Area", key=None,
                 embedding=_nearby(vector), embedding_model="fake")
    far = _save(db_session, user, "Sara likes tea", key=None,
                embedding=fake_vector("tea"), embedding_model="fake")

    assert near.action == "duplicate"
    assert far.action == "saved"


def test_temporary_memories_expire(db_session, make_user):
    user = make_user()
    _save(db_session, user, "You're in Karachi this week", key=None, temporary_days=7)

    assert len(memory_store.list_active(db_session, user.id, now=NOW + timedelta(days=6))) == 1
    assert memory_store.list_active(db_session, user.id, now=NOW + timedelta(days=8)) == []


# --- lookup ------------------------------------------------------------------------


def test_exact_lookup_by_key_and_person_is_scoped_to_the_user(db_session, make_user):
    alice, bob = make_user(), make_user()
    _save(db_session, alice, "Sara's birthday is June 15", key="birthday", subject="sara",
          kind="important_date", category="people")
    _save(db_session, alice, "Your birthday is March 3", key="birthday", subject=None,
          kind="important_date", category="personal")

    sara = memory_store.find_exact(db_session, alice.id, key="birthday", subject="sara", now=NOW)
    mine = memory_store.find_exact(db_session, alice.id, key="birthday", subject=None, now=NOW)

    assert [m.content for m in sara] == ["Sara's birthday is June 15"]
    assert [m.content for m in mine] == ["Your birthday is March 3"]
    assert memory_store.find_exact(db_session, bob.id, key="birthday", subject="sara", now=NOW) == []


def test_forget_targets_fall_back_to_words(db_session, make_user):
    user = make_user()
    _save(db_session, user, "You work at XYZ Corp", key="employer")
    _save(db_session, user, "Your dog is called Max", key="pet_name", category="personal")

    targets = memory_store.find_forget_targets(
        db_session, user.id, text="I work at XYZ", key=None, subject=None, now=NOW
    )
    assert [t.content for t in targets] == ["You work at XYZ Corp"]


# --- forget and undo ------------------------------------------------------------------


def test_forget_hides_and_undo_restores(db_session, make_user):
    user = make_user()
    memory = _save(db_session, user).memory

    memory_store.forget(db_session, memory, now=NOW)
    db_session.commit()
    assert memory_store.list_active(db_session, user.id, now=NOW) == []

    assert memory_store.undo(db_session, memory, now=NOW) == "forget"
    db_session.commit()
    assert (memory.status, memory.deleted_at) == (S.ACTIVE, None)
    assert _events(db_session, memory) == ["created", "deleted", "restored"]


def test_undo_a_save_hides_it(db_session, make_user):
    user = make_user()
    memory = _save(db_session, user).memory

    assert memory_store.undo(db_session, memory, now=NOW) == "save"
    db_session.commit()
    assert memory.status == S.DELETED
    assert _events(db_session, memory)[-1] == "rejected"


def test_undo_an_update_brings_back_the_previous_version(db_session, make_user):
    user = make_user()
    old = _save(db_session, user, "Your office is in Blue Area").memory
    new = _save(db_session, user, "Your office is in F-7").memory

    assert memory_store.undo(db_session, new, now=NOW) == "update"
    db_session.commit()
    db_session.refresh(old)
    assert (old.status, old.superseded_by, new.status) == (S.ACTIVE, None, S.DELETED)


def test_nothing_left_to_undo(db_session, make_user):
    user = make_user()
    memory = _save(db_session, user).memory
    memory_store.undo(db_session, memory, now=NOW)
    db_session.commit()

    with pytest.raises(memory_store.NothingToUndo):
        memory_store.undo(db_session, memory, now=NOW)


# --- background jobs ----------------------------------------------------------------


def test_forgotten_memories_are_erased_after_24_hours(db_session, make_user):
    user = make_user()
    old = _save(db_session, user, "Old fact", key=None).memory
    recent = _save(db_session, user, "Recent fact", key=None).memory
    now = datetime.now(timezone.utc)
    memory_store.forget(db_session, old, now=now - timedelta(hours=25))
    memory_store.forget(db_session, recent, now=now - timedelta(hours=1))
    db_session.commit()
    old_id = old.id

    erased = asyncio.run(erase_forgotten_memories())

    db_session.expire_all()
    assert erased == 1
    assert db_session.get(models.Memory, old_id) is None
    assert db_session.get(models.Memory, recent.id) is not None
    # The audit trail survives the erase, without content.
    assert [e.action for e in db_session.query(models.MemoryEvent).filter_by(memory_id=old_id)] == [
        "created", "deleted",
    ]


def test_backfill_embeds_missing_and_outdated_rows(db_session, make_user):
    user = make_user()
    missing = _save(db_session, user, "Your city is Lahore", key="home_city").memory
    outdated = _save(db_session, user, "Sara likes tea", key=None,
                     embedding=fake_vector("x"), embedding_model="old-model").memory
    current = _save(db_session, user, "Your dog is Max", key="pet_name",
                    embedding=fake_vector("y"), embedding_model="fake-embedding").memory
    embedder = FakeEmbeddingProvider()

    count = asyncio.run(backfill_memory_embeddings(embedder))

    db_session.expire_all()
    assert count == 2
    assert embedder.calls == [["Your city is Lahore", "Sara likes tea"]]
    for memory in (missing, outdated, current):
        db_session.refresh(memory)
        assert memory.embedding_model == "fake-embedding"
