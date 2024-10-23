from typing import List
from uuid import UUID
from sqlalchemy import select

from app.models.domain.source import Source
from app.models.database.models import SourceModel
from app.repositories.base import BaseRepository


class SourceRepository(BaseRepository[SourceModel, Source]):
    def __init__(self, session):
        super().__init__(session, SourceModel)

    def _to_model(self, source: Source) -> SourceModel:
        return SourceModel(
            id=source.id,
            analysis_id=source.analysis_id,
            url=source.url,
            title=source.title,
            snippet=source.snippet,
            credibility_score=source.credibility_score,
        )

    def _to_domain(self, model: SourceModel) -> Source:
        return Source(
            id=model.id,
            analysis_id=model.analysis_id,
            url=model.url,
            title=model.title,
            snippet=model.snippet,
            credibility_score=model.credibility_score,
        )

    async def get_by_analysis(self, analysis_id: UUID) -> List[Source]:
        query = select(self._model_class).where(self._model_class.analysis_id == analysis_id)
        result = await self._session.execute(query)
        return [self._to_domain(obj) for obj in result.scalars().all()]
