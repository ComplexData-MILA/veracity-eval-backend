from datetime import datetime
from typing import Optional, Dict
from dataclasses import dataclass
from uuid import UUID

from app.models.database.conversation import ConversationModel, ConversationStatus


@dataclass
class Conversation:
    id: UUID
    user_id: UUID
    start_time: datetime
    status: str
    end_time: Optional[datetime] = None
    claim_conversations: Optional[Dict[str, UUID]] = None

    @classmethod
    def from_model(cls, model: "ConversationModel") -> "Conversation":
        return cls(
            id=model.id,
            user_id=model.user_id,
            start_time=model.start_time,
            end_time=model.end_time,
            status=model.status.value,
        )

    def to_model(self) -> "ConversationModel":
        return ConversationModel(
            id=self.id,
            user_id=self.user_id,
            start_time=self.start_time,
            end_time=self.end_time,
            status=ConversationStatus(self.status),
        )
