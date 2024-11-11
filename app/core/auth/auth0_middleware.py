import asyncio
from typing import Optional
from uuid import uuid4
import aiohttp
from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import ExpiredSignatureError, jwt
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
    def __init__(self, user_service: UserService):
        self.domain = settings.AUTH0_DOMAIN
        self.audience = settings.AUTH0_AUDIENCE
        self.issuer = f"https://{settings.AUTH0_DOMAIN}/"
        self.algorithms = settings.AUTH0_ALGORITHMS
        self.jwks = None
        self.user_service = user_service
        self.security = Auth0Bearer()
        self.timeout = aiohttp.ClientTimeout(total=10, connect=5, sock_read=5, sock_connect=5)

    async def _get_jwks(self) -> dict:
        """Fetch and cache JWKS from Auth0."""
        if not self.jwks:
            try:
                jwks_url = f"https://{self.domain}/.well-known/jwks.json"
                logger.info(f"Starting JWKS fetch from: {jwks_url}")

                connector = aiohttp.TCPConnector(
                    ssl=False, enable_cleanup_closed=True, force_close=True  # Don't reuse connections
                )

                async with aiohttp.ClientSession(
                    timeout=self.timeout,
                    connector=connector,
                    trust_env=True,
                ) as session:
                    logger.info("Session created, sending request...")
                    try:
                        async with session.get(jwks_url) as response:
                            logger.info(f"Request sent, status: {response.status}")
                            if response.status != 200:
                                error_text = await response.text()
                                logger.error(f"Failed JWKS fetch. Status: {response.status}, Response: {error_text}")
                                raise HTTPException(
                                    status_code=500, detail=f"Failed to fetch authentication keys: {error_text}"
                                )
                            logger.info("Reading response...")
                            self.jwks = await response.json()
                            logger.info("Successfully fetched and parsed JWKS")
                    except asyncio.TimeoutError:
                        logger.error("Timeout while fetching JWKS")
                        raise HTTPException(status_code=500, detail="Authentication service timeout")
                    except aiohttp.ClientError as e:
                        logger.error(f"Client error during JWKS fetch: {str(e)}")
                        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")

            except Exception as e:
                logger.error(f"JWKS fetch failed: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail="Authentication service unavailable")
            finally:
                logger.info("JWKS fetch attempt completed")
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
            logger.info(f"Starting user info fetch from: {userinfo_url}")

            connector = aiohttp.TCPConnector(ssl=False, enable_cleanup_closed=True, force_close=True)

            async with aiohttp.ClientSession(timeout=self.timeout, connector=connector, trust_env=True) as session:
                try:
                    async with session.get(
                        userinfo_url, headers={"Authorization": f"Bearer {access_token}"}
                    ) as response:
                        logger.info(f"User info request sent, status: {response.status}")
                        if response.status != 200:
                            logger.error(f"Failed user info fetch. Status: {response.status}")
                            return {}
                        user_info = await response.json()
                        logger.info("Successfully fetched user info")
                        return user_info
                except asyncio.TimeoutError:
                    logger.error("Timeout while fetching user info")
                    return {}
                except aiohttp.ClientError as e:
                    logger.error(f"Client error during user info fetch: {str(e)}")
                    return {}
        except Exception as e:
            logger.error(f"User info fetch failed: {str(e)}", exc_info=True)
            return {}
        finally:
            logger.info("User info fetch attempt completed")

    def _generate_username(self, payload: dict) -> str:
        """Generate username from Auth0 payload."""
        if nickname := payload.get("nickname"):
            return nickname
        if name := payload.get("name"):
            return name.lower().replace(" ", "_")
        if email := payload.get("email"):
            return email.split("@")[0]
        return f"user_{uuid4().hex[:8]}"

    async def authenticate_request(self, request: Request) -> User:
        """Authenticate a request and return the user."""
        try:
            credentials = await self.security(request)
            if not credentials:
                raise HTTPException(status_code=401, detail="No valid authentication credentials found")

            token = credentials.credentials
            payload = await self._verify_token(token)
            user_info = await self._fetch_user_info(token)
            return await self._get_or_create_user({**payload, **user_info})
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise HTTPException(status_code=401, detail="Authentication failed")

    async def _get_or_create_user(self, user_data: dict) -> User:
        """Get existing user or create new one."""
        try:
            # Try to get user by Auth0 ID
            user = await self.user_service.get_by_auth0_id(user_data["sub"])
            if user:
                return await self.user_service.record_login(user.id)

            # Try to get user by email
            email = user_data.get("email")
            if email:
                user = await self.user_service.get_by_email(email)
                if user:
                    user.auth0_id = user_data["sub"]
                    user.last_login = datetime.now(UTC)
                    return await self.user_service.update(user)

            # Create new user
            username = self._generate_username(user_data)
            email = user_data.get("email") or f"{username}@placeholder.com"

            return await self.user_service.create_user_from_auth0(
                auth0_id=user_data["sub"],
                email=email,
                username=username,
            )
        except Exception as e:
            logger.error(f"Error in user management: {str(e)}")
            raise HTTPException(status_code=500, detail="Error processing user data")
