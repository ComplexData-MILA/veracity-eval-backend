from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional


class MessageCreate(BaseModel):
    conversation_id: UUID
    sender_type: str
    content: str
    claim_conversation_id: Optional[UUID] = None
    claim_id: Optional[UUID] = None
    analysis_id: Optional[UUID] = None


class MessageRead(BaseModel):
    id: UUID
    conversation_id: UUID
    sender_type: str
    content: str
    timestamp: datetime
    claim_conversation_id: Optional[UUID] = None
    claim_id: Optional[UUID] = None
    analysis_id: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)
