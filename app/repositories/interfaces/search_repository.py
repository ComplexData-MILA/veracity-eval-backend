from abc import ABC, abstractmethod
from typing import Optional, List
from uuid import UUID
from app.models.domain.search import Search


class SearchRepositoryInterface(ABC):
    """Interface for source repository operations."""

    @abstractmethod
    async def create(self, search: Search) -> Search:
        """Create new search."""
        pass

    @abstractmethod
    async def get(self, search_id: UUID) -> Optional[Search]:
        """Get search by ID."""
        pass

    @abstractmethod
    async def get_by_analysis(self, analysis_id: UUID) -> List[Search]:
        """Get all searches for an analysis."""
        pass
