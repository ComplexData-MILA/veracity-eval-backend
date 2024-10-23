from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from uuid import UUID
from app.models.domain.feedback import Feedback


class FeedbackRepositoryInterface(ABC):
    """Interface for feedback repository operations."""

    @abstractmethod
    async def create(self, feedback: Feedback) -> Feedback:
        """Create new feedback."""
        pass

    @abstractmethod
    async def get(self, feedback_id: UUID) -> Optional[Feedback]:
        """Get feedback by ID."""
        pass

    @abstractmethod
    async def update(self, feedback: Feedback) -> Feedback:
        """Update feedback."""
        pass

    @abstractmethod
    async def delete(self, feedback_id: UUID) -> bool:
        """Delete feedback."""
        pass

    @abstractmethod
    async def get_by_analysis(self, analysis_id: UUID, limit: int = 50, offset: int = 0) -> Tuple[List[Feedback], int]:
        """Get feedback for an analysis with pagination."""
        pass

    @abstractmethod
    async def get_by_user(self, user_id: UUID, limit: int = 50, offset: int = 0) -> Tuple[List[Feedback], int]:
        """Get feedback from a user with pagination."""
        pass

    @abstractmethod
    async def get_user_analysis_feedback(self, user_id: UUID, analysis_id: UUID) -> Optional[Feedback]:
        """Get a user's feedback for a specific analysis."""
        pass
