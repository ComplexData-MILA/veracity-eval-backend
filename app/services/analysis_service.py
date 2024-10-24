from datetime import datetime, UTC
from typing import List, Tuple
from uuid import UUID, uuid4

from app.models.database.models import AnalysisStatus
from app.models.domain.analysis import Analysis
from app.repositories.implementations.analysis_repository import AnalysisRepository
from app.repositories.implementations.claim_repository import ClaimRepository
from app.core.exceptions import NotFoundException


class AnalysisService:
    def __init__(self, analysis_repository: AnalysisRepository, claim_repository: ClaimRepository):
        self._analysis_repo = analysis_repository
        self._claim_repo = claim_repository

    async def create_analysis(
        self,
        claim_id: UUID,
        veracity_score: float,
        confidence_score: float,
        analysis_text: str,
    ) -> Analysis:
        """Create new analysis for a claim."""
        # Verify claim exists
        claim = await self._claim_repo.get(claim_id)
        if not claim:
            raise NotFoundException("Claim not found")

        analysis = Analysis(
            id=uuid4(),
            claim_id=claim_id,
            veracity_score=veracity_score,
            confidence_score=confidence_score,
            analysis_text=analysis_text,
            status=AnalysisStatus.PENDING.value,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        return await self._analysis_repo.create(analysis)

    async def get_analysis(self, analysis_id: UUID) -> Analysis:
        """Get analysis by ID."""
        analysis = await self._analysis_repo.get(analysis_id)
        if not analysis:
            raise NotFoundException("Analysis not found")
        return analysis

    async def get_claim_analyses(
        self, claim_id: UUID, include_sources: bool = False, include_feedback: bool = False
    ) -> List[Analysis]:
        """Get all analyses for a claim."""
        return await self._analysis_repo.get_by_claim(
            claim_id=claim_id, include_sources=include_sources, include_feedback=include_feedback
        )

    async def update_analysis_status(self, analysis_id: UUID, status: AnalysisStatus) -> Analysis:
        """Update analysis status."""
        analysis = await self._analysis_repo.update_status(analysis_id=analysis_id, status=status)
        if not analysis:
            raise NotFoundException("Analysis not found")
        return analysis

    async def get_recent_analyses(self, limit: int = 50, offset: int = 0) -> Tuple[List[Analysis], int]:
        """Get recent analyses with pagination."""
        return await self._analysis_repo.get_recent_analyses(limit=limit, offset=offset)
