"""Application settings using pydantic-settings."""

from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="yeirin-ai", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )

    # API
    api_v1_prefix: str = Field(default="/api/v1", description="API v1 prefix")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"], description="CORS allowed origins"
    )

    # Database (Read-Only)
    database_url: PostgresDsn = Field(
        default="postgresql://yeirin:yeirin123@localhost:5433/yeirin_dev",
        description="PostgreSQL connection URL (read-only)",
    )

    # OpenAI
    openai_api_key: str = Field(description="OpenAI API key")
    openai_model: str = Field(
        default="gpt-4o-mini", description="OpenAI model for recommendations"
    )
    openai_temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="OpenAI temperature parameter"
    )
    openai_max_tokens: int = Field(
        default=2000, gt=0, description="Maximum tokens for OpenAI response"
    )

    # Recommendation Service
    max_recommendations: int = Field(
        default=5, ge=1, le=10, description="Maximum number of recommendations to return"
    )


# Global settings instance
settings = Settings()
