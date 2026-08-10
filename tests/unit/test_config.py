from backend.app.core.config import Settings


def test_production_disables_interactive_api_docs() -> None:
    settings = Settings(app_env="production", authentication_provider="oidc")

    assert settings.docs_enabled is False
    assert "database_url" not in repr(settings)
