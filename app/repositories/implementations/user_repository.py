from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, update, and_, or_
from sqlalchemy.exc import IntegrityError

from app.models.domain.user import User
from app.models.database.models.user import UserModel
from app.repositories.base import BaseRepository
from app.repositories.interfaces.user_repository import UserRepositoryInterface
from app.core.exceptions import UserAlreadyExistsError


class UserRepository(BaseRepository[UserModel, User], UserRepositoryInterface):
    def __init__(self, session):
        super().__init__(session, UserModel)

    def _to_model(self, user: User) -> UserModel:
        return UserModel(
            id=user.id,
            username=user.username,
            email=user.email,
            auth0_id=user.auth0_id,
            created_at=user.created_at,
            last_login=user.last_login,
            is_active=user.is_active,
            preferences=user.preferences,
        )

    def _to_domain(self, model: UserModel) -> User:
        return User(
            id=model.id,
            username=model.username,
            email=model.email,
            auth0_id=model.auth0_id,
            created_at=model.created_at,
            last_login=model.last_login,
            is_active=model.is_active,
            preferences=model.preferences,
        )

    async def create(self, user: User) -> User:
        try:
            return await super().create(user)
        except IntegrityError as e:
            if "users_email_key" in str(e):
                raise UserAlreadyExistsError(f"User with email {user.email} already exists")
            if "users_username_key" in str(e):
                raise UserAlreadyExistsError(f"User with username {user.username} already exists")
            raise

    async def get_by_email(self, email: str) -> Optional[User]:
        query = select(self._model_class).where(
            and_(self._model_class.email == email, self._model_class.is_deleted is False)
        )
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_auth0_id(self, auth0_id: str) -> Optional[User]:
        query = select(self._model_class).where(
            and_(self._model_class.auth0_id == auth0_id, self._model_class.is_deleted is False)
        )
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def update_last_login(self, user_id: UUID) -> Optional[User]:
        query = (
            update(self._model_class)
            .where(self._model_class.id == user_id)
            .values(last_login=datetime.utcnow())
            .returning(self._model_class)
        )
        result = await self._session.execute(query)
        model = result.scalar_one_or_none()
        await self._session.commit()
        return self._to_domain(model) if model else None

    async def get_active_users(self) -> List[User]:
        query = select(self._model_class).where(
            and_(self._model_class.is_active is True, self._model_class.is_deleted is False)
        )
        result = await self._session.execute(query)
        return [self._to_domain(model) for model in result.scalars().all()]

    async def search_users(self, search_term: str) -> List[User]:
        """Search users by username or email."""
        query = select(self._model_class).where(
            and_(
                or_(
                    self._model_class.username.ilike(f"%{search_term}%"),
                    self._model_class.email.ilike(f"%{search_term}%"),
                ),
                self._model_class.is_deleted is False,
            )
        )
        result = await self._session.execute(query)
        return [self._to_domain(model) for model in result.scalars().all()]

    async def soft_delete(self, user_id: UUID) -> bool:
        """Soft delete a user."""
        query = (
            update(self._model_class)
            .where(self._model_class.id == user_id)
            .values(is_deleted=True, deleted_at=datetime.utcnow())
        )
        result = await self._session.execute(query)
        await self._session.commit()
        return result.rowcount > 0
