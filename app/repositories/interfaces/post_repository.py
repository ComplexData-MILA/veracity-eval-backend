from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from uuid import UUID

from app.models.domain.post import Post


class PostRepositoryInterface(ABC):
    """Interface for discussion post repository operations."""

    @abstractmethod
    async def create(self, post: Post) -> Post:
        """Create a new post."""
        pass

    @abstractmethod
    async def get(self, post_id: UUID) -> Optional[Post]:
        """Get post by ID."""
        pass

    @abstractmethod
    async def update(self, post: Post) -> Post:
        """Update a post."""
        pass

    @abstractmethod
    async def delete(self, post_id: UUID) -> bool:
        """Delete a post."""
        pass

    @abstractmethod
    async def get_by_discussion_id(
        self, discussion_id: UUID, limit: int = 50, offset: int = 0
    ) -> Tuple[List[Post], int]:
        """Get posts belonging to a discussion (paginated)."""
        pass

    @abstractmethod
    async def get_user_posts(self, user_id: UUID, limit: int = 50, offset: int = 0) -> Tuple[List[Post], int]:
        """Get posts created by a specific user."""
        pass
