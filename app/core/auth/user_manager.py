from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt.algorithms import RSAAlgorithm
import aiohttp
import json
import logging

from app.core.config import settings
from app.services.user_service import UserService
from app.models.domain.user import User
from app.core.auth.user_manager import UserManager

logger = logging.getLogger(__name__)


class Auth0Bearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)

        if credentials:
            if not credentials.scheme.lower() == "bearer":
                if self.auto_error:
                    raise HTTPException(
                        status_code=401,
                        detail="Invalid authentication scheme. Bearer required",
                    )
                return None
            return credentials

        return None


security = Auth0Bearer()


class AuthMiddleware:
    def __init__(self, user_service: UserService):
        self.domain = settings.AUTH0_DOMAIN
        self.audience = settings.AUTH0_AUDIENCE
        self.algorithms = ["RS256"]
        self.jwks = None
        self.user_manager = UserManager(user_service)

    async def get_current_user(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ) -> User:
        """Verify token and get or create user."""
        if not credentials:
            raise HTTPException(status_code=401, detail="Invalid authorization credentials")

        try:
            # Verify the JWT token
            payload = await self._verify_token(credentials.credentials)

            # Get or create user from the verified token payload
            user, created = await self.user_manager.get_or_create_user(payload)

            if created:
                logger.info(f"Created new user: {user.id}")

            return user

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.JWTClaimsError:
            raise HTTPException(status_code=401, detail="Invalid token claims")
        except Exception as e:
            logger.error(f"Auth error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    async def _verify_token(self, token: str) -> dict:
        """Verify JWT token and return payload."""
        if not self.jwks:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://{self.domain}/.well-known/jwks.json") as response:
                    self.jwks = await response.json()

        try:
            unverified_header = jwt.get_unverified_header(token)
            rsa_key = None
            for key in self.jwks["keys"]:
                if key["kid"] == unverified_header["kid"]:
                    rsa_key = {"kty": key["kty"], "kid": key["kid"], "n": key["n"], "e": key["e"]}
                    break

            if not rsa_key:
                raise HTTPException(status_code=401, detail="Invalid token key")

            public_key = RSAAlgorithm.from_jwk(json.dumps(rsa_key))
            payload = jwt.decode(
                token,
                key=public_key,
                algorithms=self.algorithms,
                audience=self.audience,
                issuer=f"https://{self.domain}/",
            )
            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.JWTClaimsError:
            raise HTTPException(status_code=401, detail="Invalid token claims")
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=401, detail="Invalid token")
