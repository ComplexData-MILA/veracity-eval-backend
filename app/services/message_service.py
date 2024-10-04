from typing import List
from uuid import UUID
from datetime import datetime
from app.models.domain.message import Message
from app.schemas.message_schema import MessageCreate


class MessageService:
    def create_message(self, message_create: MessageCreate) -> Message:
        return Message(
            id=UUID.uuid4(),
            conversation_id=message_create.conversation_id,
            sender_type=message_create.sender_type,
            content=message_create.content,
            timestamp=datetime.now(),
            claim_id=message_create.claim_id,
            analysis_id=message_create.analysis_id,
        )

    def get_message(self, message_id: UUID) -> Message:
        # In a real implementation, this would fetch from a database
        pass

    def get_messages_by_conversation(self, conversation_id: UUID) -> List[Message]:
        # In a real implementation, this would fetch from a database
        pass
