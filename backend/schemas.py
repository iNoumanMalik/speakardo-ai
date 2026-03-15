from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional
from models import ReminderStatus

class ReminderCreate(BaseModel):
    task: str
    datetime: datetime
    repeat: Optional[str] = None
    user_id: Optional[UUID] = None  # Optional for MVP

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

class ChatResponse(BaseModel):
    reply: str
    parsed_reminder: Optional[dict] = None
