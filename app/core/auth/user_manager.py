from datetime import UTC, datetime
from typing import Tuple
from uuid import uuid4
from fastapi import HTTPException
import logging

from app.models.domain.user import User
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


class UserManager:
    def __init__(self, user_service: UserService):
        self._user_service = user_service

    async def get_or_create_user(self, auth0_payload: dict) -> Tuple[User, bool]:
        """
        Get existing user or create new one from Auth0 payload.
        Returns (user, created) tuple where created is True if new user was created.
        """
        try:
            user = await self._user_service.get_by_auth0_id(auth0_payload["sub"])
            if user:
                user = await self._user_service.record_login(user.id)
                return user, False

            email = auth0_payload.get("email")
            if email:
                user = await self._user_service.get_by_email(email)
                if user:
                    user.auth0_id = auth0_payload["sub"]
                    user.last_login = datetime.now(UTC)
                    user = await self._user_service.update(user)
                    return user, False

            username = self._generate_username(auth0_payload)
            user = User(
                id=uuid4(),
                auth0_id=auth0_payload["sub"],
                email=email or "",
                username=username,
                is_active=True,
                last_login=datetime.now(UTC),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

            created_user = await self._user_service.create_user_from_auth0(
                auth0_id=user.auth0_id,
                email=user.email,
                username=username,
            )

            return created_user, True

        except Exception as e:
            logger.error(f"Error in get_or_create_user: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error processing user data")

    def _generate_username(self, auth0_payload: dict) -> str:
        """Generate username from Auth0 payload."""
        if nickname := auth0_payload.get("nickname"):
            return nickname
        if name := auth0_payload.get("name"):
            return name.lower().replace(" ", "_")
        if email := auth0_payload.get("email"):
            return email.split("@")[0]
        return f"user_{uuid4().hex[:8]}"
