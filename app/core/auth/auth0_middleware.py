from typing import Optional
from uuid import uuid4
import aiohttp
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import ExpiredSignatureError, jwt
import json
import logging
from datetime import UTC, datetime

from app.core.config import get_settings

# from app.api.dependencies import get_db
from app.repositories.implementations.user_repository import UserRepository
from app.services.user_service import UserService
from app.models.domain.user import User
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)
settings = get_settings()


class Auth0Bearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        try:
            try:
                credentials = await super().__call__(request)
                if credentials and credentials.scheme.lower() == "bearer":
                    return credentials
            except HTTPException:
                pass

            token = request.query_params.get("access_token")
            if token:
                return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

            if self.auto_error:
                raise HTTPException(status_code=401, detail="No valid authentication credentials found")
            return None
        except Exception as e:
            logger.error(f"Auth error in bearer: {str(e)}")
            if self.auto_error:
                raise HTTPException(status_code=401, detail="Authentication failed")
            return None


class Auth0Middleware:
    def __init__(self):
        self.domain = settings.AUTH0_DOMAIN
        self.audience = settings.AUTH0_AUDIENCE
        self.issuer = f"https://{settings.AUTH0_DOMAIN}/"
        self.algorithms = settings.AUTH0_ALGORITHMS
        self.jwks = None
        # self.user_service = user_service
        self.security = Auth0Bearer()

    async def _get_jwks(self) -> dict:
        """Fetch and cache JWKS from Auth0."""
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

    async def _verify_token(self, token: str) -> dict:
        """Verify JWT token and return payload."""
        try:
            unverified_header = jwt.get_unverified_header(token)
            logger.debug(f"Unverified token header: {json.dumps(unverified_header, indent=2)}")

            jwks = await self._get_jwks()
            rsa_key = None

            for key in jwks["keys"]:
                if key["kid"] == unverified_header["kid"]:
                    rsa_key = key
                    break

            if not rsa_key:
                raise HTTPException(status_code=401, detail="Invalid token key")

            payload = jwt.decode(token, rsa_key, algorithms=self.algorithms, audience=self.audience, issuer=self.issuer)
            logger.debug(f"Decoded token payload: {json.dumps(payload, indent=2)}")
            return payload

        except ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            raise HTTPException(status_code=401, detail="Invalid token")

    async def _fetch_user_info(self, access_token: str) -> dict:
        """Fetch additional user info from Auth0."""
        try:
            userinfo_url = f"https://{self.domain}/userinfo"
            async with aiohttp.ClientSession() as session:
                async with session.get(userinfo_url, headers={"Authorization": f"Bearer {access_token}"}) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch user info. Status: {response.status}")
                        return {}
                    return await response.json()
        except Exception as e:
            logger.error(f"Error fetching user info: {str(e)}")
            return {}
        
    async def __call__(self, request: Request, call_next):
        try:
            credentials = await self.security(request)
            if credentials:
                payload = await self._verify_token(credentials.credentials)
                request.state.user_claims = payload
            else:
                request.state.user_claims = None
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        return await call_next(request)

    # def _generate_username(self, payload: dict) -> str:
    #     """Generate username from Auth0 payload."""
    #     if nickname := payload.get("nickname"):
    #         return nickname
    #     if name := payload.get("name"):
    #         return name.lower().replace(" ", "_")
    #     if email := payload.get("email"):
    #         return email.split("@")[0]
    #     return f"user_{uuid4().hex[:8]}"

    # async def authenticate_request(self, request: Request) -> User:
    #     """Authenticate a request and return the user."""
    #     try:
    #         credentials = await self.security(request)
    #         if not credentials:
    #             raise HTTPException(status_code=401, detail="No valid authentication credentials found")

    #         token = credentials.credentials
    #         payload = await self._verify_token(token)
    #         user_info = await self._fetch_user_info(token)
    #         return await self._get_or_create_user({**payload, **user_info})
    #     except Exception as e:
    #         logger.error(f"Authentication error: {str(e)}")
    #         raise HTTPException(status_code=401, detail="Authentication failed")

    # async def _get_or_create_user(self, user_data: dict) -> User:
    #     """Get existing user or create new one."""
    #     try:
    #         async with AsyncSessionLocal() as session:
    #             user_repo = UserRepository(session)
    #             user_service = UserService(user_repo)
    #             # Try to get user by Auth0 ID
    #             user = await user_service.get_by_auth0_id(user_data["sub"])
    #             if user:
    #                 return await user_service.record_login(user.id)

    #             # Try to get user by email
    #             email = user_data.get("email")
    #             if email:
    #                 user = await user_service.get_by_email(email)
    #                 if user:
    #                     user.auth0_id = user_data["sub"]
    #                     user.last_login = datetime.now(UTC)
    #                     return await user_service.update(user)

    #             # Create new user
    #             username = self._generate_username(user_data)
    #             email = user_data.get("email") or f"{username}@placeholder.com"

    #             return await user_service.create_user_from_auth0(
    #                 auth0_id=user_data["sub"],
    #                 email=email,
    #                 username=username,
    #             )
    #     except Exception as e:
    #         logger.error(f"Error in user management: {str(e)}")
    #         raise HTTPException(status_code=500, detail="Error processing user data")
