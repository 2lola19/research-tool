from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
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
    notification_provider: Literal["mock", "email"] = "mock"

    @property
    def docs_enabled(self) -> bool:
        return self.app_env != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
