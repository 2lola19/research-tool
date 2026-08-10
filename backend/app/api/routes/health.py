from typing import Literal

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.app.api.dependencies import HealthServiceDependency

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["healthy", "unhealthy"]
    checks: dict[str, Literal["up", "down"]] | None = None


@router.get("/health/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(status="healthy")


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def readiness(health_service: HealthServiceDependency) -> HealthResponse | JSONResponse:
    database_is_ready = await health_service.database_is_ready()
    if not database_is_ready:
        payload = HealthResponse(status="unhealthy", checks={"database": "down"})
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload.model_dump(),
        )
    return HealthResponse(status="healthy", checks={"database": "up"})
