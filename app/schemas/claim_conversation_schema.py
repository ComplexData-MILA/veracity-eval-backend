from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional


class ClaimConversationCreate(BaseModel):
    conversation_id: UUID
    claim_id: UUID


class ClaimConversationRead(BaseModel):
    id: UUID
    conversation_id: UUID
    claim_id: UUID
    start_time: datetime
    end_time: Optional[datetime]
    status: str

    model_config = ConfigDict(from_attributes=True)
