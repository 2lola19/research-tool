from typing import Annotated

from fastapi import Depends

from backend.app.services.health import HealthService, get_health_service

HealthServiceDependency = Annotated[HealthService, Depends(get_health_service)]
