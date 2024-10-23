from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.models import MessageModel, MessageSenderType
from app.models.domain.message import Message
from app.repositories.base import BaseRepository
from app.repositories.interfaces.message_repository import MessageRepositoryInterface


class MessageRepository(BaseRepository[MessageModel, Message], MessageRepositoryInterface):
    def __init__(self, session: AsyncSession):
        super().__init__(session, MessageModel)

    def _to_model(self, message: Message) -> MessageModel:
        return MessageModel(
            id=message.id,
            conversation_id=message.conversation_id,
            sender_type=MessageSenderType(message.sender_type),
            content=message.content,
            timestamp=message.timestamp,
            claim_id=message.claim_id,
            analysis_id=message.analysis_id,
            claim_conversation_id=message.claim_conversation_id,
        )

    def _to_domain(self, model: MessageModel) -> Message:
        return Message(
            id=model.id,
            conversation_id=model.conversation_id,
            sender_type=model.sender_type.value,
            content=model.content,
            timestamp=model.timestamp,
            claim_id=model.claim_id,
            analysis_id=model.analysis_id,
            claim_conversation_id=model.claim_conversation_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_conversation_messages(
        self, conversation_id: UUID, before: Optional[datetime] = None, limit: int = 50
    ) -> List[Message]:
        """Get messages for a conversation with pagination."""
        query = select(self._model_class).where(self._model_class.conversation_id == conversation_id)

        if before:
            query = query.where(self._model_class.timestamp < before)

        query = query.order_by(self._model_class.timestamp.desc()).limit(limit)

        result = await self._session.execute(query)
        return [self._to_domain(model) for model in result.scalars().all()]

    async def get_claim_conversation_messages(
        self, claim_conversation_id: UUID, before: Optional[datetime] = None, limit: int = 50
    ) -> List[Message]:
        """Get messages for a claim conversation with pagination."""
        query = select(self._model_class).where(self._model_class.claim_conversation_id == claim_conversation_id)

        if before:
            query = query.where(self._model_class.timestamp < before)

        query = query.order_by(self._model_class.timestamp.desc()).limit(limit)

        result = await self._session.execute(query)
        return [self._to_domain(model) for model in result.scalars().all()]
