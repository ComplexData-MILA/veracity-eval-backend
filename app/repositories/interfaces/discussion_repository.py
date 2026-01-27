from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from uuid import UUID

from app.models.domain.discussion import Discussion


class DiscussionRepositoryInterface(ABC):
    """Interface for discussion repository operations."""

    @abstractmethod
    async def create(self, discussion: Discussion) -> Discussion:
        """Create a new discussion."""
        pass

    @abstractmethod
    async def get(self, discussion_id: UUID) -> Optional[Discussion]:
        """Get discussion by ID."""
        pass

    @abstractmethod
    async def update(self, discussion: Discussion) -> Discussion:
        """Update a discussion."""
        pass

    @abstractmethod
    async def delete(self, discussion_id: UUID) -> bool:
        """Delete a discussion."""
        pass

    @abstractmethod
    async def get_by_analysis_id(self, analysis_id: UUID) -> Optional[Discussion]:
        """Get a discussion associated with a specific analysis."""
        pass

    @abstractmethod
    async def get_user_discussions(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> Tuple[List[Discussion], int]:
        """Get discussions started by a user with pagination."""
        pass
        
    @abstractmethod
    async def get_recent_discussions(
        self, limit: int = 20, offset: int = 0
    ) -> Tuple[List[Discussion], int]:
        """Get a list of all discussions, ordered by recency."""
        pass