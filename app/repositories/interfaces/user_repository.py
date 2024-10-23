from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID
from app.models.domain.user import User


class UserRepositoryInterface(ABC):
    """Interface for user repository operations."""

    @abstractmethod
    async def create(self, user: User) -> User:
        """Create new user."""
        pass

    @abstractmethod
    async def get(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        pass

    @abstractmethod
    async def get_by_auth0_id(self, auth0_id: str) -> Optional[User]:
        """Get user by Auth0 ID."""
        pass

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        pass

    @abstractmethod
    async def update(self, user: User) -> User:
        """Update user."""
        pass
