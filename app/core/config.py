import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    DATABASE_URL: Optional[str] = None
    DATABASE_PASSWORD: Optional[str] = None
    POSTGRES_USER: str = "will"
    POSTGRES_PASSWORD: str = "nordai123"
    POSTGRES_DB: str = "mitigation_misinformation_db"
    POSTGRES_HOST: str = "misinformation_mitigation_db"
    POSTGRES_PORT: str = "5432"
    VERTEX_AI_LOCATION: str = "us-central1"
    VERTEX_AI_ENDPOINT_ID: str = "us-central1-aiplatform.googleapis.com"
    GOOGLE_CLOUD_PROJECT: str = "misinformation-mitigation"
    AUTH0_DOMAIN: str = "fake-domain"
    AUTH0_AUDIENCE: str = "fake-audience"
    AUTH0_CLIENT_ID: str = "fake-client-id"
    AUTH0_CLIENT_SECRET: str = "fake-client-secret"
    GOOGLE_APPLICATION_CREDENTIALS: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "service-account.json"
    )
    GOOGLE_SEARCH_API_KEY: str = ""
    GOOGLE_SEARCH_ENGINE_ID: str = ""
    LLAMA_MODEL_NAME: str = "meta/llama-3.1-70b-instruct-maas"
    DEBUG: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.DEBUG:
            self._log_debug_info()

    def _log_debug_info(self) -> None:
        """Log debug information about configuration"""

        def mask_password_in_url(url: str) -> str:
            if not url:
                return "None"
            try:
                from urllib.parse import urlparse, urlunparse

                parsed = urlparse(url)
                if "@" in parsed.netloc:
                    userpass, host = parsed.netloc.rsplit("@", 1)
                    if ":" in userpass:
                        user, _ = userpass.split(":", 1)
                        masked_netloc = f"{user}:****@{host}"
                        parsed = parsed._replace(netloc=masked_netloc)
                return urlunparse(parsed)
            except Exception as e:
                logger.error(f"Error masking URL: {e}")
                return "Error masking URL"

        print("\n=== Configuration Debug Information ===")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Environment file location: {os.path.join(os.getcwd(), '.env')}")
        print("\nEnvironment variables loaded:")
        print(f"DATABASE_URL: {mask_password_in_url(self.DATABASE_URL)}")
        print(f"Using Direct DB URL: {bool(self.DATABASE_URL)}")
        print(f"VERTEX_AI_LOCATION: {self.VERTEX_AI_LOCATION}")
        print(f"VERTEX_AI_ENDPOINT_ID: {self.VERTEX_AI_ENDPOINT_ID}")
        print(f"GOOGLE_CLOUD_PROJECT: {self.GOOGLE_CLOUD_PROJECT}")
        print(f"GOOGLE_SEARCH_ENGINE_ID: {self.GOOGLE_SEARCH_ENGINE_ID}")
        print(f"Google Search API configured: {bool(self.GOOGLE_SEARCH_API_KEY)}")
        print(f"LLAMA_MODEL_NAME: {self.LLAMA_MODEL_NAME}")
        print("=====================================\n")

    @property
    def get_sync_database_url(self) -> str:
        """Get synchronous database URL for migrations"""
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
                return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
            return self.DATABASE_URL

        return (
            f"postgresql://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/"
            f"{self.POSTGRES_DB}"
        )

    @property
    def get_async_database_url(self) -> str:
        """Get async database URL for application"""
        sync_url = self.get_sync_database_url
        if sync_url.startswith("postgresql://"):
            return sync_url.replace("postgresql://", "postgresql+asyncpg://")
        return sync_url

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance"""
    return Settings()


settings = get_settings()
