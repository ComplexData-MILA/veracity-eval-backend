from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from app.models.database.user import UserModel


@dataclass
class User:
    """Domain model for users."""

    id: UUID
    auth0_id: str
    email: str
    username: str
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, model: "UserModel") -> "User":
        """Create domain model from database model."""
        return cls(
            id=model.id,
            auth0_id=model.auth0_id,
            email=model.email,
            username=model.username,
            is_active=model.is_active,
            last_login=model.last_login,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def to_model(self) -> "UserModel":
        """Convert to database model."""
        return UserModel(
            id=self.id,
            auth0_id=self.auth0_id,
            email=self.email,
            username=self.username,
            is_active=self.is_active,
            last_login=self.last_login,
        )
