import logging
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.models import DiscussionModel
from app.models.domain.discussion import Discussion
from app.repositories.base import BaseRepository
from app.repositories.interfaces.discussion_repository import DiscussionRepositoryInterface

logger = logging.getLogger(__name__)


class DiscussionRepository(BaseRepository[DiscussionModel, Discussion], DiscussionRepositoryInterface):
    def __init__(self, session: AsyncSession):
        super().__init__(session, DiscussionModel)

    def _to_model(self, domain: Discussion) -> DiscussionModel:
        return DiscussionModel(
            id=domain.id,
            title=domain.title,
            description=domain.description,
            analysis_id=domain.analysis_id,
            user_id=domain.user_id,
            # created_at/updated_at are typically handled by DB defaults,
            # but can be passed if the domain sets them explicitly
        )

    def _to_domain(self, model: DiscussionModel) -> Discussion:
        return Discussion(
            id=model.id,
            title=model.title,
            description=model.description,
            analysis_id=model.analysis_id,
            user_id=model.user_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_analysis_id(self, analysis_id: UUID) -> Optional[Discussion]:
        stmt = select(self._model_class).where(self._model_class.analysis_id == analysis_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_user_discussions(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> Tuple[List[Discussion], int]:

        # 1. Build Query
        query = select(self._model_class).where(self._model_class.user_id == user_id)

        # 2. Get Total Count
        count_query = select(func.count()).select_from(self._model_class).where(self._model_class.user_id == user_id)
        total = await self._session.scalar(count_query)

        # 3. Apply Limit/Offset/Order
        query = query.order_by(self._model_class.created_at.desc()).limit(limit).offset(offset)

        result = await self._session.execute(query)
        discussions = [self._to_domain(model) for model in result.scalars().all()]

        return discussions, total

    async def get_recent_discussions(self, limit: int = 20, offset: int = 0) -> Tuple[List[Discussion], int]:

        query = select(self._model_class)
        count_query = select(func.count()).select_from(self._model_class)

        total = await self._session.scalar(count_query)

        query = query.order_by(self._model_class.created_at.desc()).limit(limit).offset(offset)

        result = await self._session.execute(query)
        discussions = [self._to_domain(model) for model in result.scalars().all()]

        return discussions, total
