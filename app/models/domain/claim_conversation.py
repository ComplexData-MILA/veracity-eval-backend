from dataclasses import dataclass
from typing import Optional
from uuid import UUID
from datetime import datetime

from app.models.database.claim_conversation import ClaimConversationModel
from app.models.database.conversation import ConversationStatus


@dataclass
class ClaimConversation:
    id: UUID
    conversation_id: UUID
    claim_id: UUID
    start_time: datetime
    status: str
    end_time: Optional[datetime] = None

    @classmethod
    def from_model(cls, model: "ClaimConversationModel") -> "ClaimConversation":
        return cls(
            id=model.id,
            conversation_id=model.conversation_id,
            claim_id=model.claim_id,
            start_time=model.start_time,
            end_time=model.end_time,
            status=model.status.value,
        )

    def to_model(self) -> "ClaimConversationModel":
        return ClaimConversationModel(
            id=self.id,
            conversation_id=self.conversation_id,
            claim_id=self.claim_id,
            start_time=self.start_time,
            end_time=self.end_time,
            status=ConversationStatus(self.status),
        )
