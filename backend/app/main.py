from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response

from backend.app.api.router import build_api_router
from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import install_exception_handlers
from backend.app.core.logging import (
    configure_logging,
    normalize_request_id,
    request_id_context,
    trace_id_context,
    trace_id_from_header,
)
from backend.app.core.metrics import RequestMetrics, safe_route_label
from backend.app.core.rate_limit import InMemoryRateLimiter
from backend.app.db.session import dispose_database

logger = logging.getLogger(__name__)


def _add_security_headers(response: Response, environment: str) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if environment == "production":
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.app_log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info("application_started", extra={"environment": resolved_settings.app_env})
        yield
        await dispose_database()
        logger.info("application_stopped")

    application = FastAPI(
        title="Systematic Review Platform API",
        version="0.1.0",
        docs_url="/docs" if resolved_settings.docs_enabled else None,
        redoc_url="/redoc" if resolved_settings.docs_enabled else None,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.request_metrics = RequestMetrics()
    application.state.auth_rate_limiter = InMemoryRateLimiter(
        max_requests=resolved_settings.app_auth_rate_limit_requests,
        window_seconds=resolved_settings.app_auth_rate_limit_window_seconds,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.app_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Organization-ID",
            "X-Request-ID",
            "traceparent",
        ],
        expose_headers=["X-Request-ID", "X-Trace-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
    )

    @application.middleware("http")
    async def request_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = normalize_request_id(request.headers.get("X-Request-ID"))
        trace_id = trace_id_from_header(request.headers.get("traceparent"))
        request_token = request_id_context.set(request_id)
        trace_token = trace_id_context.set(trace_id)
        started_at = time.perf_counter()
        response: Response | None = None
        try:
            if (
                resolved_settings.app_rate_limit_enabled
                and request.method == "POST"
                and request.url.path.rstrip("/")
                == f"{resolved_settings.app_api_prefix}/auth/token".rstrip("/")
            ):
                client_host = request.client.host if request.client is not None else "unknown"
                decision = application.state.auth_rate_limiter.check(client_host)
                if not decision.allowed:
                    response = JSONResponse(
                        status_code=429,
                        content={
                            "error": {
                                "code": "rate_limited",
                                "message": "too many authentication attempts; try again later",
                            },
                            "request_id": request_id,
                        },
                        headers={
                            "Retry-After": str(decision.retry_after_seconds),
                            "X-RateLimit-Limit": str(
                                resolved_settings.app_auth_rate_limit_requests
                            ),
                            "X-RateLimit-Remaining": "0",
                        },
                    )
                else:
                    response = await call_next(request)
                    response.headers["X-RateLimit-Limit"] = str(
                        resolved_settings.app_auth_rate_limit_requests
                    )
                    response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
            else:
                response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Trace-ID"] = trace_id
            if request.url.path.startswith("/health/"):
                response.headers.setdefault("Cache-Control", "no-store")
            if resolved_settings.app_security_headers_enabled:
                _add_security_headers(response, resolved_settings.app_env)
            return response
        finally:
            if response is not None:
                duration_ms = (time.perf_counter() - started_at) * 1_000
                route = getattr(request.scope.get("route"), "path", None) or "/unmatched"
                application.state.request_metrics.observe(route, response.status_code, duration_ms)
                logger.info(
                    "request_completed",
                    extra={
                        "method": request.method,
                        "route": safe_route_label(route),
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 3),
                    },
                )
            trace_id_context.reset(trace_token)
            request_id_context.reset(request_token)

    install_exception_handlers(application)
    application.include_router(build_api_router(resolved_settings.app_api_prefix))
    return application


app = create_app()
