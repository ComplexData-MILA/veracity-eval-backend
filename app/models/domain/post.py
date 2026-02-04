from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.models.database.models import PostModel


@dataclass
class Post:
    """Domain model for discussion posts."""

    id: UUID
    discussion_id: UUID
    text: str
    created_at: datetime
    updated_at: datetime
    user_id: Optional[UUID] = None
    up_votes: Optional[int] = 0
    down_votes: Optional[int] = 0

    @classmethod
    def from_model(cls, model: "PostModel") -> "Post":
        """Create domain model from database model."""
        return cls(
            id=model.id,
            discussion_id=model.discussion_id,
            text=model.text,
            user_id=model.user_id,
            up_votes=model.up_votes,
            down_votes=model.down_votes,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def to_model(self) -> "PostModel":
        """Convert to database model."""
        return PostModel(
            id=self.id,
            discussion_id=self.discussion_id,
            text=self.text,
            user_id=self.user_id,
            up_votes=self.up_votes,
            down_votes=self.down_votes,
        )
