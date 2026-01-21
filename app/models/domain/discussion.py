from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.models.database.models import DiscussionModel


@dataclass
class Discussion:
    """Domain model for discussions."""

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime

    analysis_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    description: Optional[str] = None

    @classmethod
    def from_model(cls, model: "DiscussionModel") -> "Discussion":
        """Create domain model from database model."""
        return cls(
            id=model.id,
            title=model.title,
            description=model.description,
            analysis_id=model.analysis_id,
            user_id=model.user_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def to_model(self) -> "DiscussionModel":
        """Convert to database model."""
        return DiscussionModel(
            id=self.id,
            title=self.title,
            description=self.description,
            analysis_id=self.analysis_id,
            user_id=self.user_id,
        )