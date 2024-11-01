# app/core/config.py
import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: Optional[str] = None
    POSTGRES_USER: str = "will"
    POSTGRES_PASSWORD: str = "nordai123"
    POSTGRES_DB: str = "mitigation_misinformation_db"
    POSTGRES_HOST: str = "misinformation_mitigation_db"
    POSTGRES_PORT: str = "5432"
    VERTEX_AI_LOCATION: str = "us-central1"
    VERTEX_AI_ENDPOINT_ID: str = "us-central1-aiplatform.googleapis.com"
    GOOGLE_CLOUD_PROJECT: str = "mitigation-misinformation"
    GOOGLE_APPLICATION_CREDENTIALS: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "service-account.json"
    )
    LLAMA_MODEL_NAME: str = "meta/llama-3.1-70b-instruct-maas"
    DEBUG: bool = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._log_debug_info()

    def _log_debug_info(self) -> None:
        """Log debug information about configuration"""
        print("\n=== Configuration Debug Information ===")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Environment file location: {os.path.join(os.getcwd(), '.env')}")
        print("\nEnvironment variables loaded:")
        print(f"DATABASE_URL: {self.DATABASE_URL}")
        print(f"POSTGRES_USER: {self.POSTGRES_USER}")
        print(f"POSTGRES_PASSWORD: {'*' * len(self.POSTGRES_PASSWORD) if self.POSTGRES_PASSWORD else 'None'}")
        print(f"POSTGRES_HOST: {self.POSTGRES_HOST}")
        print(f"POSTGRES_DB: {self.POSTGRES_DB}")
        print(f"VERTEX_AI_LOCATION: {self.VERTEX_AI_LOCATION}")
        print(f"VERTEX_AI_ENDPOINT_ID: {self.VERTEX_AI_ENDPOINT_ID}")
        print(f"GOOGLE_CLOUD_PROJECT: {self.GOOGLE_CLOUD_PROJECT}")
        print(f"LLAMA_MODEL_NAME: {self.LLAMA_MODEL_NAME}")
        print(f"Sync Database URL: {self.get_sync_database_url}")
        print(f"Async Database URL: {self.get_async_database_url}")
        print("=====================================\n")

    @property
    def get_sync_database_url(self) -> str:
        """Get synchronous database URL for migrations"""
        if self.DATABASE_URL:
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
        if self.DATABASE_URL:
            # Convert standard URL to async URL
            return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

        return (
            f"postgresql+asyncpg://"
            f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/"
            f"{self.POSTGRES_DB}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance"""
    return Settings()


settings = get_settings()
