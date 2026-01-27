import logging
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.models import PostModel
from app.models.domain.post import Post
from app.repositories.base import BaseRepository
from app.repositories.interfaces.post_repository import PostRepositoryInterface

logger = logging.getLogger(__name__)


class PostRepository(BaseRepository[PostModel, Post], PostRepositoryInterface):
    def __init__(self, session: AsyncSession):
        super().__init__(session, PostModel)

    def _to_model(self, domain: Post) -> PostModel:
        return PostModel(
            id=domain.id,
            discussion_id=domain.discussion_id,
            text=domain.text,
            user_id=domain.user_id,
            up_votes=domain.up_votes,
            down_votes=domain.down_votes,
            # Database usually handles created_at, but we map if provided
        )

    def _to_domain(self, model: PostModel) -> Post:
        return Post(
            id=model.id,
            discussion_id=model.discussion_id,
            text=model.text,
            created_at=model.created_at,
            updated_at=model.updated_at,
            user_id=model.user_id,
            up_votes=model.up_votes,
            down_votes=model.down_votes,
        )

    async def get_by_discussion_id(
        self, discussion_id: UUID, limit: int = 50, offset: int = 0
    ) -> Tuple[List[Post], int]:
        
        # Base query
        query = select(self._model_class).where(self._model_class.discussion_id == discussion_id)
        
        # Count query
        count_query = (
            select(func.count())
            .select_from(self._model_class)
            .where(self._model_class.discussion_id == discussion_id)
        )
        total = await self._session.scalar(count_query)

        # Ordering (Usually oldest first for chats/threads, or usually newest first? 
        # Standard forums usually do Oldest -> Newest. Comments sections usually do Newest -> Oldest.
        # I will default to Created At ASC (Oldest first) for reading a thread properly).
        query = query.order_by(self._model_class.created_at.asc()).limit(limit).offset(offset)

        result = await self._session.execute(query)
        posts = [self._to_domain(model) for model in result.scalars().all()]

        return posts, total

    async def get_user_posts(
        self, user_id: UUID, limit: int = 50, offset: int = 0
    ) -> Tuple[List[Post], int]:
        
        query = select(self._model_class).where(self._model_class.user_id == user_id)
        
        count_query = (
            select(func.count())
            .select_from(self._model_class)
            .where(self._model_class.user_id == user_id)
        )
        total = await self._session.scalar(count_query)

        # For user history, Newest first is standard
        query = query.order_by(self._model_class.created_at.desc()).limit(limit).offset(offset)

        result = await self._session.execute(query)
        posts = [self._to_domain(model) for model in result.scalars().all()]

        return posts, total