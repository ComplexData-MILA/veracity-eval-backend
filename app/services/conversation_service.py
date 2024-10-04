from uuid import UUID
from datetime import datetime
from app.models.domain.conversation import Conversation
from app.schemas.conversation_schema import ConversationCreate


class ConversationService:
    def create_conversation(self, conversation_create: ConversationCreate) -> Conversation:
        return Conversation(id=UUID.uuid4(), user_id=conversation_create.user_id, start_time=datetime.now())

    def get_conversation(self, conversation_id: UUID) -> Conversation:
        # In a real implementation, this would fetch from a database
        pass
