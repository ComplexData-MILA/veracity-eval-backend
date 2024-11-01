from datetime import datetime, UTC
from typing import List, Optional
from uuid import UUID, uuid4

from app.models.database.models import ConversationStatus
from app.models.domain.conversation import Conversation
from app.repositories.implementations.conversation_repository import ConversationRepository
from app.repositories.implementations.claim_conversation_repository import ClaimConversationRepository
from app.core.exceptions import NotFoundException, NotAuthorizedException


class ConversationService:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        claim_conversation_repository: ClaimConversationRepository,
    ):
        self._conversation_repo = conversation_repository
        self._claim_conversation_repo = claim_conversation_repository

    async def create_conversation(self, user_id: UUID) -> Conversation:
        conversation = Conversation(
            id=uuid4(),
            user_id=user_id,
            start_time=datetime.now(UTC),
            status=ConversationStatus.active,
        )
        return await self._conversation_repo.create(conversation)

    async def get_conversation(self, conversation_id: UUID, user_id: UUID) -> Conversation:
        conversation = await self._conversation_repo.get(conversation_id)
        if not conversation:
            raise NotFoundException("Conversation not found")
        if conversation.user_id != user_id:
            raise NotAuthorizedException("Not authorized to access this conversation")
        return conversation

    async def list_user_conversations(
        self, user_id: UUID, status: Optional[ConversationStatus] = None, limit: int = 50, offset: int = 0
    ) -> List[Conversation]:
        conversations = await self._conversation_repo.get_user_conversations(
            user_id=user_id, status=status.value if status else None, limit=limit, offset=offset
        )

        return conversations
