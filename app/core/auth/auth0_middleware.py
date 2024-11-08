# app/core/auth/auth0_middleware.py
from typing import Optional
from uuid import uuid4
from fastapi import HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, ExpiredSignatureError
import aiohttp
import json
import logging
from datetime import UTC, datetime

from app.core.config import get_settings
from app.services.user_service import UserService
from app.models.domain.user import User

logger = logging.getLogger(__name__)
settings = get_settings()


class Auth0Bearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        if credentials:
            if not credentials.scheme.lower() == "bearer":
                if self.auto_error:
                    raise HTTPException(status_code=401, detail="Invalid authentication scheme. Bearer required")
            return credentials
        return None


security = Auth0Bearer()


class Auth0Middleware:
    def __init__(self, user_service: UserService):
        self.domain = settings.AUTH0_DOMAIN
        self.audience = settings.AUTH0_AUDIENCE
        self.issuer = f"https://{settings.AUTH0_DOMAIN}/"
        self.algorithms = settings.AUTH0_ALGORITHMS
        self.jwks = None
        self.user_service = user_service

    async def _get_jwks(self) -> dict:
        """Fetch and cache JWKS from Auth0"""
        if not self.jwks:
            try:
                jwks_url = f"https://{self.domain}/.well-known/jwks.json"
                logger.debug(f"Fetching JWKS from: {jwks_url}")

                async with aiohttp.ClientSession() as session:
                    async with session.get(jwks_url) as response:
                        if response.status != 200:
                            logger.error(f"Failed to fetch JWKS. Status: {response.status}")
                            raise HTTPException(status_code=500, detail="Failed to fetch authentication keys")
                        self.jwks = await response.json()
                        logger.debug(f"Successfully fetched JWKS: {json.dumps(self.jwks, indent=2)}")
            except aiohttp.ClientError as e:
                logger.error(f"Network error fetching JWKS: {str(e)}")
                raise HTTPException(status_code=500, detail="Authentication service unavailable")
        return self.jwks

    async def get_current_user(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ) -> User:
        """Verify token and get or create user."""
        if not credentials:
            raise HTTPException(status_code=401, detail="Invalid authorization credentials")

        try:
            # Log the token for debugging (remove in production)
            logger.debug(f"Verifying token: {credentials.credentials[:20]}...")

            # Verify the JWT token
            payload = await self._verify_token(credentials.credentials)

            # Get or create user from the token payload
            try:
                # First try to get user by Auth0 ID
                user = await self.user_service.get_by_auth0_id(payload["sub"])
                if user:
                    # Update last login time
                    user = await self.user_service.record_login(user.id)
                    return user

                # Try finding by email as fallback
                email = payload.get("email")
                if email:
                    user = await self.user_service.get_by_email(email)
                    if user:
                        # Update Auth0 ID and last login
                        user.auth0_id = payload["sub"]
                        user.last_login = datetime.now(UTC)
                        user = await self.user_service.update(user)
                        return user

                # Create new user if not found
                username = self._generate_username(payload)
                email = payload.get("email", "")

                user = await self.user_service.create_user_from_auth0(
                    auth0_id=payload["sub"],
                    email=email,
                    username=username,
                )

                return user

            except Exception as e:
                logger.error(f"Error processing user: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error processing user data")

        except ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except Exception as e:
            logger.error(f"Auth error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    async def _verify_token(self, token: str) -> dict:
        """Verify JWT token and return payload."""
        try:
            # First try to get the unverified header
            try:
                unverified_header = jwt.get_unverified_header(token)
                logger.debug(f"Unverified token header: {json.dumps(unverified_header, indent=2)}")
            except Exception as e:
                logger.error(f"Error getting unverified header: {str(e)}")
                raise HTTPException(status_code=401, detail="Invalid token header")

            # Get the JWKS
            jwks = await self._get_jwks()

            # Find the key for this token
            rsa_key = None
            if "kid" not in unverified_header:
                logger.error("No 'kid' in token header")
                raise HTTPException(status_code=401, detail="Invalid token format")

            for key in jwks["keys"]:
                if key["kid"] == unverified_header["kid"]:
                    logger.debug(f"Found matching key: {json.dumps(key, indent=2)}")
                    rsa_key = key
                    break

            if not rsa_key:
                logger.error(f"No matching key found for kid: {unverified_header['kid']}")
                raise HTTPException(status_code=401, detail="Invalid token key")

            # Decode and verify the token
            try:
                payload = jwt.decode(
                    token, rsa_key, algorithms=self.algorithms, audience=self.audience, issuer=self.issuer
                )
                logger.debug(f"Successfully verified token. Payload: {json.dumps(payload, indent=2)}")
                return payload
            except jwt.ExpiredSignatureError:
                logger.warning("Token has expired")
                raise HTTPException(status_code=401, detail="Token has expired")
            except jwt.JWTClaimsError as e:
                logger.warning(f"Invalid claims: {str(e)}")
                raise HTTPException(status_code=401, detail="Invalid token claims")
            except Exception as e:
                logger.error(f"Error decoding token: {str(e)}")
                raise HTTPException(status_code=401, detail="Invalid token")

        except Exception as e:
            logger.error(f"Token verification error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=401, detail="Invalid token")

    def _generate_username(self, payload: dict) -> str:
        """Generate username from Auth0 payload."""
        # Try different fields in order of preference
        if nickname := payload.get("nickname"):
            return nickname
        if name := payload.get("name"):
            return name.lower().replace(" ", "_")
        if email := payload.get("email"):
            return email.split("@")[0]
        # Fallback to random username
        return f"user_{uuid4().hex[:8]}"
