from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database.analysis import AnalysisModel, AnalysisStatus
from app.models.domain.analysis import Analysis
from app.models.domain.feedback import Feedback
from app.models.domain.source import Source
from app.repositories.base import BaseRepository
from app.repositories.interfaces.analysis_repository import AnalysisRepositoryInterface


class AnalysisRepository(BaseRepository[AnalysisModel, Analysis], AnalysisRepositoryInterface):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AnalysisModel)

    def _to_model(self, analysis: Analysis) -> AnalysisModel:
        return AnalysisModel(
            id=analysis.id,
            claim_id=analysis.claim_id,
            veracity_score=analysis.veracity_score,
            confidence_score=analysis.confidence_score,
            analysis_text=analysis.analysis_text,
            status=AnalysisStatus(analysis.status),
        )

    def _to_domain(self, model: AnalysisModel) -> Analysis:
        return Analysis(
            id=model.id,
            claim_id=model.claim_id,
            veracity_score=model.veracity_score,
            confidence_score=model.confidence_score,
            analysis_text=model.analysis_text,
            status=model.status.value,
            created_at=model.created_at,
            updated_at=model.updated_at,
            sources=[Source.from_model(s) for s in model.sources] if model.sources else None,
            feedback=[Feedback.from_model(f) for f in model.feedback] if model.feedback else None,
        )

    async def get_by_claim(
        self, claim_id: UUID, include_sources: bool = False, include_feedback: bool = False
    ) -> List[Analysis]:
        """Get all analyses for a claim."""
        query = select(self._model_class).where(self._model_class.claim_id == claim_id)

        if include_sources:
            query = query.options(selectinload(self._model_class.sources))
        if include_feedback:
            query = query.options(selectinload(self._model_class.feedback))

        result = await self._session.execute(query)
        return [self._to_domain(model) for model in result.scalars().all()]

    async def update_status(self, analysis_id: UUID, status: AnalysisStatus) -> Optional[Analysis]:
        """Update analysis status."""
        analysis = await self.get(analysis_id)
        if not analysis:
            return None

        analysis.status = status.value

        return await self.update(analysis)

    async def get_recent_analyses(self, limit: int = 50, offset: int = 0) -> Tuple[List[Analysis], int]:
        """Get recent analyses with pagination."""
        # Get total count
        count_query = select(func.count()).select_from(self._model_class)
        total = await self._session.scalar(count_query)

        # Get paginated results
        query = select(self._model_class).order_by(self._model_class.created_at.desc()).limit(limit).offset(offset)

        result = await self._session.execute(query)
        analyses = [self._to_domain(model) for model in result.scalars().all()]

        return analyses, total
