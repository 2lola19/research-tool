from fastapi.testclient import TestClient


def test_system_info_contains_only_safe_configuration(client: TestClient) -> None:
    response = client.get("/api/v1/system/info")

    assert response.status_code == 200
    assert response.json() == {
        "service": "review-platform-api",
        "version": "0.1.0",
        "environment": "test",
        "ai_provider": "mock",
        "object_storage_provider": "local",
    }
    assert "database" not in response.text
