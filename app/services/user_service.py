from app.models.domain.user import User
from app.schemas.user_schema import UserCreate
from uuid import uuid4, UUID
from datetime import datetime


class UserService:
    def create_user(self, user_create: UserCreate) -> User:
        return User(
            id=uuid4(),
            username=user_create.username,
            email=user_create.email,
            created_at=datetime.now(),
            last_login=datetime.now(),
        )

    def get_user(self, user_id: UUID) -> User:
        # In a real implementation, this would fetch from a database
        pass
