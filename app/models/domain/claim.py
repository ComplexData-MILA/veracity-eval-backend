from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.models.database.models import ClaimModel, ClaimStatus


@dataclass
class Claim:
    """Domain model for claims."""

    id: UUID
    user_id: UUID
    claim_text: str
    context: str
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, model: "ClaimModel") -> "Claim":
        """Create domain model from database model."""
        return cls(
            id=model.id,
            user_id=model.user_id,
            claim_text=model.claim_text,
            context=model.context,
            status=ClaimStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def to_model(self) -> "ClaimModel":
        """Convert to database model."""
        return ClaimModel(
            id=self.id,
            user_id=self.user_id,
            claim_text=self.claim_text,
            context=self.context,
            status=ClaimStatus(self.status).value,
        )
