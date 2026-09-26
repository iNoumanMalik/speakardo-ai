"""Server-side chat history (conversation_messages)."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

import models

# A gap longer than this starts a new chat session.
SESSION_GAP = timedelta(minutes=30)


def resolve_session_id(db: Session, user_id: UUID, now: datetime) -> UUID:
    """Continue the latest session if the user spoke recently, else start a new one."""
    latest = (
        db.query(models.ConversationMessage.session_id, models.ConversationMessage.created_at)
        .filter(models.ConversationMessage.user_id == user_id)
        .order_by(
            models.ConversationMessage.created_at.desc(),
            models.ConversationMessage.id.desc(),
        )
        .first()
    )
    if latest and now - latest.created_at < SESSION_GAP:
        return latest.session_id
    return uuid4()


def record_exchange(
    db: Session,
    *,
    user_id: UUID,
    user_text: str,
    reply: str,
    intent: Optional[str],
    received_at: datetime,
    replied_at: datetime,
) -> tuple[models.ConversationMessage, models.ConversationMessage]:
    """Add the user message and the assistant reply. The caller commits."""
    # History is ordered by created_at: the reply must sort after the message.
    if replied_at <= received_at:
        replied_at = received_at + timedelta(microseconds=1)
    session_id = resolve_session_id(db, user_id, received_at)
    user_msg = models.ConversationMessage(
        user_id=user_id,
        session_id=session_id,
        role=models.ChatRole.USER,
        content=user_text,
        intent=intent,
        created_at=received_at,
    )
    assistant_msg = models.ConversationMessage(
        user_id=user_id,
        session_id=session_id,
        role=models.ChatRole.ASSISTANT,
        content=reply,
        created_at=replied_at,
    )
    db.add_all([user_msg, assistant_msg])
    return user_msg, assistant_msg


def get_message_for_user(
    db: Session, user_id: UUID, message_id: UUID
) -> Optional[models.ConversationMessage]:
    return (
        db.query(models.ConversationMessage)
        .filter(
            models.ConversationMessage.id == message_id,
            models.ConversationMessage.user_id == user_id,
        )
        .first()
    )


def list_history(
    db: Session,
    user_id: UUID,
    *,
    before: Optional[models.ConversationMessage] = None,
    limit: int = 50,
) -> tuple[list[models.ConversationMessage], bool]:
    """Newest-first page of a user's messages, older than ``before`` when given."""
    msg = models.ConversationMessage
    query = db.query(msg).filter(msg.user_id == user_id)
    if before is not None:
        query = query.filter(
            or_(
                msg.created_at < before.created_at,
                and_(msg.created_at == before.created_at, msg.id < before.id),
            )
        )
    rows = query.order_by(msg.created_at.desc(), msg.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    return rows[:limit], has_more


_PURGE_SQL = """
DELETE FROM conversation_messages m
USING users u
WHERE m.user_id = u.id
  AND u.chat_retention_days IS NOT NULL
  AND m.created_at < :now - make_interval(days => u.chat_retention_days)
"""


def purge_expired_messages(
    db: Session, now: datetime, *, user_id: Optional[UUID] = None
) -> int:
    """Delete messages older than each user's retention (NULL = keep forever).

    Scoped to one user when ``user_id`` is given. The caller commits.
    """
    sql = _PURGE_SQL
    params: dict = {"now": now}
    if user_id is not None:
        sql += "  AND u.id = :user_id\n"
        params["user_id"] = user_id
    result = db.execute(text(sql), params)
    return result.rowcount or 0
