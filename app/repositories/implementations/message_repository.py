from typing import List
from uuid import UUID
from app.models.domain.message import Message
from app.models.database.models import MessageModel
from app.repositories.base import BaseRepository
from sqlalchemy import select


class MessageRepository(BaseRepository[MessageModel, Message]):
    def __init__(self, session):
        super().__init__(session, MessageModel)

    def _to_model(self, message: Message) -> MessageModel:
        return MessageModel(
            id=message.id,
            conversation_id=message.conversation_id,
            claim_conversation_id=getattr(message, "claim_conversation_id", None),
            sender_type=message.sender_type,
            content=message.content,
            timestamp=message.timestamp,
            claim_id=message.claim_id,
            analysis_id=message.analysis_id,
        )

    def _to_domain(self, model: MessageModel) -> Message:
        return Message(
            id=model.id,
            conversation_id=model.conversation_id,
            sender_type=model.sender_type,
            content=model.content,
            timestamp=model.created_at,
            claim_id=model.claim_id,
            analysis_id=model.analysis_id,
            claim_conversation_id=model.claim_conversation_id,
        )

    async def get_by_conversation(self, conversation_id: UUID) -> List[Message]:
        query = (
            select(self._model_class)
            .where(self._model_class.conversation_id == conversation_id)
            .order_by(self._model_class.created_at)
        )
        result = await self._session.execute(query)
        return [self._to_domain(obj) for obj in result.scalars().all()]

    async def get_by_claim_conversation(self, claim_conversation_id: UUID) -> List[Message]:
        query = (
            select(self._model_class)
            .where(self._model_class.claim_conversation_id == claim_conversation_id)
            .order_by(self._model_class.created_at)
        )
        result = await self._session.execute(query)
        return [self._to_domain(obj) for obj in result.scalars().all()]
