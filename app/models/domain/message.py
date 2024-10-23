from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict
from uuid import UUID

from app.models.database.message import MessageModel, MessageSenderType


@dataclass
class Message:
    """Domain model for messages."""

    id: UUID
    conversation_id: UUID
    sender_type: str
    content: str
    timestamp: datetime
    claim_id: Optional[UUID] = None
    analysis_id: Optional[UUID] = None
    claim_conversation_id: Optional[UUID] = None
    metadata: Dict = None
    created_at: datetime = None
    updated_at: datetime = None

    @classmethod
    def from_model(cls, model: "MessageModel") -> "Message":
        """Create domain model from database model."""
        return cls(
            id=model.id,
            conversation_id=model.conversation_id,
            sender_type=model.sender_type.value,
            content=model.content,
            timestamp=model.timestamp,
            claim_id=model.claim_id,
            analysis_id=model.analysis_id,
            claim_conversation_id=model.claim_conversation_id,
            metadata=model.metadata or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def to_model(self) -> "MessageModel":
        """Convert to database model."""
        return MessageModel(
            id=self.id,
            conversation_id=self.conversation_id,
            sender_type=MessageSenderType(self.sender_type),
            content=self.content,
            timestamp=self.timestamp,
            claim_id=self.claim_id,
            analysis_id=self.analysis_id,
            claim_conversation_id=self.claim_conversation_id,
            metadata=self.metadata,
        )
