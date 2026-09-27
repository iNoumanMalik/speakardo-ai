"""All reads and writes of memories and their audit events (design §6, §7, §9).

Callers commit. Memory content is never logged and never copied into
memory_events; logs carry ids and event names only.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

import models

logger = logging.getLogger(__name__)

# Memories within this cosine distance of an existing one count as the same fact.
DUPLICATE_DISTANCE = 0.08
# Forgotten memories can be restored until they are erased, this long after Forget.
ERASE_AFTER = timedelta(hours=24)

Status = models.MemoryStatus


@dataclass
class SaveOutcome:
    """What save_memory did: 'saved', 'updated' (replaced `previous`) or 'duplicate'."""

    action: str
    memory: models.Memory
    previous: Optional[models.Memory] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalise_text(text: str) -> str:
    """Compare wording loosely: case, punctuation and spacing don't matter."""
    return " ".join(re.sub(r"[^\w\s]", "", (text or "").casefold()).split())


def log_event(
    db: Session,
    memory: models.Memory,
    action: str,
    *,
    actor: str = "user",
    detail: Optional[dict[str, Any]] = None,
) -> None:
    db.add(
        models.MemoryEvent(
            memory_id=memory.id,
            user_id=memory.user_id,
            action=action,
            actor=actor,
            detail=detail,
        )
    )
    logger.info(
        "event=memory_%s memory_id=%s user_id=%s actor=%s", action, memory.id, memory.user_id, actor
    )


def _active(db: Session, user_id: UUID, now: datetime):
    """Active memories that are currently valid (temporary ones not yet expired)."""
    return db.query(models.Memory).filter(
        models.Memory.user_id == user_id,
        models.Memory.status == Status.ACTIVE,
        or_(models.Memory.valid_until.is_(None), models.Memory.valid_until > now),
    )


def _find_duplicate(
    db: Session,
    user_id: UUID,
    content: str,
    subject: Optional[str],
    embedding: Optional[list[float]],
    embedding_model: Optional[str],
    now: datetime,
) -> Optional[models.Memory]:
    candidates = _active(db, user_id, now)
    if subject is None:
        candidates = candidates.filter(models.Memory.subject.is_(None))
    else:
        candidates = candidates.filter(models.Memory.subject == subject)
    wanted = _normalise_text(content)
    for row in candidates.all():
        if _normalise_text(row.content) == wanted:
            return row
    if embedding is not None and embedding_model:
        distance = models.Memory.embedding.cosine_distance(embedding)
        row = (
            _active(db, user_id, now)
            .filter(
                models.Memory.embedding.is_not(None),
                models.Memory.embedding_model == embedding_model,
                distance < DUPLICATE_DISTANCE,
            )
            .order_by(distance)
            .first()
        )
        if row is not None:
            return row
    return None


def save_memory(
    db: Session,
    user_id: UUID,
    *,
    content: str,
    kind: str,
    category: str,
    key: Optional[str],
    subject: Optional[str],
    value: Optional[dict[str, Any]],
    source: str,
    confidence: float,
    importance: float,
    temporary_days: Optional[int] = None,
    source_message_id: Optional[UUID] = None,
    embedding: Optional[list[float]] = None,
    embedding_model: Optional[str] = None,
    now: Optional[datetime] = None,
) -> SaveOutcome:
    """Store a memory that passed the save policy.

    - Same key + subject as an active memory: the old one is superseded (kept in history).
    - Same wording, or nearly the same meaning: nothing new is stored ('duplicate').
    """
    now = now or _now()
    previous = None
    if key:
        previous = (
            _active(db, user_id, now)
            .filter(models.Memory.key == key)
            .filter(
                models.Memory.subject.is_(None)
                if subject is None
                else models.Memory.subject == subject
            )
            .order_by(models.Memory.created_at.desc())
            .first()
        )
        if previous is not None and _normalise_text(previous.content) == _normalise_text(content):
            return SaveOutcome("duplicate", previous)
    if previous is None:
        duplicate = _find_duplicate(db, user_id, content, subject, embedding, embedding_model, now)
        if duplicate is not None:
            return SaveOutcome("duplicate", duplicate)

    memory = models.Memory(
        user_id=user_id,
        kind=kind,
        category=category,
        key=key,
        subject=subject,
        content=content,
        value=value,
        source=source,
        source_message_id=source_message_id,
        confidence=confidence,
        importance=importance,
        valid_from=now,
        valid_until=now + timedelta(days=temporary_days) if temporary_days else None,
        embedding=embedding,
        embedding_model=embedding_model if embedding is not None else None,
        created_at=now,
        updated_at=now,
    )
    db.add(memory)
    db.flush()

    if previous is not None:
        previous.status = Status.SUPERSEDED
        previous.superseded_by = memory.id
        log_event(db, memory, "updated", detail={"previous_id": str(previous.id)})
        return SaveOutcome("updated", memory, previous)

    log_event(db, memory, "created", detail={"source": source})
    return SaveOutcome("saved", memory)


def get_for_user(db: Session, user_id: UUID, memory_id: UUID) -> Optional[models.Memory]:
    return (
        db.query(models.Memory)
        .filter(models.Memory.id == memory_id, models.Memory.user_id == user_id)
        .first()
    )


def list_active(
    db: Session,
    user_id: UUID,
    *,
    kind: Optional[str] = None,
    category: Optional[str] = None,
    q: Optional[str] = None,
    now: Optional[datetime] = None,
) -> list[models.Memory]:
    query = _active(db, user_id, now or _now())
    if kind:
        query = query.filter(models.Memory.kind == kind)
    if category:
        query = query.filter(models.Memory.category == category)
    if q:
        query = query.filter(models.Memory.content.ilike(f"%{q.strip()}%"))
    return query.order_by(models.Memory.created_at.desc()).all()


def find_exact(
    db: Session,
    user_id: UUID,
    *,
    key: Optional[str],
    subject: Optional[str],
    now: Optional[datetime] = None,
) -> list[models.Memory]:
    """Exact lookup by key and/or person (design §8 step 1)."""
    if key is None and subject is None:
        return []
    query = _active(db, user_id, now or _now())
    if key is not None:
        query = query.filter(models.Memory.key == key)
    if subject is None:
        query = query.filter(models.Memory.subject.is_(None))
    else:
        query = query.filter(models.Memory.subject == subject)
    return query.order_by(models.Memory.importance.desc(), models.Memory.created_at.desc()).all()


_STOPWORDS = {
    "the", "and", "that", "this", "about", "with", "for", "from", "have", "has", "was",
    "were", "are", "is", "my", "me", "i", "a", "an", "of", "to", "in", "on", "at",
}


def find_forget_targets(
    db: Session,
    user_id: UUID,
    *,
    text: str,
    key: Optional[str],
    subject: Optional[str],
    now: Optional[datetime] = None,
) -> list[models.Memory]:
    """Memories a "forget …" request refers to: by key/person, else by its words."""
    exact = find_exact(db, user_id, key=key, subject=subject, now=now)
    if exact:
        return exact
    words = [w for w in re.findall(r"\w+", text.casefold()) if len(w) >= 3 and w not in _STOPWORDS]
    if not words:
        return []
    query = _active(db, user_id, now or _now())
    for word in words:
        query = query.filter(models.Memory.content.ilike(f"%{word}%"))
    return query.order_by(models.Memory.created_at.desc()).limit(5).all()


def forget(db: Session, memory: models.Memory, *, now: Optional[datetime] = None) -> None:
    """Hide a memory now; erase_forgotten() removes it for good after 24 hours."""
    memory.status = Status.DELETED
    memory.deleted_at = now or _now()
    log_event(db, memory, "deleted")


def mark_used(db: Session, memories: list[models.Memory], *, now: Optional[datetime] = None) -> None:
    now = now or _now()
    for memory in memories:
        memory.use_count = (memory.use_count or 0) + 1
        memory.last_used_at = now
        log_event(db, memory, "used", actor="system")


class NothingToUndo(Exception):
    pass


def undo(db: Session, memory: models.Memory, *, now: Optional[datetime] = None) -> str:
    """Reverse the latest user action on a memory. Returns what was undone.

    created → hidden ('rejected'); updated → the previous version comes back;
    deleted → restored. Anything else raises NothingToUndo.
    """
    now = now or _now()
    last = (
        db.query(models.MemoryEvent)
        .filter(
            models.MemoryEvent.memory_id == memory.id,
            models.MemoryEvent.action.in_(("created", "updated", "deleted", "rejected", "restored")),
        )
        .order_by(models.MemoryEvent.created_at.desc())
        .first()
    )
    if last is None:
        raise NothingToUndo()

    if last.action == "deleted" and memory.status == Status.DELETED:
        memory.status = Status.ACTIVE
        memory.deleted_at = None
        log_event(db, memory, "restored", detail={"reason": "undo"})
        return "forget"

    if last.action in ("created", "updated") and memory.status == Status.ACTIVE:
        memory.status = Status.DELETED
        memory.deleted_at = now
        log_event(db, memory, "rejected", detail={"reason": "undo"})
        if last.action == "updated":
            previous_id = (last.detail or {}).get("previous_id")
            previous = get_for_user(db, memory.user_id, UUID(previous_id)) if previous_id else None
            if previous is not None and previous.status == Status.SUPERSEDED:
                previous.status = Status.ACTIVE
                previous.superseded_by = None
                log_event(db, previous, "restored", detail={"reason": "undo_update"})
            return "update"
        return "save"

    raise NothingToUndo()


def erase_forgotten(db: Session, *, now: Optional[datetime] = None) -> int:
    """Hard-delete memories forgotten more than 24 hours ago, embeddings included.

    Their memory_events rows stay (no content, no foreign key).
    """
    cutoff = (now or _now()) - ERASE_AFTER
    deleted = (
        db.query(models.Memory)
        .filter(
            models.Memory.status == Status.DELETED,
            models.Memory.deleted_at.is_not(None),
            models.Memory.deleted_at < cutoff,
        )
        .delete(synchronize_session=False)
    )
    return deleted


def rows_needing_embedding(db: Session, *, model: str, limit: int = 50) -> list[models.Memory]:
    """Active, non-sensitive memories with no embedding or one from another model."""
    return (
        db.query(models.Memory)
        .filter(
            models.Memory.status == Status.ACTIVE,
            models.Memory.sensitivity == "normal",
            or_(
                models.Memory.embedding.is_(None),
                models.Memory.embedding_model.is_(None),
                models.Memory.embedding_model != model,
            ),
        )
        .order_by(models.Memory.created_at.asc())
        .limit(limit)
        .all()
    )


def count_active(db: Session, user_id: UUID) -> int:
    return (
        db.query(func.count(models.Memory.id))
        .filter(models.Memory.user_id == user_id, models.Memory.status == Status.ACTIVE)
        .scalar()
        or 0
    )


# How many nearest memories to fetch before ranking (design §8: top 20).
SEMANTIC_CANDIDATES = 20
PROFILE_MIN_IMPORTANCE = 0.6


def semantic_candidates(
    db: Session,
    user_id: UUID,
    embedding: list[float],
    *,
    model: str,
    limit: int = SEMANTIC_CANDIDATES,
    now: Optional[datetime] = None,
) -> list[tuple[models.Memory, float]]:
    """Nearest active, currently valid memories as (memory, cosine similarity).

    Only rows embedded with the same model are comparable.
    """
    distance = models.Memory.embedding.cosine_distance(embedding)
    rows = (
        _active(db, user_id, now or _now())
        .filter(
            models.Memory.embedding.is_not(None),
            models.Memory.embedding_model == model,
        )
        .add_columns(distance.label("distance"))
        .order_by(distance)
        .limit(limit)
        .all()
    )
    return [(memory, 1.0 - float(d)) for memory, d in rows]


def profile_memories(
    db: Session, user_id: UUID, *, limit: int = 6, now: Optional[datetime] = None
) -> list[models.Memory]:
    """Always-on profile: the most important basics, for every reply (design §8)."""
    return (
        _active(db, user_id, now or _now())
        .filter(
            models.Memory.importance >= PROFILE_MIN_IMPORTANCE,
            models.Memory.sensitivity == "normal",
        )
        .order_by(models.Memory.importance.desc(), models.Memory.created_at.desc())
        .limit(limit)
        .all()
    )
