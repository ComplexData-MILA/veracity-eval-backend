from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional, List


class ConversationCreate(BaseModel):
    """Schema for creating a conversation."""


class ConversationUpdate(BaseModel):
    """Schema for updating a conversation."""

    status: str


class ConversationRead(BaseModel):
    """Schema for reading a conversation."""

    id: UUID
    user_id: UUID
    start_time: datetime
    end_time: Optional[datetime]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationList(BaseModel):
    """Schema for paginated conversation list."""

    items: List[ConversationRead]
    total: int
    limit: int
    offset: int
