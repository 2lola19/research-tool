import pytest

from backend.app.core.config import Settings


def test_production_disables_interactive_api_docs() -> None:
    settings = Settings(
        app_env="production",
        authentication_provider="oidc",
        database_url="postgresql+psycopg://app:password@db.internal:5432/review_platform",
        app_cors_origins=["https://review.example.test"],
        database_require_migrations=True,
        document_parser_provider="grobid",
    )

    assert settings.docs_enabled is False
    assert "database_url" not in repr(settings)


def test_ai_live_execution_is_opt_in_and_secret_is_not_repr() -> None:
    settings = Settings(
        app_env="test",
        ai_openai_api_key="test-secret",
        ai_live_provider_execution_enabled=False,
    )

    assert settings.ai_live_provider_execution_enabled is False
    assert settings.ai_openai_api_key is not None
    assert "test-secret" not in repr(settings)


def test_production_rejects_insecure_deployment_defaults() -> None:
    with pytest.raises(ValueError, match="local authentication"):
        Settings(
            app_env="production",
            database_require_migrations=True,
            app_cors_origins=["https://review.example.test"],
        )

    with pytest.raises(ValueError, match="require PostgreSQL"):
        Settings(
            app_env="production",
            authentication_provider="oidc",
            database_url="sqlite+aiosqlite:///production.db",
            app_cors_origins=["https://review.example.test"],
            database_require_migrations=True,
        )

    with pytest.raises(ValueError, match="CORS origins must use HTTPS"):
        Settings(
            app_env="production",
            authentication_provider="oidc",
            database_url="postgresql+psycopg://app:password@db.internal:5432/review_platform",
            app_cors_origins=["http://review.example.test"],
            database_require_migrations=True,
        )
