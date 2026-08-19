from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app


def test_authentication_endpoint_has_process_local_throttle() -> None:
    settings = Settings(
        app_env="test",
        database_url="sqlite+aiosqlite:///:memory:",
        app_auth_rate_limit_requests=2,
        app_auth_rate_limit_window_seconds=60,
    )
    with TestClient(create_app(settings)) as client:
        first = client.post("/api/v1/auth/token", json={})
        second = client.post("/api/v1/auth/token", json={})
        third = client.post("/api/v1/auth/token", json={})

    assert first.status_code == second.status_code == 422
    assert first.headers["X-RateLimit-Remaining"] == "1"
    assert second.headers["X-RateLimit-Remaining"] == "0"
    assert third.status_code == 429
    assert third.headers["Retry-After"]
    assert third.json()["error"]["code"] == "rate_limited"
