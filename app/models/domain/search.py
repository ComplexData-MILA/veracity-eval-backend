from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.models.database.models import SearchModel


@dataclass
class Search:
    """Domain model for web searches."""

    id: UUID
    analysis_id: UUID
    prompt: str
    summary: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, model: "SearchModel") -> "Search":
        """Create domain model from database model."""
        return cls(
            id=model.id,
            analysis_id=model.analysis_id,
            prompt=model.prompt,
            summary=model.summary,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def to_model(self) -> "SearchModel":
        """Convert to database model."""
        return SearchModel(
            id=self.id,
            analysis_id=self.analysis_id,
            prompt=self.prompt,
            summary=self.summary,
        )
