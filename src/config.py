"""Application configuration using pydantic settings."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    debug: bool = False

    # Database
    database_url: str = "postgresql://hard75:hard75@localhost:5432/hard75"

    # S3/MinIO
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "hard75-photos"
    s3_region: str = "us-east-1"

    # Google OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "http://localhost:8000/auth/callback"

    # Gmail API
    gmail_credentials_file: str = "credentials.json"
    gmail_token_file: str = "token.pickle"

    # Anthropic
    anthropic_api_key: Optional[str] = None

    # Admin
    admin_email: str = "admin@example.com"
    admin_name: str = "Admin User"

    # Agent
    agent_poll_interval_seconds: int = 300  # 5 minutes

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
