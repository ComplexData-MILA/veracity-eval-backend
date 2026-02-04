import logging
from datetime import datetime, UTC
from typing import List, Tuple
from uuid import UUID, uuid4

from app.models.domain.post import Post
from app.repositories.implementations.post_repository import PostRepository
from app.repositories.implementations.discussion_repository import DiscussionRepository
from app.core.exceptions import NotFoundException, NotAuthorizedException

logger = logging.getLogger(__name__)


class PostService:
    def __init__(self, post_repository: PostRepository, discussion_repository: DiscussionRepository):
        self._post_repo = post_repository
        self._discussion_repo = discussion_repository

    async def create_post(
        self,
        discussion_id: UUID,
        user_id: UUID,
        text: str,
    ) -> Post:
        """Create a new post in a discussion."""
        # Validate discussion exists
        discussion = await self._discussion_repo.get(discussion_id)
        if not discussion:
            raise NotFoundException("Discussion not found")

        now = datetime.now(UTC)

        post = Post(
            id=uuid4(),
            discussion_id=discussion_id,
            user_id=user_id,
            text=text,
            up_votes=0,
            down_votes=0,
            created_at=now,
            updated_at=now,
        )

        return await self._post_repo.create(post)

    async def get_post(self, post_id: UUID) -> Post:
        """Get a single post."""
        post = await self._post_repo.get(post_id)
        if not post:
            raise NotFoundException("Post not found")
        return post

    async def list_discussion_posts(
        self, discussion_id: UUID, limit: int = 50, offset: int = 0
    ) -> Tuple[List[Post], int]:
        """List posts for a specific discussion."""
        # Optional: verify discussion exists first if you want strict checking
        return await self._post_repo.get_by_discussion_id(discussion_id=discussion_id, limit=limit, offset=offset)

    async def list_user_posts(self, user_id: UUID, limit: int = 50, offset: int = 0) -> Tuple[List[Post], int]:
        """List posts made by a specific user."""
        return await self._post_repo.get_user_posts(user_id=user_id, limit=limit, offset=offset)

    async def update_post_text(self, post_id: UUID, user_id: UUID, new_text: str) -> Post:
        """Update the content of a post (Owner only)."""
        post = await self.get_post(post_id)

        if post.user_id != user_id:
            raise NotAuthorizedException("You are not authorized to edit this post")

        post.text = new_text
        post.updated_at = datetime.now(UTC)
        return await self._post_repo.update(post)

    async def delete_post(self, post_id: UUID, user_id: UUID) -> bool:
        """Delete a post (Owner only)."""
        post = await self.get_post(post_id)

        if post.user_id != user_id:
            raise NotAuthorizedException("You are not authorized to delete this post")

        return await self._post_repo.delete(post_id)

    async def vote_post(self, post_id: UUID, vote_type: str) -> Post:
        """
        Increment upvotes or downvotes.
        vote_type must be 'up' or 'down'.
        Note: In a production system, you should track *who* voted to prevent double voting.
        This simple implementation just increments counters.
        """
        post = await self.get_post(post_id)

        if vote_type == "up":
            post.up_votes = (post.up_votes or 0) + 1
        elif vote_type == "down":
            post.down_votes = (post.down_votes or 0) + 1
        else:
            raise ValueError("vote_type must be 'up' or 'down'")

        # We don't update 'updated_at' for votes usually, but that depends on preference
        return await self._post_repo.update(post)
