from typing import List, Tuple
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database.models import SourceModel
from app.models.domain.source import Source
from app.repositories.base import BaseRepository
from app.repositories.interfaces.source_repository import SourceRepositoryInterface


class SourceRepository(BaseRepository[SourceModel, Source], SourceRepositoryInterface):
    def __init__(self, session: AsyncSession):
        super().__init__(session, SourceModel)

    def _to_model(self, source: Source) -> SourceModel:
        return SourceModel(
            id=source.id,
            analysis_id=source.analysis_id,
            url=source.url,
            title=source.title,
            snippet=source.snippet,
            domain_id=source.domain_id,
            content=source.content,
            credibility_score=source.credibility_score,
        )

    def _to_domain(self, model: SourceModel) -> Source:
        return Source(
            id=model.id,
            analysis_id=model.analysis_id,
            url=model.url,
            title=model.title,
            snippet=model.snippet,
            domain_id=model.domain_id,
            content=model.content,
            credibility_score=model.credibility_score,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_analysis(self, analysis_id: UUID, include_content: bool = False) -> List[Source]:
        """Get all sources for an analysis."""
        query = select(self._model_class).where(self._model_class.analysis_id == analysis_id)

        if include_content:
            query = query.options(selectinload(self._model_class.domain))

        result = await self._session.execute(query)
        return [self._to_domain(model) for model in result.scalars().all()]

    async def get_by_domain(self, domain_id: UUID, limit: int = 50, offset: int = 0) -> Tuple[List[Source], int]:
        """Get sources from a specific domain."""
        # Get total count
        count_query = (
            select(func.count()).select_from(self._model_class).where(self._model_class.domain_id == domain_id)
        )
        total = await self._session.scalar(count_query)

        # Get paginated results
        query = (
            select(self._model_class)
            .where(self._model_class.domain_id == domain_id)
            .order_by(self._model_class.created_at.desc())
            .limit(limit)
            .offset(offset)
        )

        result = await self._session.execute(query)
        sources = [self._to_domain(model) for model in result.scalars().all()]

        return sources, total
