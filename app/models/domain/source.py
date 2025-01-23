from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.models.database.models import SourceModel


@dataclass
class Source:
    """Domain model for web sources."""

    id: UUID
    search_id: UUID
    url: str
    title: str
    snippet: str
    domain_id: Optional[UUID]
    content: Optional[str]
    credibility_score: float
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, model: "SourceModel") -> "Source":
        """Create domain model from database model."""
        return cls(
            id=model.id,
            search_id=model.search_id,
            url=model.url,
            title=model.title,
            snippet=model.snippet,
            domain_id=model.domain_id,
            content=model.content,
            credibility_score=model.credibility_score,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def to_model(self) -> "SourceModel":
        """Convert to database model."""
        return SourceModel(
            id=self.id,
            search_id=self.search_id,
            url=self.url,
            title=self.title,
            snippet=self.snippet,
            domain_id=self.domain_id,
            content=self.content,
            credibility_score=self.credibility_score,
        )
