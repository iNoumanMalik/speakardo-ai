from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime, timezone
from uuid import UUID
from typing import Any, Optional
from models import ReminderStatus

class ReminderCreate(BaseModel):
    task: str
    datetime: datetime
    repeat: Optional[str] = None
    user_id: Optional[UUID] = None  # Optional for MVP

    @field_validator("datetime")
    @classmethod
    def datetime_as_utc_naive(cls, v: datetime) -> datetime:
        """Store UTC wall time as naive so scheduler (UTC now) compares correctly."""
        if v.tzinfo is not None:
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v

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
    recent_reminders: Optional[list[dict[str, Any]]] = None


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
    def datetime_as_utc_naive(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return None
        if v.tzinfo is not None:
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v


class DeviceRegisterRequest(BaseModel):
    user_id: Optional[UUID] = None
    device_token: str
    platform: Optional[str] = None


class DeviceRegisterResponse(BaseModel):
    message: str
