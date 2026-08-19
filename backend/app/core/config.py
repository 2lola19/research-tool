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
    ai_live_provider_execution_enabled: bool = False
    ai_provider_user_agent: str = Field(
        default="ResearchTool/0.1 (AI provider adapter)", min_length=1, max_length=200
    )
    ai_provider_timeout_seconds: int = Field(default=60, ge=1, le=300)
    ai_provider_max_attempts: int = Field(default=5, ge=1, le=5)
    ai_per_run_token_ceiling: int = Field(default=16_384, ge=1, le=1_000_000)
    ai_provider_max_response_bytes: int = Field(default=2_000_000, ge=1024, le=10_000_000)
    ai_openai_api_key: SecretStr | None = Field(default=None, repr=False)
    ai_anthropic_api_key: SecretStr | None = Field(default=None, repr=False)
    ai_gemini_api_key: SecretStr | None = Field(default=None, repr=False)
    ai_openai_model_identifier: str = Field(default="gpt-4o-mini", min_length=1, max_length=160)
    ai_anthropic_model_identifier: str = Field(
        default="claude-3-5-haiku-latest", min_length=1, max_length=160
    )
    ai_gemini_model_identifier: str = Field(
        default="gemini-2.0-flash", min_length=1, max_length=160
    )
    ai_openai_allowed_models: list[str] = Field(default_factory=list)
    ai_anthropic_allowed_models: list[str] = Field(default_factory=list)
    ai_gemini_allowed_models: list[str] = Field(default_factory=list)
    ai_openai_input_cost_per_token: float | None = Field(default=None, ge=0)
    ai_openai_output_cost_per_token: float | None = Field(default=None, ge=0)
    ai_anthropic_input_cost_per_token: float | None = Field(default=None, ge=0)
    ai_anthropic_output_cost_per_token: float | None = Field(default=None, ge=0)
    ai_gemini_input_cost_per_token: float | None = Field(default=None, ge=0)
    ai_gemini_output_cost_per_token: float | None = Field(default=None, ge=0)
    ai_monthly_token_budget: int | None = Field(default=1_000_000, ge=1)
    ai_monthly_cost_budget: float | None = Field(default=None, ge=0)
    ai_circuit_failure_threshold: int = Field(default=3, ge=1, le=20)
    ai_circuit_cooldown_seconds: int = Field(default=300, ge=1, le=86_400)
    ai_allow_unknown_cost: bool = False
    ai_require_pricing_for_live_providers: bool = True
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
    worker_id: str = Field(default="review-worker-local", min_length=1, max_length=160)
    worker_max_concurrency: int = Field(default=1, ge=1, le=100)
    worker_lease_seconds: int = Field(default=60, ge=5, le=3600)
    search_provider_execution_enabled: bool = False
    search_provider_user_agent: str = Field(
        default="ResearchTool/0.1", min_length=1, max_length=200
    )
    search_provider_contact_email: str | None = Field(default=None, max_length=320)
    search_provider_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    search_provider_max_pages: int = Field(default=10, ge=1, le=100)
    search_provider_page_size: int = Field(default=100, ge=1, le=1000)
    search_provider_max_response_bytes: int = Field(default=2_000_000, ge=1024, le=10_000_000)
    search_provider_rate_limit_seconds: float = Field(default=0.1, ge=0, le=60)
    search_provider_max_attempts: int = Field(default=3, ge=1, le=5)
    search_pubmed_api_key: SecretStr | None = Field(default=None, repr=False)

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
