from uuid import UUID, uuid4
from typing import Optional
from datetime import datetime, UTC

from app.models.domain.user import User
from app.repositories.implementations.user_repository import UserRepository
from app.core.exceptions import NotFoundException, DuplicateUserError


class UserService:
    def __init__(self, user_repository: UserRepository):
        self._user_repo = user_repository

    async def create_user_from_auth0(
        self,
        auth0_id: str,
        email: str,
        username: str,
    ) -> User:
        """Create a new user from Auth0 data."""
        existing = await self._user_repo.get_by_auth0_id(auth0_id)
        if existing:
            raise DuplicateUserError(f"User with Auth0 ID {auth0_id} already exists")

        user = User(
            id=uuid4(),
            auth0_id=auth0_id,
            email=email,
            username=username,
            is_active=True,
            last_login=datetime.now(UTC),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        return await self._user_repo.create(user)

    async def get_user(self, user_id: UUID) -> User:
        """Get user by ID."""
        user = await self._user_repo.get(user_id)
        if not user:
            raise NotFoundException("User not found")
        return user

    async def get_by_auth0_id(self, auth0_id: str) -> Optional[User]:
        """Get user by Auth0 ID."""
        return await self._user_repo.get_by_auth0_id(auth0_id)

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return await self._user_repo.get_by_email(email)

    async def record_login(self, user_id: UUID) -> User:
        """Record user login."""
        user = await self.get_user(user_id)
        user.last_login = datetime.now(UTC)
        return await self._user_repo.update(user)

    async def deactivate_user(self, user_id: UUID) -> User:
        """Deactivate a user account."""
        user = await self.get_user(user_id)
        user.is_active = False
        user.updated_at = datetime.now(UTC)
        return await self._user_repo.update(user)

    async def update_user(self, user: User) -> User:
        """Update user data."""
        return await self._user_repo.update(user)
