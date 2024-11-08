import json
import logging
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt.algorithms import RSAAlgorithm
import aiohttp

from app.core.config import settings
from app.services.user_service import UserService
from app.core.auth.user_manager import UserManager

security = HTTPBearer()
logger = logging.getLogger(__name__)


class AuthMiddleware:
    def __init__(self, user_service: UserService):
        self.domain = settings.AUTH0_DOMAIN
        self.audience = settings.AUTH0_AUDIENCE
        self.algorithms = ["RS256"]
        self.jwks = None
        self.user_manager = UserManager(user_service)

    async def get_current_user(
        self, credentials: HTTPAuthorizationCredentials = None, request: Request = None
    ) -> Optional[dict]:
        """Verify token and get or create user."""
        if not credentials:
            if not request:
                raise HTTPException(status_code=401, detail="No authorization provided")
            auth = request.headers.get("Authorization")
            if not auth:
                raise HTTPException(status_code=401, detail="No authorization header")
            scheme, credentials = auth.split()
            if scheme.lower() != "bearer":
                raise HTTPException(status_code=401, detail="Invalid authentication scheme")
        else:
            credentials = credentials.credentials

        try:
            payload = await self._verify_token(credentials)
            user, created = await self.user_manager.get_or_create_user(payload)

            if created:
                logger.info(f"Created new user: {user.id}")

            return user
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
