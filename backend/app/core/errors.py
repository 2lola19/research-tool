from __future__ import annotations

import logging
from typing import ClassVar

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from backend.app.core.logging import request_id_context

logger = logging.getLogger(__name__)


class DomainError(Exception):
    code = "domain_error"
    status_code = status.HTTP_400_BAD_REQUEST
    headers: ClassVar[dict[str, str] | None] = None

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ResourceNotFoundError(DomainError):
    code = "not_found"
    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(DomainError):
    code = "conflict"
    status_code = status.HTTP_409_CONFLICT


class AuthenticationError(DomainError):
    code = "authentication_required"
    status_code = status.HTTP_401_UNAUTHORIZED
    headers: ClassVar[dict[str, str]] = {"WWW-Authenticate": "Bearer"}


class AuthorizationError(DomainError):
    code = "access_denied"
    status_code = status.HTTP_403_FORBIDDEN


class InvalidOrganizationContextError(DomainError):
    code = "invalid_organization_context"
    status_code = status.HTTP_400_BAD_REQUEST


class InvalidStateTransitionError(ConflictError):
    code = "invalid_state_transition"


class InvalidCitationImportError(DomainError):
    code = "invalid_citation_import"


class InvalidJobPayloadError(DomainError):
    code = "invalid_job_payload"


class StaleWorkflowDefinitionError(ConflictError):
    code = "stale_workflow_definition"


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "error": {"code": exc.code, "message": exc.message},
                "request_id": request_id_context.get(),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_application_error", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {"code": "internal_error", "message": "An unexpected error occurred."},
                "request_id": request_id_context.get(),
            },
        )
