from __future__ import annotations

import json
from typing import Any

import pytest

from backend.app.ai.domain import AIProviderErrorKind
from backend.app.ai.provider import AIProviderError, ProviderRequest
from backend.app.ai.providers import (
    AITransportResponse,
    AnthropicProvider,
    GeminiProvider,
    OpenAIProvider,
    build_provider_registry,
)
from backend.app.core.config import Settings


class FakeTransport:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code
        self.calls: list[dict[str, Any]] = []

    async def post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> AITransportResponse:
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
                "max_response_bytes": max_response_bytes,
            }
        )
        return AITransportResponse(
            status_code=self.status_code,
            headers={"content-type": "application/json"},
            body=json.dumps(self.payload).encode(),
        )


def _request(model: str = "test-model") -> ProviderRequest:
    return ProviderRequest(
        task_type="SEARCH_QUERY_SUGGESTION",
        provider_model_identifier=model,
        system_prompt="Return JSON only.",
        structured_input={"query": "aspirin", "objective": "trials"},
        output_schema={"type": "object"},
        timeout_seconds=7,
        temperature=0,
        top_p=None,
        seed=23,
        max_output_tokens=128,
    )


@pytest.mark.asyncio
async def test_openai_adapter_normalizes_structured_output_and_usage() -> None:
    transport = FakeTransport(
        {
            "id": "req-1",
            "model": "test-model",
            "choices": [{"message": {"content": '{"answer":"ok"}'}}],
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 5,
                "prompt_tokens_details": {"cached_tokens": 2},
            },
        }
    )
    provider = OpenAIProvider(
        api_key="secret-value",
        transport=transport,
        max_response_bytes=10_000,
        allowed_model_identifiers=("test-model",),
        user_agent="test-agent",
    )

    result = await provider.generate_structured(_request())

    assert result.output == {"answer": "ok"}
    assert result.usage == {
        "input_tokens": 11,
        "output_tokens": 5,
        "total_tokens": 16,
        "cached_tokens": 2,
        "reasoning_tokens": None,
    }
    assert transport.calls[0]["payload"]["response_format"] == {"type": "json_object"}
    assert transport.calls[0]["headers"]["Authorization"] == "Bearer secret-value"


@pytest.mark.asyncio
async def test_anthropic_adapter_maps_content_blocks() -> None:
    transport = FakeTransport(
        {
            "id": "msg-1",
            "model": "test-model",
            "content": [{"type": "text", "text": '{"answer":"ok"}'}],
            "usage": {"input_tokens": 4, "output_tokens": 3},
        }
    )
    provider = AnthropicProvider(
        api_key="secret-value",
        transport=transport,
        max_response_bytes=10_000,
        allowed_model_identifiers=("test-model",),
        user_agent="test-agent",
    )

    result = await provider.generate_structured(_request())

    assert result.output == {"answer": "ok"}
    assert result.usage["total_tokens"] == 7
    assert transport.calls[0]["headers"]["x-api-key"] == "secret-value"


@pytest.mark.asyncio
async def test_gemini_adapter_uses_header_key_and_normalizes_envelope() -> None:
    transport = FakeTransport(
        {
            "candidates": [{"content": {"parts": [{"text": '{"answer":"ok"}'}]}}],
            "usageMetadata": {
                "promptTokenCount": 6,
                "candidatesTokenCount": 2,
                "totalTokenCount": 8,
            },
        }
    )
    provider = GeminiProvider(
        api_key="secret-value",
        transport=transport,
        max_response_bytes=10_000,
        allowed_model_identifiers=("test-model",),
        user_agent="test-agent",
    )

    result = await provider.generate_structured(_request())

    assert result.output == {"answer": "ok"}
    assert result.usage["total_tokens"] == 8
    assert "/models/test-model:generateContent" in transport.calls[0]["url"]
    assert transport.calls[0]["headers"]["x-goog-api-key"] == "secret-value"


@pytest.mark.asyncio
async def test_provider_http_errors_are_safe_and_retry_classified() -> None:
    transport = FakeTransport({"error": "do not persist"}, status_code=429)
    provider = OpenAIProvider(
        api_key="secret-value",
        transport=transport,
        max_response_bytes=10_000,
        allowed_model_identifiers=("test-model",),
        user_agent="test-agent",
    )

    with pytest.raises(AIProviderError) as raised:
        await provider.generate_structured(_request())

    error = raised.value
    assert error.kind is AIProviderErrorKind.RATE_LIMIT
    assert "do not persist" not in str(error)
    assert "secret-value" not in str(error)


@pytest.mark.asyncio
async def test_provider_model_allowlist_blocks_unapproved_identifier_before_network() -> None:
    transport = FakeTransport({})
    provider = OpenAIProvider(
        api_key="secret-value",
        transport=transport,
        max_response_bytes=10_000,
        allowed_model_identifiers=("approved-model",),
        user_agent="test-agent",
    )

    with pytest.raises(AIProviderError) as raised:
        await provider.generate_structured(_request("unapproved-model"))

    assert raised.value.kind is AIProviderErrorKind.POLICY_BLOCKED
    assert transport.calls == []


def test_live_provider_registry_is_disabled_without_explicit_opt_in() -> None:
    disabled = Settings(app_env="test", ai_openai_api_key="secret-value")
    assert set(build_provider_registry(disabled)) == {"mock"}

    enabled = Settings(
        app_env="test",
        ai_live_provider_execution_enabled=True,
        ai_openai_api_key="secret-value",
    )
    providers = build_provider_registry(enabled, transport=FakeTransport({}))
    assert set(providers) == {"mock", "openai"}
    assert isinstance(providers["openai"], OpenAIProvider)
    assert providers["openai"].allowed_model_identifiers == ("gpt-4o-mini",)
