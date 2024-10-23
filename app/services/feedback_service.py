from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from app.models.domain.feedback import Feedback
from app.repositories.implementations.feedback_repository import FeedbackRepository
from app.repositories.implementations.analysis_repository import AnalysisRepository
from app.core.exceptions import NotFoundException, NotAuthorizedException, DuplicateFeedbackError


class FeedbackService:
    def __init__(self, feedback_repository: FeedbackRepository, analysis_repository: AnalysisRepository):
        self._feedback_repo = feedback_repository
        self._analysis_repo = analysis_repository

    async def create_feedback(
        self,
        user_id: UUID,
        analysis_id: UUID,
        rating: float,
        comment: Optional[str] = None,
    ) -> Feedback:
        """Create new feedback for an analysis."""
        # Verify analysis exists
        analysis = await self._analysis_repo.get(analysis_id)
        if not analysis:
            raise NotFoundException("Analysis not found")

        # Create feedback
        feedback = Feedback(
            id=uuid4(),
            analysis_id=analysis_id,
            user_id=user_id,
            rating=rating,
            comment=comment,
        )

        try:
            return await self._feedback_repo.create(feedback)
        except DuplicateFeedbackError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    async def get_analysis_feedback(
        self, analysis_id: UUID, limit: int = 50, offset: int = 0
    ) -> Tuple[List[Feedback], int]:
        """Get all feedback for an analysis."""
        return await self._feedback_repo.get_by_analysis(analysis_id=analysis_id, limit=limit, offset=offset)

    async def get_user_feedback(self, user_id: UUID, limit: int = 50, offset: int = 0) -> Tuple[List[Feedback], int]:
        """Get all feedback from a user."""
        return await self._feedback_repo.get_by_user(user_id=user_id, limit=limit, offset=offset)

    async def update_feedback(
        self,
        feedback_id: UUID,
        user_id: UUID,
        rating: Optional[float] = None,
        comment: Optional[str] = None,
    ) -> Feedback:
        """Update existing feedback."""
        feedback = await self._feedback_repo.get(feedback_id)
        if not feedback:
            raise NotFoundException("Feedback not found")

        if feedback.user_id != user_id:
            raise NotAuthorizedException("Not authorized to update this feedback")

        if rating is not None:
            feedback.rating = rating
        if comment is not None:
            feedback.comment = comment

        return await self._feedback_repo.update(feedback)
