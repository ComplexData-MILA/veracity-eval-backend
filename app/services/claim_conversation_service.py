from typing import List, Tuple
from uuid import UUID, uuid4
from datetime import UTC, datetime
from app.core.exceptions import NotAuthorizedException, NotFoundException
from app.models.database.models import ConversationStatus
from app.models.domain.claim_conversation import ClaimConversation
from app.models.domain.conversation import Conversation
from app.repositories.implementations.claim_conversation_repository import ClaimConversationRepository
from app.services.conversation_service import ConversationService


class ClaimConversationService:
    def __init__(
        self,
        conversation_service: ConversationService,
        claim_conversation_repository: ClaimConversationRepository,
    ):
        self._conversation_service = conversation_service
        self._claim_conversation_repo = claim_conversation_repository

    async def create_claim_conversation(
        self, conversation_id: UUID, user_id: UUID, claim_id: UUID
    ) -> Tuple[ClaimConversation, Conversation]:
        conversation = await self._conversation_service.get_conversation(conversation_id, user_id)

        claim_conversation = ClaimConversation(
            id=uuid4(),
            conversation_id=conversation_id,
            claim_id=claim_id,
            start_time=datetime.now(UTC),
            status=ConversationStatus.active,
        )

        created_claim_conv = await self._claim_conversation_repo.create(claim_conversation)

        return created_claim_conv, conversation

    async def get_claim_conversation(
        self, claim_conversation_id: UUID, user_id: UUID
    ) -> Tuple[ClaimConversation, Conversation]:
        claim_conv = await self._claim_conversation_repo.get(claim_conversation_id)
        if not claim_conv:
            raise NotFoundException("Claim conversation not found")

        conversation = await self._conversation_repo.get(claim_conv.conversation_id)
        if conversation.user_id != user_id:
            raise NotAuthorizedException("Not authorized to access this claim conversation")

        return claim_conv, conversation

    async def list_conversation_claims(self, conversation_id: UUID, user_id: UUID) -> List[ClaimConversation]:
        await self.get_conversation(conversation_id, user_id)
        return await self._claim_conversation_repo.get_by_conversation(conversation_id)
