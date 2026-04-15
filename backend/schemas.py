from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from datetime import datetime, timezone
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


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ReminderCreate(BaseModel):
    task: str
    datetime: datetime
    repeat: Optional[str] = None

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


class ReminderUpdate(BaseModel):
    task: Optional[str] = None
    datetime: Optional[datetime] = None
    repeat: Optional[str] = None

    @field_validator("datetime")
    @classmethod
    def datetime_as_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
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
