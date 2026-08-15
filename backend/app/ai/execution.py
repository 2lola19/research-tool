from __future__ import annotations

import asyncio

from backend.app.ai.domain import AIProviderErrorKind, ProviderResult
from backend.app.ai.provider import AIProvider, AIProviderError, ProviderRequest


async def call_with_timeout(
    provider: AIProvider, request: ProviderRequest, timeout_seconds: int
) -> ProviderResult:
    try:
        return await asyncio.wait_for(
            provider.generate_structured(request), timeout=float(timeout_seconds)
        )
    except TimeoutError as exc:
        raise AIProviderError(AIProviderErrorKind.TIMEOUT, "provider call timed out") from exc
