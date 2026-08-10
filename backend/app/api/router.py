from fastapi import APIRouter

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.system import router as system_router
from backend.app.core.config import get_settings

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(system_router, prefix=get_settings().app_api_prefix)
