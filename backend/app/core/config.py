from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    app_api_prefix: str = "/api/v1"
    app_cors_origins: list[str] = ["http://localhost:3000"]
    database_url: str = Field(
        default="postgresql+psycopg://review:review@localhost:5432/review_platform",
        repr=False,
    )
    database_echo: bool = False
    ai_provider: Literal["mock", "openai", "anthropic", "gemini"] = "mock"
    object_storage_provider: Literal["local", "s3"] = "local"
    local_storage_path: Path = Path("data/objects")
    max_document_file_size_bytes: int = Field(default=25_000_000, ge=1024, le=200_000_000)
    notification_provider: Literal["mock", "email"] = "mock"
    authentication_provider: Literal["local", "oidc"] = "local"
    local_auth_secret: SecretStr = Field(
        default=SecretStr("local-development-only-change-me"),
        repr=False,
    )
    local_auth_token_ttl_seconds: int = Field(default=3600, ge=60, le=86400)

    @model_validator(mode="after")
    def validate_local_authentication_scope(self) -> "Settings":
        if self.authentication_provider == "local" and self.app_env not in {
            "development",
            "test",
        }:
            raise ValueError("local authentication is restricted to development and test")
        return self

    @property
    def docs_enabled(self) -> bool:
        return self.app_env != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
