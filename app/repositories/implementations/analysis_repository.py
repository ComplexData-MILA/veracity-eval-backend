from typing import Optional, List
from uuid import UUID
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database.models import AnalysisModel, AnalysisStatus
from app.models.domain.analysis import Analysis
from app.models.domain.feedback import Feedback
from app.models.domain.source import Source
from app.repositories.base import BaseRepository


class AnalysisRepository(BaseRepository[AnalysisModel, Analysis]):
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
        """Convert database model to domain model without loading relationships."""
        return Analysis(
            id=model.id,
            claim_id=model.claim_id,
            veracity_score=model.veracity_score,
            confidence_score=model.confidence_score,
            analysis_text=model.analysis_text,
            status=model.status.value,
            created_at=model.created_at,
            updated_at=model.updated_at,
            sources=None,  # Don't load relationships here
            feedback=None,
        )

    async def create(self, analysis: Analysis) -> Analysis:
        """Create new analysis."""
        model = self._to_model(analysis)
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)

        # Detach the model from the session to prevent lazy loading
        self._session.expunge(model)

        return self._to_domain(model)

    async def get_with_relations(self, analysis_id: UUID) -> Optional[Analysis]:
        """Get analysis with related sources and feedback."""
        query = (
            select(self._model_class)
            .where(self._model_class.id == analysis_id)
            .options(
                selectinload(self._model_class.sources),
                selectinload(self._model_class.feedbacks),
            )
        )

        result = await self._session.execute(query)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Ensure relationships are loaded
        self._session.expunge(model)

        return model

    async def get_by_claim(
        self, claim_id: UUID, include_sources: bool = False, include_feedback: bool = False
    ) -> List[Analysis]:
        """Get all analyses for a claim."""
        query = select(self._model_class).where(self._model_class.claim_id == claim_id)

        if include_sources or include_feedback:
            if include_sources:
                query = query.options(selectinload(self._model_class.sources))
            if include_feedback:
                query = query.options(selectinload(self._model_class.feedback))

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
                    sources=(
                        [Source.from_model(s) for s in model.sources] if include_sources and model.sources else None
                    ),
                    feedback=(
                        [Feedback.from_model(f) for f in model.feedback]
                        if include_feedback and model.feedback
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

        # Detach the model to prevent lazy loading
        self._session.expunge(model)

        return self._to_domain(model)

    async def get_latest_by_claim(
        self, claim_id: UUID, include_sources: bool = False, include_feedback: bool = False
    ) -> Optional[Analysis]:
        """Get the most recent analysis for a claim."""
        query = (
            select(self._model_class)
            .where(self._model_class.claim_id == claim_id)
            .order_by(desc(self._model_class.created_at))
            .limit(1)
        )

        if include_sources:
            query = query.options(selectinload(self._model_class.sources))
        if include_feedback:
            query = query.options(selectinload(self._model_class.feedback))

        result = await self._session.execute(query)
        model = result.scalar_one_or_none()

        if not model:
            return None

        # Detach to prevent lazy loading
        self._session.expunge(model)

        if include_sources or include_feedback:
            return Analysis(
                id=model.id,
                claim_id=model.claim_id,
                veracity_score=model.veracity_score,
                confidence_score=model.confidence_score,
                analysis_text=model.analysis_text,
                status=model.status.value,
                created_at=model.created_at,
                updated_at=model.updated_at,
                sources=[Source.from_model(s) for s in model.sources] if include_sources and model.sources else None,
                feedback=(
                    [Feedback.from_model(f) for f in model.feedback] if include_feedback and model.feedback else None
                ),
            )
        else:
            return self._to_domain(model)
