from typing import Optional, List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain.search import Search
from app.repositories.base import BaseRepository
from app.models.database.models import SearchModel


class SearchRepository(BaseRepository[SearchModel, Search]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, SearchModel)

    def _to_model(self, search: Search) -> SearchModel:
        return SearchModel(
            id=search.id,
            analysis_id=search.analysis_id,
            prompt=search.prompt,
            summary=search.summary
    )

    def _to_domain(self, model: SearchModel) -> Search:
        return Search(
            id=model.id,
            analysis_id=model.analysis_id,
            prompt=model.prompt,
            summary=model.summary,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
    async def get_by_analysis(self, analysis_id: UUID) -> List[SearchModel]:
        query = select(self._model_class).where(self._model_class.analysis_id == analysis_id)

        result = await self._session.execute(query)
        sources = list(result.scalars().all())

        if not sources:
            return []

        return sources

    async def update(self, source: SearchModel) -> SearchModel:
        """Update a source."""
        try:
            merged = await self._session.merge(source)
            await self._session.commit()
            return merged
        except Exception as e:
            await self._session.rollback()
            raise e
