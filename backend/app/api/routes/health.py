from typing import Literal

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from backend.app.api.dependencies import HealthServiceDependency

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["healthy", "unhealthy"]
    checks: dict[str, Literal["up", "down"]] | None = None


@router.get("/health/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(status="healthy")


@router.get("/health/metrics", response_class=PlainTextResponse)
async def metrics(request: Request) -> PlainTextResponse:
    settings = request.app.state.settings
    if not settings.app_metrics_enabled:
        return PlainTextResponse("metrics are disabled\n", status_code=status.HTTP_404_NOT_FOUND)
    return PlainTextResponse(
        request.app.state.request_metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4",
    )


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def readiness(health_service: HealthServiceDependency) -> HealthResponse | JSONResponse:
    database_is_ready = await health_service.database_is_ready()
    if not database_is_ready:
        payload = HealthResponse(
            status="unhealthy", checks={"database": "down", "malware_scanner": "down"}
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload.model_dump(),
        )
    scanner_is_ready = await health_service.malware_scanner_is_ready()
    if not scanner_is_ready:
        payload = HealthResponse(
            status="unhealthy", checks={"database": "up", "malware_scanner": "down"}
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload.model_dump(),
        )
    return HealthResponse(status="healthy", checks={"database": "up", "malware_scanner": "up"})


@router.get(
    "/health/processing-ready",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def processing_readiness(
    health_service: HealthServiceDependency,
) -> HealthResponse | JSONResponse:
    database_is_ready = await health_service.database_is_ready()
    scanner_is_ready = await health_service.malware_scanner_is_ready()
    parser_is_ready = await health_service.document_parser_is_ready()
    checks = {
        "database": "up" if database_is_ready else "down",
        "malware_scanner": "up" if scanner_is_ready else "down",
        "document_parser": "up" if parser_is_ready else "down",
    }
    if not all(value == "up" for value in checks.values()):
        payload = HealthResponse(status="unhealthy", checks=checks)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload.model_dump(),
        )
    return HealthResponse(status="healthy", checks=checks)
