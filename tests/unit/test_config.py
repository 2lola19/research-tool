from backend.app.core.config import Settings


def test_production_disables_interactive_api_docs() -> None:
    settings = Settings(app_env="production", authentication_provider="oidc")

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
