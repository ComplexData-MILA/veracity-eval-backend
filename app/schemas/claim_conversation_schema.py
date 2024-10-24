from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional


class ClaimConversationCreate(BaseModel):
    """Schema for creating a claim conversation."""

    claim_id: UUID


class ClaimConversationRead(BaseModel):
    """Schema for reading a claim conversation."""

    id: UUID
    conversation_id: UUID
    claim_id: UUID
    start_time: datetime
    end_time: Optional[datetime]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
