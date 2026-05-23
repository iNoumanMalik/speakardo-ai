import uuid
from sqlalchemy import Boolean, Column, String, DateTime, ForeignKey, Enum, Integer, Text
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

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    timezone = Column(String, nullable=False, default="UTC", server_default="UTC")
    notifications_enabled = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Reminder(Base):
    __tablename__ = "reminders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    task = Column(String, index=True, nullable=False)
    datetime = Column(DateTime(timezone=True), nullable=False)
    repeat = Column(String, nullable=True)
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
