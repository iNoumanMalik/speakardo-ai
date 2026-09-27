import uuid
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    String,
    DateTime,
    ForeignKey,
    Enum,
    Index,
    Float,
    Integer,
    SmallInteger,
    Text,
    text,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID
from datetime import datetime, timezone
from database import Base
import enum

class ReminderStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    TRIGGERED = "triggered"
    COMPLETED = "completed"
    FAILED = "failed"


class DeliveryStatus(str, enum.Enum):
    SUCCESS = "success"
    TEMP_FAILURE = "temp_failure"
    PERM_FAILURE = "perm_failure"

class AuthTokenPurpose:
    EMAIL_VERIFY = "email_verify"
    PASSWORD_RESET = "password_reset"


class ChatRole:
    USER = "user"
    ASSISTANT = "assistant"


# Days of chat history a user can choose to keep; NULL on the user means forever.
CHAT_RETENTION_CHOICES = (30, 90, 365)
DEFAULT_CHAT_RETENTION_DAYS = 90


class ReminderEventType:
    CREATED = "created"
    FIRED = "fired"
    SNOOZED = "snoozed"
    COMPLETED = "completed"
    # Reserved: nothing observes a dismissal yet (Flutter event tracking arrives in 8B).
    DISMISSED = "dismissed"
    EDITED = "edited"
    DELETED = "deleted"


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=True)
    firebase_uid = Column(String, unique=True, index=True, nullable=True)
    email_verified = Column(Boolean, nullable=False, default=False, server_default="false")
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    timezone = Column(String, nullable=False, default="UTC", server_default="UTC")
    notifications_enabled = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # Chat history older than this is deleted daily; NULL keeps it forever.
    chat_retention_days = Column(
        Integer,
        nullable=True,
        default=DEFAULT_CHAT_RETENTION_DAYS,
        server_default=str(DEFAULT_CHAT_RETENTION_DAYS),
    )
    # Memory privacy settings. memory_enabled=False saves nothing; with
    # learn_from_chat=False only explicit "remember that ..." requests are saved.
    memory_enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    learn_from_chat = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), nullable=False, index=True)
    purpose = Column(String(32), nullable=False, index=True)
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Reminder(Base):
    __tablename__ = "reminders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    task = Column(String, index=True, nullable=False)
    datetime = Column(DateTime(timezone=True), nullable=False)
    repeat = Column(String, nullable=True)
    local_time = Column(String(5), nullable=True)
    local_weekday = Column(Integer, nullable=True)
    local_day_of_month = Column(Integer, nullable=True)
    snoozed_until = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, default=ReminderStatus.PENDING.value, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    triggered_at = Column(DateTime(timezone=True), nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    platform = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    reminder_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reminders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_token_id = Column(UUID(as_uuid=True), ForeignKey("device_tokens.id"), nullable=False, index=True)
    dedupe_key = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, default=DeliveryStatus.TEMP_FAILURE.value, nullable=False)
    provider_message_id = Column(String, nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ConversationMessage(Base):
    """One chat turn (user or assistant), stored so history survives app restarts."""

    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant')", name="ck_conversation_messages_role"
        ),
        # Serves newest-first keyset pagination (Postgres scans it backwards).
        Index("ix_conversation_messages_user_created", "user_id", "created_at", "id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id = Column(UUID(as_uuid=True), nullable=False)
    role = Column(String(16), nullable=False)
    content = Column(Text, nullable=False)
    intent = Column(String(32), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class ReminderEvent(Base):
    """Append-only log of what happened to a reminder; raw input for 8B habit mining."""

    __tablename__ = "reminder_events"
    __table_args__ = (
        CheckConstraint(
            "event IN ('created', 'fired', 'snoozed', 'completed', 'dismissed', 'edited', 'deleted')",
            name="ck_reminder_events_event",
        ),
        Index("ix_reminder_events_user_occurred", "user_id", "occurred_at"),
        Index("ix_reminder_events_reminder_id", "reminder_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # No foreign key: the log must outlive the reminder (the 'deleted' event).
    reminder_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event = Column(String(16), nullable=False)
    # The fire time this event is about.
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    occurred_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    # occurred_at in the user's timezone: "HH:MM" and weekday 0=Mon..6=Sun.
    local_time = Column(String(5), nullable=True)
    weekday = Column(SmallInteger, nullable=True)


# --- Module 8: memories ----------------------------------------------------------
# Allowed values, mirrored by CHECK constraints (and by ai_service/memory/keys.py,
# which validates what the AI returns; tests keep the two in sync).
MEMORY_KINDS = ("fact", "preference", "important_date", "relationship", "note", "event")
MEMORY_CATEGORIES = (
    "personal", "work", "people", "health", "finance", "places", "routine", "other",
)
MEMORY_SOURCES = (
    "user_explicit", "conversation", "reminder", "onboarding", "manual_edit", "behavior",
)
MEMORY_SENSITIVITIES = ("normal", "private", "sensitive")
MEMORY_EVENT_ACTIONS = (
    "created", "updated", "used", "confirmed", "rejected", "deleted", "restored",
)
MEMORY_EMBEDDING_DIMENSIONS = 1536  # = ai_service.gateway.embeddings.EMBEDDING_DIMENSIONS


class MemoryStatus:
    ACTIVE = "active"
    PENDING_CONFIRMATION = "pending_confirmation"
    SUPERSEDED = "superseded"
    DELETED = "deleted"  # hidden by Forget; erased 24 hours after deleted_at

    ALL = (ACTIVE, PENDING_CONFIRMATION, SUPERSEDED, DELETED)


def _in(column: str, values: tuple) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Memory(Base):
    """Something the user told Speakardo, in their words, plus structure for lookups."""

    __tablename__ = "memories"
    __table_args__ = (
        CheckConstraint(_in("kind", MEMORY_KINDS), name="ck_memories_kind"),
        CheckConstraint(_in("category", MEMORY_CATEGORIES), name="ck_memories_category"),
        CheckConstraint(_in("source", MEMORY_SOURCES), name="ck_memories_source"),
        CheckConstraint(_in("sensitivity", MEMORY_SENSITIVITIES), name="ck_memories_sensitivity"),
        CheckConstraint(_in("status", MemoryStatus.ALL), name="ck_memories_status"),
        Index("ix_memories_user_status", "user_id", "status"),
        Index("ix_memories_user_key_subject", "user_id", "key", "subject"),
        Index(
            "ix_memories_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind = Column(String(24), nullable=False)
    category = Column(String(16), nullable=False)
    # Normalised slot from ai_service/memory/keys.py (birthday, work_location, ...).
    key = Column(String(48), nullable=True)
    # Interim person label ("sara", "mother"); NULL = about the user. The people
    # table replaces this in 8.3.
    subject = Column(String(80), nullable=True)
    content = Column(Text, nullable=False)
    value = Column(JSONB, nullable=True)
    source = Column(String(24), nullable=False)
    source_message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversation_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Rule-based (1.0 stated, 0.8 implied, <= 0.6 inferred), never the AI's estimate.
    confidence = Column(Float, nullable=False)
    importance = Column(Float, nullable=False)
    sensitivity = Column(String(12), nullable=False, default="normal", server_default="normal")
    status = Column(
        String(24), nullable=False, default=MemoryStatus.ACTIVE, server_default=MemoryStatus.ACTIVE
    )
    superseded_by = Column(
        UUID(as_uuid=True), ForeignKey("memories.id", ondelete="SET NULL"), nullable=True
    )
    valid_from = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    valid_until = Column(DateTime(timezone=True), nullable=True)
    embedding = Column(Vector(MEMORY_EMBEDDING_DIMENSIONS), nullable=True)
    embedding_model = Column(String(64), nullable=True)
    use_count = Column(Integer, nullable=False, default=0, server_default="0")
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )


class MemoryEvent(Base):
    """Audit trail for memories. Never holds memory content."""

    __tablename__ = "memory_events"
    __table_args__ = (
        CheckConstraint(_in("action", MEMORY_EVENT_ACTIONS), name="ck_memory_events_action"),
        CheckConstraint("actor IN ('user', 'system')", name="ck_memory_events_actor"),
        Index("ix_memory_events_memory_id", "memory_id"),
        Index("ix_memory_events_user_created", "user_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # No foreign key: the audit line outlives the erased memory.
    memory_id = Column(UUID(as_uuid=True), nullable=False)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action = Column(String(16), nullable=False)
    actor = Column(String(8), nullable=False)
    # Ids and reasons only, e.g. {"previous_id": ..., "reason": "undo"}.
    detail = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=text("now()"),
    )
