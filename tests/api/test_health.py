from fastapi.testclient import TestClient

from backend.app.services.health import get_health_service


class FakeHealthService:
    def __init__(self, ready: bool, parser_ready: bool | None = None) -> None:
        self._ready = ready
        self._parser_ready = ready if parser_ready is None else parser_ready

    async def database_is_ready(self) -> bool:
        return self._ready

    async def malware_scanner_is_ready(self) -> bool:
        return self._ready

    async def document_parser_is_ready(self) -> bool:
        return self._parser_ready


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
    assert response.json() == {
        "status": "healthy",
        "checks": {"database": "up", "malware_scanner": "up"},
    }


def test_readiness_reports_database_down(client: TestClient) -> None:
    client.app.dependency_overrides[get_health_service] = lambda: FakeHealthService(False)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unhealthy",
        "checks": {"database": "down", "malware_scanner": "down"},
    }


def test_processing_readiness_reports_parser_down_without_failing_liveness(
    client: TestClient,
) -> None:
    client.app.dependency_overrides[get_health_service] = lambda: FakeHealthService(
        True, parser_ready=False
    )

    response = client.get("/health/processing-ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unhealthy",
        "checks": {
            "database": "up",
            "malware_scanner": "up",
            "document_parser": "down",
        },
    }
    assert client.get("/health/live").status_code == 200


def test_metrics_are_low_cardinality_and_operational_only(client: TestClient) -> None:
    client.get("/health/live")

    response = client.get("/health/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "review_http_requests_total" in response.text
    assert "/health/live" in response.text
