from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/system", tags=["system"])


class SystemInfoResponse(BaseModel):
    service: Literal["review-platform-api"] = "review-platform-api"
    version: str
    environment: str
    ai_provider: str
    object_storage_provider: str


@router.get("/info", response_model=SystemInfoResponse)
async def system_info(request: Request) -> SystemInfoResponse:
    settings = request.app.state.settings
    return SystemInfoResponse(
        version="0.1.0",
        environment=settings.app_env,
        ai_provider=settings.ai_provider,
        object_storage_provider=settings.object_storage_provider,
    )
