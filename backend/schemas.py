from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from services.repeat_schedule import validate_repeat_field
from datetime import datetime, timezone

# Avoid field name `datetime` shadowing the `datetime` type in Optional[datetime].
DateTime = datetime
from uuid import UUID
from typing import Any, Optional
from models import ReminderStatus


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    email_verified: bool = True


class MessageResponse(BaseModel):
    message: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=256)
    password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10, max_length=256)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class GoogleAuthRequest(BaseModel):
    id_token: str = Field(min_length=10, max_length=8192)


class ReminderCreate(BaseModel):
    task: str
    datetime: datetime
    repeat: Optional[str] = None

    @field_validator("repeat")
    @classmethod
    def validate_repeat(cls, v: Optional[str]) -> Optional[str]:
        return validate_repeat_field(v)

    @field_validator("datetime")
    @classmethod
    def datetime_as_utc(cls, v: datetime) -> datetime:
        """Normalize reminder timestamps to timezone-aware UTC."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

class ReminderResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    task: str
    datetime: datetime
    repeat: Optional[str]
    status: ReminderStatus
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ChatRequest(BaseModel):
    message: str
    pending_context: Optional[dict[str, Any]] = None


class ChatResponse(BaseModel):
    reply: str
    parsed_reminder: Optional[dict[str, Any]] = None
    client_action: Optional[dict[str, Any]] = None


class ReminderSnooze(BaseModel):
    minutes: int = Field(description="Snooze duration in minutes")

    @field_validator("minutes")
    @classmethod
    def validate_minutes(cls, value: int) -> int:
        if value not in (5, 10, 30):
            raise ValueError("minutes must be 5, 10, or 30")
        return value


class ReminderUpdate(BaseModel):
    task: Optional[str] = None
    datetime: Optional[DateTime] = None
    repeat: Optional[str] = None

    @field_validator("repeat")
    @classmethod
    def validate_repeat(cls, v: Optional[str]) -> Optional[str]:
        return validate_repeat_field(v)

    @field_validator("datetime")
    @classmethod
    def datetime_as_utc(cls, v: Optional[DateTime]) -> Optional[DateTime]:
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class ReminderRepublish(BaseModel):
    """Re-activate a reminder for scheduling (optional field updates)."""

    task: Optional[str] = None
    datetime: Optional[DateTime] = None
    repeat: Optional[str] = None

    @field_validator("repeat")
    @classmethod
    def validate_repeat(cls, v: Optional[str]) -> Optional[str]:
        return validate_repeat_field(v)

    @field_validator("datetime")
    @classmethod
    def datetime_as_utc(cls, v: Optional[DateTime]) -> Optional[DateTime]:
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class DeviceRegisterRequest(BaseModel):
    device_token: str
    platform: Optional[str] = None


class DeviceRegisterResponse(BaseModel):
    message: str


class UserProfileResponse(BaseModel):
    id: UUID
    email: EmailStr
    email_verified: bool
    timezone: str
    notifications_enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedbackCreate(BaseModel):
    message: str = Field(min_length=3, max_length=2000)


class FeedbackResponse(BaseModel):
    message: str


class UserTimezoneUpdate(BaseModel):
    timezone: str = Field(min_length=1, max_length=64)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Timezone cannot be empty")
        try:
            ZoneInfo(cleaned)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Invalid timezone") from exc
        return cleaned


class UserPreferencesUpdate(BaseModel):
    timezone: Optional[str] = None
    notifications_enabled: Optional[bool] = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Timezone cannot be empty")
        try:
            ZoneInfo(cleaned)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Invalid timezone") from exc
        return cleaned
