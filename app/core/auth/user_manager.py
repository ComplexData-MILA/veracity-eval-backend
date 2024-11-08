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
            logger.debug(f"Auth0 payload received: {auth0_payload}")

            user = await self._user_service.get_by_auth0_id(auth0_payload["sub"])
            if user:
                logger.debug(f"Found existing user by Auth0 ID: {user.id}")
                user = await self._user_service.record_login(user.id)
                return user, False

            email = self._extract_email(auth0_payload)
            logger.debug(f"Extracted email: {email}")

            if email:
                user = await self._user_service.get_by_email(email)
                if user:
                    logger.debug(f"Found existing user by email: {user.id}")
                    user.auth0_id = auth0_payload["sub"]
                    user.last_login = datetime.now(UTC)
                    user = await self._user_service.update(user)
                    return user, False

            username = self._generate_username(auth0_payload)
            logger.debug(f"Generated username: {username}")

            if not email:
                logger.warning(f"No email found in Auth0 payload for user {username}")
                email = f"{username}@placeholder.com"

            # Create new user
            user = User(
                id=uuid4(),
                auth0_id=auth0_payload["sub"],
                email=email,
                username=username,
                is_active=True,
                last_login=datetime.now(UTC),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

            logger.debug(f"Creating new user with email: {email} and username: {username}")
            created_user = await self._user_service.create_user_from_auth0(
                auth0_id=user.auth0_id,
                email=user.email,
                username=username,
            )

            return created_user, True

        except Exception as e:
            logger.error(f"Error in get_or_create_user: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error processing user data: {str(e)}")

    def _extract_email(self, auth0_payload: dict) -> str:
        """
        Extract email from Auth0 payload, trying different possible locations.
        """
        email_locations = [
            "email",
            "emails",
            "user_info.email",
            "user_metadata.email",
            "app_metadata.email",
        ]

        for location in email_locations:
            try:
                if "." in location:
                    # Handle nested paths
                    value = auth0_payload
                    for key in location.split("."):
                        value = value.get(key, {})
                else:
                    value = auth0_payload.get(location)

                if isinstance(value, list):
                    # If it's a list, take the first email
                    value = value[0] if value else None

                if value and isinstance(value, str) and "@" in value:
                    logger.debug(f"Found email in {location}: {value}")
                    return value
            except Exception as e:
                logger.debug(f"Error extracting email from {location}: {str(e)}")
                continue

        return ""

    def _generate_username(self, auth0_payload: dict) -> str:
        """Generate username from Auth0 payload."""
        logger.debug(f"Generating username from payload keys: {auth0_payload.keys()}")

        if nickname := auth0_payload.get("nickname"):
            logger.debug(f"Using nickname: {nickname}")
            return nickname
        if name := auth0_payload.get("name"):
            username = name.lower().replace(" ", "_")
            logger.debug(f"Using transformed name: {username}")
            return username
        if email := auth0_payload.get("email"):
            username = email.split("@")[0]
            logger.debug(f"Using email prefix: {username}")
            return username

        # Generate random username as fallback
        random_username = f"user_{uuid4().hex[:8]}"
        logger.debug(f"Using random username: {random_username}")
        return random_username
