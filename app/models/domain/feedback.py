from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from app.models.database.models import FeedbackModel


@dataclass
class Feedback:
    id: UUID
    analysis_id: UUID
    user_id: UUID
    rating: float
    comment: Optional[str]
    created_at: datetime = None
    updated_at: datetime = None
    labels: List[int] = None

    @classmethod
    def from_model(cls, model: "FeedbackModel") -> "Feedback":
        """Create domain model from database model."""
        return cls(
            id=model.id,
            analysis_id=model.analysis_id,
            user_id=model.user_id,
            rating=model.rating,
            comment=model.comment,
            created_at=model.created_at,
            updated_at=model.updated_at,
            labels=model.labels
        )

    def to_model(self) -> "FeedbackModel":
        """Convert to database model."""
        return FeedbackModel(
            id=self.id,
            analysis_id=self.analysis_id,
            user_id=self.user_id,
            rating=self.rating,
            comment=self.comment,
            labels=self.labels
        )
