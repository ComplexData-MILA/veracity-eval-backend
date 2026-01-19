from typing import Optional, List
from uuid import UUID
from sqlalchemy import desc, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime

from app.models.database.models import AnalysisModel, AnalysisStatus, SearchModel
from app.models.domain.analysis import Analysis
from app.models.domain.feedback import Feedback
from app.models.domain.search import Search
from app.repositories.base import BaseRepository


class AnalysisRepository(BaseRepository[AnalysisModel, Analysis]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AnalysisModel)

    def _to_model(self, analysis: Analysis) -> AnalysisModel:
        return analysis.to_model()

    def _to_domain(self, model: AnalysisModel) -> Analysis:
        """Convert database model to domain model without loading relationships."""
        return Analysis.from_model_safe(model)

    async def create(self, analysis: Analysis) -> Analysis:
        """Create new analysis."""
        model = self._to_model(analysis)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

        self._session.expunge(model)

        return self._to_domain(model)

    async def get_with_relations(self, analysis_id: UUID) -> Optional[Analysis]:
        """Get analysis with related sources and feedback."""
        query = (
            select(self._model_class)
            .where(self._model_class.id == analysis_id)
            .options(
                selectinload(self._model_class.searches).selectinload(SearchModel.sources),
                selectinload(self._model_class.feedbacks),
            )
        )

        result = await self._session.execute(query)
        model = result.scalar_one_or_none()

        if not model:
            return None

        self._session.expunge(model)

        return Analysis.from_model(model=model)

    async def get_by_claim(
        self,
        claim_id: UUID,
        include_searches: bool = False,
        include_sources: bool = False,
        include_feedback: bool = False,
    ) -> List[Analysis]:
        """Get all analyses for a claim."""
        query = select(self._model_class).where(self._model_class.claim_id == claim_id)

        if include_sources or include_searches or include_feedback:
            if include_searches:
                if include_sources:
                    query = query.options(selectinload(self._model_class.searches).selectinload(SearchModel.sources))
                else:
                    query = query.options(selectinload(self._model_class.searches))
            if include_feedback:
                query = query.options(selectinload(self._model_class.feedbacks))

            result = await self._session.execute(query)
            models = result.scalars().all()

            return [
                Analysis(
                    id=model.id,
                    claim_id=model.claim_id,
                    veracity_score=model.veracity_score,
                    confidence_score=model.confidence_score,
                    analysis_text=model.analysis_text,
                    status=model.status.value,
                    created_at=model.created_at,
                    updated_at=model.updated_at,
                    searches=(
                        [Search.from_model(s) for s in model.searches] if include_searches and model.searches else None
                    ),
                    feedback=(
                        [Feedback.from_model(f) for f in model.feedbacks]
                        if include_feedback and model.feedbacks
                        else None
                    ),
                )
                for model in models
            ]
        else:
            result = await self._session.execute(query)
            return [self._to_domain(model) for model in result.scalars().all()]

    async def update_status(self, analysis_id: UUID, status: AnalysisStatus) -> Optional[Analysis]:
        """Update analysis status."""
        query = select(self._model_class).where(self._model_class.id == analysis_id)
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()

        if not model:
            return None

        model.status = status
        await self._session.commit()
        await self._session.refresh(model)

        self._session.expunge(model)

        return self._to_domain(model)

    async def get_latest_by_claim(
        self,
        claim_id: UUID,
        include_searches: bool = False,
        include_sources: bool = False,
        include_feedback: bool = False,
    ) -> Optional[Analysis]:
        """Get the most recent analysis for a claim."""
        query = (
            select(self._model_class)
            .where(self._model_class.claim_id == claim_id)
            .order_by(desc(self._model_class.created_at))
            .limit(1)
        )

        if include_searches:
            if include_sources:
                query = query.options(selectinload(self._model_class.searches).selectinload(SearchModel.sources))
            else:
                query = query.options(selectinload(self._model_class.searches))
        if include_feedback:
            query = query.options(selectinload(self._model_class.feedbacks))

        result = await self._session.execute(query)
        model = result.scalar_one_or_none()

        if not model:
            return None

        self._session.expunge(model)

        if include_sources or include_feedback or include_searches:
            return Analysis(
                id=model.id,
                claim_id=model.claim_id,
                veracity_score=model.veracity_score,
                confidence_score=model.confidence_score,
                analysis_text=model.analysis_text,
                status=model.status.value,
                created_at=model.created_at,
                updated_at=model.updated_at,
                searches=[Search.from_model(s) for s in model.searches]
                if include_searches and model.searches
                else None,
                feedback=(
                    [Feedback.from_model(f) for f in model.feedbacks] if include_feedback and model.feedbacks else None
                ),
            )
        else:
            return self._to_domain(model)

    async def get_analysis_in_date_range(self, start_date: datetime, end_date: datetime) -> List[Analysis]:
        stmt = select(self._model_class).where(
            and_(
                self._model_class.created_at >= start_date,
                self._model_class.created_at <= end_date,
                self._model_class.status == AnalysisStatus.completed,
            )
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(model) for model in result.scalars().all()]
