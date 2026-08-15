from __future__ import annotations

import asyncio

import pytest

from backend.app.ai.domain import AIProviderErrorKind, ProviderResult
from backend.app.ai.execution import call_with_timeout
from backend.app.ai.provider import AIProviderError, ProviderRequest


class SlowProvider:
    provider_key = "slow-mock"

    async def generate_structured(self, request: ProviderRequest) -> ProviderResult:
        await asyncio.sleep(1)
        raise AssertionError("timeout boundary did not cancel the provider")


@pytest.mark.asyncio
async def test_provider_calls_are_actually_bounded_by_timeout() -> None:
    request = ProviderRequest(
        task_type="SEARCH_QUERY_SUGGESTION",
        provider_model_identifier="slow",
        system_prompt="bounded",
        structured_input={},
        output_schema={},
        timeout_seconds=1,
        temperature=0,
        top_p=None,
        seed=None,
    )
    with pytest.raises(AIProviderError) as error:
        await call_with_timeout(SlowProvider(), request, timeout_seconds=0)
    assert error.value.kind is AIProviderErrorKind.TIMEOUT
