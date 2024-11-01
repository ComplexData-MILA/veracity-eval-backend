from typing import Optional, List
from uuid import UUID
from datetime import UTC, datetime
from sqlalchemy import select, and_, desc

from app.models.database.models import ConversationModel, ConversationStatus
from app.models.domain.conversation import Conversation
from app.repositories.base import BaseRepository
from app.repositories.interfaces.conversation_repository import (
    ConversationRepositoryInterface,
)


class ConversationRepository(BaseRepository[ConversationModel, Conversation], ConversationRepositoryInterface):
    def __init__(self, session):
        super().__init__(session, ConversationModel)

    def _to_model(self, conversation: Conversation) -> ConversationModel:
        return ConversationModel(
            id=conversation.id,
            user_id=conversation.user_id,
            start_time=conversation.start_time,
            end_time=conversation.end_time,
            status=conversation.status,
        )

    def _to_domain(self, model: ConversationModel) -> Conversation:
        return Conversation(
            id=model.id,
            user_id=model.user_id,
            start_time=model.start_time,
            end_time=model.end_time,
            status=model.status,
        )

    async def get_user_conversations(
        self, user_id: UUID, status: Optional[ConversationStatus] = None
    ) -> List[Conversation]:
        query = (
            select(self._model_class)
            .where(self._model_class.user_id == user_id)
            .order_by(desc(self._model_class.start_time))
        )

        if status:
            query = query.where(self._model_class.status == status)

        result = await self._session.execute(query)
        return [self._to_domain(model) for model in result.scalars().all()]

    async def update_status(self, conversation_id: UUID, status: ConversationStatus) -> Optional[Conversation]:
        conversation = await self.get(conversation_id)
        if conversation:
            conversation.status = status
            if status == ConversationStatus.completed:
                conversation.end_time = datetime.now(UTC)
            return await self.update(conversation)
        return None

    async def get_active_conversation(self, user_id: UUID) -> Optional[Conversation]:
        query = select(self._model_class).where(
            and_(self._model_class.user_id == user_id, self._model_class.status == ConversationStatus.active)
        )
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def end_conversation(self, conversation_id: UUID) -> Optional[Conversation]:
        return await self.update_status(conversation_id, ConversationStatus.completed)
