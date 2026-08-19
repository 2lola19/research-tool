from fastapi.testclient import TestClient

from backend.app.services.health import get_health_service


class FakeHealthService:
    def __init__(self, ready: bool) -> None:
        self._ready = ready

    async def database_is_ready(self) -> bool:
        return self._ready


def test_liveness_returns_request_id(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "test-request"})

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "checks": None}
    assert response.headers["X-Request-ID"] == "test-request"
    assert response.headers["X-Trace-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_readiness_reports_database_up(client: TestClient) -> None:
    client.app.dependency_overrides[get_health_service] = lambda: FakeHealthService(True)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "checks": {"database": "up"}}


def test_readiness_reports_database_down(client: TestClient) -> None:
    client.app.dependency_overrides[get_health_service] = lambda: FakeHealthService(False)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "checks": {"database": "down"}}


def test_metrics_are_low_cardinality_and_operational_only(client: TestClient) -> None:
    client.get("/health/live")

    response = client.get("/health/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "review_http_requests_total" in response.text
    assert "/health/live" in response.text
