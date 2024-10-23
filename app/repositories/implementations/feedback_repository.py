from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.database.feedback import FeedbackModel
from app.models.domain.feedback import Feedback
from app.repositories.base import BaseRepository
from app.repositories.interfaces.feedback_repository import FeedbackRepositoryInterface
from app.core.exceptions import DuplicateFeedbackError


class FeedbackRepository(BaseRepository[FeedbackModel, Feedback], FeedbackRepositoryInterface):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FeedbackModel)

    def _to_model(self, feedback: Feedback) -> FeedbackModel:
        return FeedbackModel(
            id=feedback.id,
            analysis_id=feedback.analysis_id,
            user_id=feedback.user_id,
            rating=feedback.rating,
            comment=feedback.comment,
        )

    def _to_domain(self, model: FeedbackModel) -> Feedback:
        return Feedback(
            id=model.id,
            analysis_id=model.analysis_id,
            user_id=model.user_id,
            rating=model.rating,
            comment=model.comment,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def create(self, feedback: Feedback) -> Feedback:
        """Create new feedback with duplicate check."""
        try:
            return await super().create(feedback)
        except IntegrityError as e:
            if "idx_unique_user_analysis" in str(e):
                raise DuplicateFeedbackError("User has already provided feedback for this analysis")
            raise

    async def get_by_analysis(self, analysis_id: UUID, limit: int = 50, offset: int = 0) -> Tuple[List[Feedback], int]:
        """Get feedback for an analysis with pagination."""
        # Get total count
        count_query = (
            select(func.count()).select_from(self._model_class).where(self._model_class.analysis_id == analysis_id)
        )
        total = await self._session.scalar(count_query)

        # Get paginated results
        query = (
            select(self._model_class)
            .where(self._model_class.analysis_id == analysis_id)
            .order_by(self._model_class.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self._session.execute(query)
        feedback_list = [self._to_domain(model) for model in result.scalars().all()]

        return feedback_list, total

    async def get_by_user(self, user_id: UUID, limit: int = 50, offset: int = 0) -> Tuple[List[Feedback], int]:
        """Get feedback from a user with pagination."""
        # Get total count
        count_query = select(func.count()).select_from(self._model_class).where(self._model_class.user_id == user_id)
        total = await self._session.scalar(count_query)

        # Get paginated results
        query = (
            select(self._model_class)
            .where(self._model_class.user_id == user_id)
            .order_by(self._model_class.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self._session.execute(query)
        feedback_list = [self._to_domain(model) for model in result.scalars().all()]

        return feedback_list, total

    async def get_user_analysis_feedback(self, user_id: UUID, analysis_id: UUID) -> Optional[Feedback]:
        """Get a user's feedback for a specific analysis."""
        query = select(self._model_class).where(
            and_(self._model_class.user_id == user_id, self._model_class.analysis_id == analysis_id)
        )

        result = await self._session.execute(query)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None
