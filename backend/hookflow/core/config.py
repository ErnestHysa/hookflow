"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "HookFlow"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True  # Default to True for local dev

    # API
    api_prefix: str = "/api/v1"
    max_request_size: int = 10 * 1024 * 1024  # 10MB

    # Security
    secret_key: str = Field(default="dev-secret-key-change-in-production-32chars", min_length=32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day

    # Database - default to SQLite for local development
    database_url: str = Field(
        default="sqlite+aiosqlite:///./hookflow_dev.db"
    )

    # Redis - optional, will use in-memory if not set
    redis_url: str | None = Field(default=None)

    # Webhook
    webhook_timeout: int = 30  # seconds
    webhook_max_retries: int = 5
    webhook_retry_delay: int = 60  # seconds (initial backoff)
    webhook_max_deadletter: int = 100  # max failed events per app

    # Retention
    free_retention_hours: int = 24
    pro_retention_days: int = 30
    team_retention_days: int = 90
    enterprise_retention_days: int = 365

    # Rate Limiting
    rate_limit_free: int = 1000  # per month
    rate_limit_pro: int = 100000  # per month
    rate_limit_team: int = 500000  # per month

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Clerk Authentication
    clerk_secret_key: str | None = Field(default=None)
    clerk_webhook_secret: str | None = Field(default=None)
    clerk_frontend_api: str | None = Field(default=None)

    # Stripe Billing
    stripe_secret_key: str | None = Field(default=None)
    stripe_webhook_secret: str | None = Field(default=None)
    stripe_publishable_key: str | None = Field(default=None)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
