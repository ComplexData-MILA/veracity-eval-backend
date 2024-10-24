from datetime import datetime, UTC
from typing import List, Optional
from uuid import UUID, uuid4

from app.models.domain.message import Message
from app.repositories.implementations.message_repository import MessageRepository
from app.repositories.implementations.conversation_repository import ConversationRepository
from app.core.exceptions import NotAuthorizedException


class MessageService:
    def __init__(self, message_repository: MessageRepository, conversation_repository: ConversationRepository):
        self._message_repo = message_repository
        self._conversation_repo = conversation_repository

    async def create_message(
        self,
        conversation_id: UUID,
        sender_type: str,
        content: str,
        user_id: UUID,
        claim_id: Optional[UUID] = None,
        analysis_id: Optional[UUID] = None,
        claim_conversation_id: Optional[UUID] = None,
    ) -> Message:
        """Create a new message."""
        # Verify conversation ownership
        conversation = await self._conversation_repo.get(conversation_id)
        if not conversation or conversation.user_id != user_id:
            raise NotAuthorizedException("Not authorized to access this conversation")

        message = Message(
            id=uuid4(),
            conversation_id=conversation_id,
            sender_type=sender_type,
            content=content,
            timestamp=datetime.now(UTC),
            claim_id=claim_id,
            analysis_id=analysis_id,
            claim_conversation_id=claim_conversation_id,
        )

        return await self._message_repo.create(message)

    async def get_conversation_messages(
        self, conversation_id: UUID, user_id: UUID, before: Optional[datetime] = None, limit: int = 50
    ) -> List[Message]:
        """Get messages for a conversation."""
        # Verify conversation ownership
        conversation = await self._conversation_repo.get(conversation_id)
        if not conversation or conversation.user_id != user_id:
            raise NotAuthorizedException("Not authorized to access this conversation")

        return await self._message_repo.get_conversation_messages(
            conversation_id=conversation_id, before=before, limit=limit
        )

    async def get_claim_conversation_messages(
        self, claim_conversation_id: UUID, user_id: UUID, before: Optional[datetime] = None, limit: int = 50
    ) -> List[Message]:
        """Get messages for a claim conversation."""
        messages = await self._message_repo.get_claim_conversation_messages(
            claim_conversation_id=claim_conversation_id, before=before, limit=limit
        )

        if messages:
            # Verify ownership using first message's conversation
            conversation = await self._conversation_repo.get(messages[0].conversation_id)
            if not conversation or conversation.user_id != user_id:
                raise NotAuthorizedException("Not authorized to access these messages")

        return messages
