from uuid import UUID
from datetime import datetime
from app.models.domain.claim_conversation import ClaimConversation
from app.schemas.claim_conversation_schema import ClaimConversationCreate


class ClaimConversationService:
    def create_claim_conversation(self, claim_conversation_create: ClaimConversationCreate) -> ClaimConversation:
        return ClaimConversation(
            id=UUID.uuid4(),
            conversation_id=claim_conversation_create.conversation_id,
            claim_id=claim_conversation_create.claim_id,
            start_time=datetime.now(),
        )

    def get_claim_conversation(self, claim_conversation_id: UUID) -> ClaimConversation:
        # In a real implementation, this would fetch from a database
        pass

    def get_claim_conversations_by_conversation(self, conversation_id: UUID) -> list[ClaimConversation]:
        # In a real implementation, this would fetch from a database
        pass
