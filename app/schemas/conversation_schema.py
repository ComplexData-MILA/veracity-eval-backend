from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID
from typing import Optional, List
from app.schemas.claim_conversation_schema import ClaimConversationRead


class ConversationCreate(BaseModel):
    user_id: UUID


class ConversationRead(BaseModel):
    id: UUID
    user_id: UUID
    start_time: datetime
    end_time: Optional[datetime]
    status: str
    claim_conversations: List[ClaimConversationRead] = []

    model_config = ConfigDict(from_attributes=True)
