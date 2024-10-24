from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.models import UserModel
from app.models.domain.user import User
from app.repositories.base import BaseRepository
from app.repositories.interfaces.user_repository import UserRepositoryInterface


class UserRepository(BaseRepository[UserModel, User], UserRepositoryInterface):
    def __init__(self, session: AsyncSession):
        super().__init__(session, UserModel)

    def _to_model(self, user: User) -> UserModel:
        return UserModel(
            id=user.id,
            auth0_id=user.auth0_id,
            email=user.email,
            username=user.username,
            is_active=user.is_active,
            last_login=user.last_login,
        )

    def _to_domain(self, model: UserModel) -> User:
        return User(
            id=model.id,
            auth0_id=model.auth0_id,
            email=model.email,
            username=model.username,
            is_active=model.is_active,
            last_login=model.last_login,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_by_auth0_id(self, auth0_id: str) -> Optional[User]:
        """Get user by Auth0 ID."""
        query = select(self._model_class).where(self._model_class.auth0_id == auth0_id)
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        query = select(self._model_class).where(self._model_class.email == email)
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None
