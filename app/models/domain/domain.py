from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.models.database.models import DomainModel


@dataclass
class Domain:
    """Domain model for website domains."""

    id: UUID
    domain_name: str
    credibility_score: float
    is_reliable: bool
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, model: "DomainModel") -> "Domain":
        """Create domain model from database model."""
        return cls(
            id=model.id,
            domain_name=model.domain_name,
            credibility_score=model.credibility_score,
            is_reliable=model.is_reliable,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def to_model(self) -> "DomainModel":
        """Convert to database model."""
        return DomainModel(
            id=self.id,
            domain_name=self.domain_name,
            credibility_score=self.credibility_score,
            is_reliable=self.is_reliable,
            description=self.description,
        )
