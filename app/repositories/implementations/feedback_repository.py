from typing import List
from uuid import UUID
from sqlalchemy import select

from app.models.domain.feedback import Feedback
from app.models.database.models import FeedbackModel
from app.repositories.base import BaseRepository


class FeedbackRepository(BaseRepository[FeedbackModel, Feedback]):
    def __init__(self, session):
        super().__init__(session, FeedbackModel)

    def _to_model(self, feedback: Feedback) -> FeedbackModel:
        return FeedbackModel(
            id=feedback.id,
            analysis_id=feedback.analysis_id,
            user_id=feedback.user_id,
            rating=feedback.rating,
            comment=feedback.comment,
            created_at=feedback.created_at,
        )

    def _to_domain(self, model: FeedbackModel) -> Feedback:
        return Feedback(
            id=model.id,
            analysis_id=model.analysis_id,
            user_id=model.user_id,
            rating=model.rating,
            comment=model.comment,
            created_at=model.created_at,
        )

    async def get_by_analysis(self, analysis_id: UUID) -> List[Feedback]:
        query = select(self._model_class).where(self._model_class.analysis_id == analysis_id)
        result = await self._session.execute(query)
        return [self._to_domain(obj) for obj in result.scalars().all()]

    async def get_by_user(self, user_id: UUID) -> List[Feedback]:
        query = select(self._model_class).where(self._model_class.user_id == user_id)
        result = await self._session.execute(query)
        return [self._to_domain(obj) for obj in result.scalars().all()]
