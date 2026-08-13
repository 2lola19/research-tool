from fastapi import APIRouter

from backend.app.api.routes.analysis import router as analysis_router
from backend.app.api.routes.certainty import router as certainty_router
from backend.app.api.routes.citations import router as citations_router
from backend.app.api.routes.deduplication import router as deduplication_router
from backend.app.api.routes.documents import router as documents_router
from backend.app.api.routes.exports import router as exports_router
from backend.app.api.routes.extraction import router as extraction_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.identity import router as identity_router
from backend.app.api.routes.outcomes import router as outcomes_router
from backend.app.api.routes.prisma import router as prisma_router
from backend.app.api.routes.protocols import router as protocols_router
from backend.app.api.routes.provenance import router as provenance_router
from backend.app.api.routes.reporting import router as reporting_router
from backend.app.api.routes.reviews import router as reviews_router
from backend.app.api.routes.risk_of_bias import router as risk_of_bias_router
from backend.app.api.routes.screening import router as screening_router
from backend.app.api.routes.search import router as search_router
from backend.app.api.routes.search_executions import router as search_executions_router
from backend.app.api.routes.studies import router as studies_router
from backend.app.api.routes.system import router as system_router
from backend.app.api.routes.workflow import router as workflow_router
from backend.app.core.config import get_settings


def build_api_router(api_prefix: str) -> APIRouter:
    router = APIRouter()
    router.include_router(health_router)
    router.include_router(citations_router, prefix=api_prefix)
    router.include_router(deduplication_router, prefix=api_prefix)
    router.include_router(documents_router, prefix=api_prefix)
    router.include_router(system_router, prefix=api_prefix)
    router.include_router(identity_router, prefix=api_prefix)
    router.include_router(provenance_router, prefix=api_prefix)
    router.include_router(protocols_router, prefix=api_prefix)
    router.include_router(reviews_router, prefix=api_prefix)
    router.include_router(search_router, prefix=api_prefix)
    router.include_router(search_executions_router, prefix=api_prefix)
    router.include_router(screening_router, prefix=api_prefix)
    router.include_router(workflow_router, prefix=api_prefix)
    router.include_router(studies_router, prefix=api_prefix)
    router.include_router(extraction_router, prefix=api_prefix)
    router.include_router(risk_of_bias_router, prefix=api_prefix)
    router.include_router(outcomes_router, prefix=api_prefix)
    router.include_router(analysis_router, prefix=api_prefix)
    router.include_router(certainty_router, prefix=api_prefix)
    router.include_router(prisma_router, prefix=api_prefix)
    router.include_router(reporting_router, prefix=api_prefix)
    router.include_router(exports_router, prefix=api_prefix)
    return router


api_router = build_api_router(get_settings().app_api_prefix)
