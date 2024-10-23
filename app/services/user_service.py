from typing import Optional
from uuid import UUID
from datetime import UTC, datetime

from app.models.domain.user import User
from app.repositories.implementations.user_repository import UserRepository
from app.schemas.user_schema import UserCreate, UserUpdate


class UserService:
    def __init__(self, user_repository: UserRepository):
        self._user_repo = user_repository

    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user."""
        user = User(
            id=UUID.uuid4(),
            username=user_data.username,
            email=user_data.email,
            auth0_id=user_data.auth0_id,
            created_at=datetime.now(UTC),
            is_active=True,
        )
        return await self._user_repo.create(user)

    async def get_user(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        return await self._user_repo.get(user_id)

    async def get_by_auth0_id(self, auth0_id: str) -> Optional[User]:
        """Get user by Auth0 ID."""
        return await self._user_repo.get_by_auth0_id(auth0_id)

    async def update_user(self, user_id: UUID, user_data: UserUpdate) -> Optional[User]:
        """Update user information."""
        user = await self._user_repo.get(user_id)
        if not user:
            return None

        for field, value in user_data.dict(exclude_unset=True).items():
            setattr(user, field, value)

        return await self._user_repo.update(user)

    async def record_login(self, user_id: UUID) -> Optional[User]:
        """Record user login."""
        return await self._user_repo.update_last_login(user_id)
