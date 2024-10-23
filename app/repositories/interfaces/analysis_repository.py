from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from uuid import UUID
from app.models.database.analysis import AnalysisStatus
from app.models.domain.analysis import Analysis


class AnalysisRepositoryInterface(ABC):
    """Interface for analysis repository operations."""

    @abstractmethod
    async def create(self, analysis: Analysis) -> Analysis:
        """Create new analysis."""
        pass

    @abstractmethod
    async def get(self, analysis_id: UUID) -> Optional[Analysis]:
        """Get analysis by ID."""
        pass

    @abstractmethod
    async def get_by_claim(
        self, claim_id: UUID, include_sources: bool = False, include_feedback: bool = False
    ) -> List[Analysis]:
        """Get all analyses for a claim."""
        pass

    @abstractmethod
    async def update_status(self, analysis_id: UUID, status: AnalysisStatus) -> Optional[Analysis]:
        """Update analysis status."""
        pass

    @abstractmethod
    async def get_recent_analyses(self, limit: int = 50, offset: int = 0) -> Tuple[List[Analysis], int]:
        """Get recent analyses with pagination."""
        pass
