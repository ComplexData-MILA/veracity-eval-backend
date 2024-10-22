from uuid import UUID
from datetime import datetime
from typing import List, Optional
from app.models.domain.conversation import Conversation
from app.models.domain.claim_conversation import ClaimConversation
from app.schemas.conversation_schema import ConversationCreate
from app.schemas.claim_conversation_schema import ClaimConversationCreate


class ConversationService:
    def create_conversation(self, conversation_create: ConversationCreate) -> Conversation:
        return Conversation(id=UUID.uuid4(), user_id=conversation_create.user_id, start_time=datetime.now())

    def get_conversation(self, conversation_id: UUID) -> Optional[Conversation]:
        # In a real implementation, this would fetch from a database
        pass

    def add_claim_conversation(
        self, conversation_id: UUID, claim_conversation_create: ClaimConversationCreate
    ) -> ClaimConversation:
        # This would:
        # 1. Verify the conversation exists
        # 2. Create a new claim_conversation
        # 3. Link it to the conversation
        # 4. Return the new claim_conversation
        pass

    def get_claim_conversations(self, conversation_id: UUID) -> List[ClaimConversation]:
        # Get all claim conversations for a given conversation
        pass
