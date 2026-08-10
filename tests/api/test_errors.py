from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.core.errors import DomainError
from backend.app.main import create_app


def create_error_app(settings: Settings) -> FastAPI:
    app = create_app(settings)

    @app.get("/test/domain-error")
    async def raise_domain_error() -> None:
        raise DomainError("invalid review state")

    @app.get("/test/unexpected-error")
    async def raise_unexpected_error() -> None:
        raise RuntimeError("sensitive detail")

    return app


def test_domain_errors_use_the_public_error_contract(settings: Settings) -> None:
    with TestClient(create_error_app(settings), raise_server_exceptions=False) as client:
        response = client.get("/test/domain-error", headers={"X-Request-ID": "error-request"})

    assert response.status_code == 400
    assert response.json() == {
        "error": {"code": "domain_error", "message": "invalid review state"},
        "request_id": "error-request",
    }


def test_unexpected_errors_do_not_disclose_details(settings: Settings) -> None:
    with TestClient(create_error_app(settings), raise_server_exceptions=False) as client:
        response = client.get("/test/unexpected-error")

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "internal_error",
        "message": "An unexpected error occurred.",
    }
    assert "sensitive detail" not in response.text
