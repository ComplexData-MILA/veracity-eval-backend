import logging
from datetime import datetime, UTC
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from app.models.domain.discussion import Discussion
from app.repositories.implementations.discussion_repository import DiscussionRepository
from app.core.exceptions import NotFoundException, NotAuthorizedException

logger = logging.getLogger(__name__)


class DiscussionService:
    def __init__(self, discussion_repository: DiscussionRepository):
        self._discussion_repo = discussion_repository

    async def create_discussion(
        self,
        title: str,
        user_id: UUID,
        analysis_id: Optional[UUID] = None,
        description: Optional[str] = None,
    ) -> Discussion:
        """Create a new discussion."""
        now = datetime.now(UTC)

        # Optional: You could check if a discussion already exists for this analysis_id
        # if analysis_id:
        #     existing = await self._discussion_repo.get_by_analysis_id(analysis_id)
        #     if existing:
        #         return existing

        discussion = Discussion(
            id=uuid4(),
            title=title,
            description=description,
            analysis_id=analysis_id,
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )

        return await self._discussion_repo.create(discussion)

    async def get_discussion(self, discussion_id: UUID) -> Discussion:
        """Get a discussion by ID."""
        discussion = await self._discussion_repo.get(discussion_id)
        if not discussion:
            raise NotFoundException("Discussion not found")
        return discussion

    async def get_discussion_by_analysis(self, analysis_id: UUID) -> Discussion:
        """Get the discussion associated with a specific analysis."""
        discussion = await self._discussion_repo.get_by_analysis_id(analysis_id)
        if not discussion:
            raise NotFoundException("Discussion for this analysis not found")
        return discussion

    async def list_recent_discussions(self, limit: int = 20, offset: int = 0) -> Tuple[List[Discussion], int]:
        """List all discussions ordered by recency."""
        return await self._discussion_repo.get_recent_discussions(limit=limit, offset=offset)

    async def list_user_discussions(
        self, user_id: UUID, limit: int = 20, offset: int = 0
    ) -> Tuple[List[Discussion], int]:
        """List discussions created by a specific user."""
        return await self._discussion_repo.get_user_discussions(user_id=user_id, limit=limit, offset=offset)

    async def delete_discussion(self, discussion_id: UUID, user_id: UUID) -> bool:
        """Delete a discussion (Owner only)."""
        discussion = await self.get_discussion(discussion_id)

        if discussion.user_id != user_id:
            raise NotAuthorizedException("You are not authorized to delete this discussion")

        return await self._discussion_repo.delete(discussion_id)

    async def update_discussion(
        self, discussion_id: UUID, user_id: UUID, title: Optional[str] = None, description: Optional[str] = None
    ) -> Discussion:
        """Update discussion details (Owner only)."""
        discussion = await self.get_discussion(discussion_id)

        if discussion.user_id != user_id:
            raise NotAuthorizedException("You are not authorized to edit this discussion")

        if title:
            discussion.title = title
        if description is not None:
            discussion.description = description

        discussion.updated_at = datetime.now(UTC)

        return await self._discussion_repo.update(discussion)
