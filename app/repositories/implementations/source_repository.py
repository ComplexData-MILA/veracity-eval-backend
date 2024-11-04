from typing import Optional, List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain.source import Source
from app.repositories.base import BaseRepository
from app.models.database.models import SourceModel


class SourceRepository(BaseRepository[SourceModel, Source]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, SourceModel)

    async def get_by_url(self, url: str) -> Optional[SourceModel]:
        """Get a source by its URL."""
        query = (
            select(self._model_class)
            .where(self._model_class.url == url)
            .options(selectinload(self._model_class.domain))
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_analysis(self, analysis_id: UUID, include_domain: bool = False) -> List[SourceModel]:
        """Get sources for an analysis."""
        query = select(self._model_class).where(self._model_class.analysis_id == analysis_id)

        if include_domain:
            query = query.options(selectinload(self._model_class.domain))

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def create_with_domain(self, source: SourceModel) -> Optional[SourceModel]:
        """Create a source with its domain relationship."""
        try:
            self._session.add(source)
            await self._session.flush()
            await self._session.refresh(source, ["domain"])
            await self._session.commit()
            return source
        except Exception as e:
            await self._session.rollback()
            raise e

    async def update(self, source: SourceModel) -> SourceModel:
        """Update a source."""
        try:
            merged = await self._session.merge(source)
            await self._session.commit()
            return merged
        except Exception as e:
            await self._session.rollback()
            raise e
