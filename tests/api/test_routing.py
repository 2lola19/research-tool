from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app


def test_api_routes_use_the_application_settings_prefix(tmp_path: Path) -> None:
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'routing.db').as_posix()}",
        app_api_prefix="/custom-api",
    )

    with TestClient(create_app(settings)) as client:
        assert client.get("/custom-api/system/info").status_code == 200
        assert client.get("/api/v1/system/info").status_code == 404
