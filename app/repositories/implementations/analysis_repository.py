from typing import List
from uuid import UUID

from sqlalchemy import select
from app.models.domain.analysis import Analysis
from app.models.database.models import AnalysisModel
from app.repositories.base import BaseRepository


class AnalysisRepository(BaseRepository[AnalysisModel, Analysis]):
    def __init__(self, session):
        super().__init__(session, AnalysisModel)

    def _to_model(self, analysis: Analysis) -> AnalysisModel:
        return AnalysisModel(
            id=analysis.id,
            claim_id=analysis.claim_id,
            veracity_score=analysis.veracity_score,
            confidence_score=analysis.confidence_score,
            analysis_text=analysis.analysis_text,
            created_at=analysis.created_at,
        )

    def _to_domain(self, model: AnalysisModel) -> Analysis:
        return Analysis(
            id=model.id,
            claim_id=model.claim_id,
            veracity_score=model.veracity_score,
            confidence_score=model.confidence_score,
            analysis_text=model.analysis_text,
            created_at=model.created_at,
        )

    async def get_by_claim_id(self, claim_id: UUID) -> List[Analysis]:
        query = select(self._model_class).where(self._model_class.claim_id == claim_id)
        result = await self._session.execute(query)
        return [self._to_domain(obj) for obj in result.scalars().all()]
