from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, and_

from app.models.domain.claim_conversation import ClaimConversation
from app.models.database.models import ClaimConversationModel
from app.repositories.base import BaseRepository


class ClaimConversationRepository(BaseRepository[ClaimConversationModel, ClaimConversation]):
    def __init__(self, session):
        super().__init__(session, ClaimConversationModel)

    def _to_model(self, claim_conv: ClaimConversation) -> ClaimConversationModel:
        return ClaimConversationModel(
            id=claim_conv.id,
            conversation_id=claim_conv.conversation_id,
            claim_id=claim_conv.claim_id,
            start_time=claim_conv.start_time,
            end_time=claim_conv.end_time,
            status=claim_conv.status,
        )

    def _to_domain(self, model: ClaimConversationModel) -> ClaimConversation:
        return ClaimConversation(
            id=model.id,
            conversation_id=model.conversation_id,
            claim_id=model.claim_id,
            start_time=model.start_time,
            end_time=model.end_time,
            status=model.status,
        )

    async def get_by_conversation(self, conversation_id: UUID) -> List[ClaimConversation]:
        query = select(self._model_class).where(self._model_class.conversation_id == conversation_id)
        result = await self._session.execute(query)
        return [self._to_domain(obj) for obj in result.scalars().all()]

    async def get_active_by_claim(self, claim_id: UUID) -> Optional[ClaimConversation]:
        query = select(self._model_class).where(
            and_(self._model_class.claim_id == claim_id, self._model_class.status == "active")
        )
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None
