"""Retrieval: scoring (pure) and pgvector search with its filters (Postgres)."""

import math
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from ai_service.memory.scoring import MIN_SIMILARITY, rank, recency, score
from services import memory_store

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
DIM = 1536


def _axis(i: int, j: int = None, mix: float = 0.0) -> list[float]:
    """Unit vector on axis i, optionally tilted towards axis j (cosine = cos of the tilt)."""
    v = [0.0] * DIM
    v[i] = math.cos(mix)
    if j is not None:
        v[j] = math.sin(mix)
    return v


# --- scoring -------------------------------------------------------------------------


def test_score_is_a_weighted_sum():
    assert score(similarity=1, importance=1, confidence=1, kind="fact", age_days=0) == pytest.approx(1.0)
    assert score(similarity=0.8, importance=0.9, confidence=1.0, kind="fact", age_days=0) == pytest.approx(
        0.55 * 0.8 + 0.20 * 0.9 + 0.15 * 1.0 + 0.10
    )


def test_lasting_facts_keep_full_recency_events_decay():
    assert recency("important_date", 365, temporary=False) == 1.0
    assert recency("event", 30, temporary=False) == pytest.approx(math.exp(-1))
    assert recency("fact", 30, temporary=True) == pytest.approx(math.exp(-1))


def test_rank_drops_low_confidence_and_off_topic_and_orders_by_score():
    items = [
        ("birthday", 0.80, 0.9, 1.0, "important_date", 400, False),
        ("coffee", 0.82, 0.3, 1.0, "preference", 1, False),
        ("guess", 0.95, 0.9, 0.4, "fact", 1, False),  # confidence < 0.5
        ("unrelated", MIN_SIMILARITY - 0.01, 0.9, 1.0, "fact", 1, False),
    ]
    assert [s.item for s in rank(items)] == ["birthday", "coffee"]


def test_rank_respects_the_limit():
    items = [(i, 0.9, 0.5, 1.0, "fact", 0, False) for i in range(15)]
    assert len(rank(items, limit=10)) == 10


# --- pgvector search ---------------------------------------------------------------


def _save(db, user, content, embedding, *, model="fake", **fields):
    values = dict(kind="fact", category="other", key=None, subject=None, value=None,
                  source="conversation", confidence=1.0, importance=0.5, now=NOW)
    values.update(fields)
    memory = memory_store.save_memory(
        db, user.id, content=content, embedding=embedding, embedding_model=model, **values
    ).memory
    db.commit()
    return memory


def test_semantic_candidates_are_ordered_by_similarity(db_session, make_user):
    user = make_user()
    _save(db_session, user, "Far", _axis(0, 1, mix=1.2))
    _save(db_session, user, "Near", _axis(0, 1, mix=0.2))
    _save(db_session, user, "Middle", _axis(0, 1, mix=0.7))

    results = memory_store.semantic_candidates(db_session, user.id, _axis(0), model="fake", now=NOW)

    assert [m.content for m, _ in results] == ["Near", "Middle", "Far"]
    assert results[0][1] == pytest.approx(math.cos(0.2), abs=1e-4)


def test_semantic_candidates_filter_what_must_not_be_used(db_session, make_user):
    # Different directions, so the store's duplicate check doesn't merge them.
    user, other = make_user(), make_user()
    _save(db_session, user, "Mine", _axis(0))
    _save(db_session, other, "Someone else's", _axis(0))
    _save(db_session, user, "Other model", _axis(1), model="old-model")
    _save(db_session, user, "Expired", _axis(2), temporary_days=1)
    forgotten = _save(db_session, user, "Forgotten", _axis(3))
    memory_store.forget(db_session, forgotten, now=NOW)
    db_session.commit()

    results = memory_store.semantic_candidates(
        db_session, user.id, _axis(0), model="fake", now=NOW + timedelta(days=2)
    )

    assert [m.content for m, _ in results] == ["Mine"]


def test_profile_holds_the_important_basics(db_session, make_user):
    user = make_user()
    _save(db_session, user, "Your name is Nomi", _axis(0), importance=0.8)
    _save(db_session, user, "You like green tea", _axis(1), importance=0.3)

    assert [m.content for m in memory_store.profile_memories(db_session, user.id, now=NOW)] == [
        "Your name is Nomi"
    ]
