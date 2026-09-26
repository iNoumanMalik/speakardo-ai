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
    Integer,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
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
