from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from uuid import UUID
from app.models.domain.source import Source


class SourceRepositoryInterface(ABC):
    """Interface for source repository operations."""

    @abstractmethod
    async def create(self, source: Source) -> Source:
        """Create new source."""
        pass

    @abstractmethod
    async def get(self, source_id: UUID) -> Optional[Source]:
        """Get source by ID."""
        pass

    @abstractmethod
    async def get_by_analysis(self, analysis_id: UUID, include_content: bool = False) -> List[Source]:
        """Get all sources for an analysis."""
        pass

    @abstractmethod
    async def get_by_domain(self, domain_id: UUID, limit: int = 50, offset: int = 0) -> Tuple[List[Source], int]:
        """Get sources from a specific domain."""
        pass
