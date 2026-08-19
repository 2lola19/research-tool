from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from backend.app.ai.domain import (
    AIProviderErrorKind,
    ProviderResult,
    normalize_usage,
)
from backend.app.ai.mock_provider import DeterministicMockAIProvider
from backend.app.ai.provider import AIProvider, AIProviderError, ProviderRequest
from backend.app.core.config import Settings


@dataclass(frozen=True, slots=True)
class AIProviderCapability:
    provider_key: str
    capabilities: tuple[str, ...]
    network_required: bool
    endpoint_profile: str
    model_allowlist_configured: bool


@dataclass(frozen=True, slots=True)
class AITransportResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class AIHTTPTransport(Protocol):
    async def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> AITransportResponse: ...


class HttpxAIHTTPTransport:
    """Small HTTP boundary; provider behavior remains behind AIProvider."""

    async def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> AITransportResponse:
        try:
            async with (
                httpx.AsyncClient(follow_redirects=False) as client,
                client.stream(
                    "POST",
                    url,
                    headers=dict(headers),
                    json=dict(payload),
                    timeout=timeout_seconds,
                ) as response,
            ):
                body_buffer = bytearray()
                async for chunk in response.aiter_bytes():
                    body_buffer.extend(chunk)
                    if len(body_buffer) > max_response_bytes:
                        raise AIProviderError(
                            AIProviderErrorKind.POLICY_BLOCKED,
                            "AI provider response exceeded the configured size limit",
                            metadata={"max_response_bytes": max_response_bytes},
                        )
                body = bytes(body_buffer)
        except httpx.TimeoutException as exc:
            raise AIProviderError(
                AIProviderErrorKind.TIMEOUT, "AI provider request timed out"
            ) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(
                AIProviderErrorKind.UNAVAILABLE, "AI provider transport was unavailable"
            ) from exc
        return AITransportResponse(
            status_code=response.status_code,
            headers={key.lower(): value for key, value in response.headers.items()},
            body=body,
        )


def _json_object(text: str, provider_key: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```") and candidate.endswith("```"):
        candidate = candidate[3:-3].strip()
        if candidate.casefold().startswith("json"):
            candidate = candidate[4:].lstrip()
    try:
        value = json.loads(candidate)
    except (TypeError, ValueError) as exc:
        raise AIProviderError(
            AIProviderErrorKind.INVALID_RESPONSE,
            f"{provider_key} returned invalid structured JSON",
        ) from exc
    if not isinstance(value, dict):
        raise AIProviderError(
            AIProviderErrorKind.INVALID_RESPONSE,
            f"{provider_key} returned a non-object structured response",
        )
    return value


def _safe_json(body: bytes, provider_key: str) -> dict[str, Any]:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise AIProviderError(
            AIProviderErrorKind.INVALID_RESPONSE,
            f"{provider_key} returned an invalid JSON envelope",
        ) from exc
    if not isinstance(value, dict):
        raise AIProviderError(
            AIProviderErrorKind.INVALID_RESPONSE,
            f"{provider_key} returned an invalid response envelope",
        )
    return value


def _classify_status(status_code: int, provider_key: str) -> AIProviderError:
    if status_code == 429:
        kind = AIProviderErrorKind.RATE_LIMIT
    elif status_code in {408, 504}:
        kind = AIProviderErrorKind.TIMEOUT
    elif status_code >= 500:
        kind = AIProviderErrorKind.UNAVAILABLE
    else:
        kind = AIProviderErrorKind.PERMANENT
    return AIProviderError(
        kind,
        f"{provider_key} provider request failed with HTTP {status_code}",
        metadata={"status_code": status_code},
    )


class _HTTPAIProvider:
    provider_key: str
    endpoint: str
    capability: AIProviderCapability

    def __init__(
        self,
        *,
        api_key: str,
        transport: AIHTTPTransport,
        max_response_bytes: int,
        allowed_model_identifiers: tuple[str, ...],
        user_agent: str,
    ) -> None:
        self._api_key = api_key
        self._transport = transport
        self._max_response_bytes = max_response_bytes
        self.allowed_model_identifiers = allowed_model_identifiers
        self._user_agent = user_agent

    async def _request(
        self,
        request: ProviderRequest,
        payload: Mapping[str, Any],
        *,
        endpoint: str | None = None,
    ) -> dict[str, Any]:
        if self.allowed_model_identifiers and (
            request.provider_model_identifier not in self.allowed_model_identifiers
        ):
            raise AIProviderError(
                AIProviderErrorKind.POLICY_BLOCKED,
                f"{self.provider_key} model is not allowlisted",
            )
        response = await self._transport.post_json(
            endpoint or self.endpoint,
            headers=self._headers(),
            payload=payload,
            timeout_seconds=float(request.timeout_seconds),
            max_response_bytes=self._max_response_bytes,
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise _classify_status(response.status_code, self.provider_key)
        return _safe_json(response.body, self.provider_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": self._user_agent,
        }


class OpenAIProvider(_HTTPAIProvider):
    provider_key = "openai"
    endpoint = "https://api.openai.com/v1/chat/completions"
    capability = AIProviderCapability(
        provider_key="openai",
        capabilities=("structured_generation",),
        network_required=True,
        endpoint_profile="openai-chat-completions-v1",
        model_allowlist_configured=False,
    )

    async def generate_structured(self, request: ProviderRequest) -> ProviderResult:
        payload: dict[str, Any] = {
            "model": request.provider_model_identifier,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        request.structured_input, ensure_ascii=False, sort_keys=True, default=str
                    ),
                },
            ],
            "temperature": request.temperature,
            "response_format": {"type": "json_object"},
        }
        if request.max_output_tokens is not None:
            payload["max_tokens"] = request.max_output_tokens
        envelope = await self._request(request, payload)
        choices = envelope.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise AIProviderError(AIProviderErrorKind.INVALID_RESPONSE, "openai returned no choice")
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise AIProviderError(
                AIProviderErrorKind.INVALID_RESPONSE, "openai returned no structured content"
            )
        raw_usage = envelope.get("usage")
        usage: dict[str, Any] | None = raw_usage if isinstance(raw_usage, dict) else None
        if usage is not None:
            prompt_details = usage.get("prompt_tokens_details")
            completion_details = usage.get("completion_tokens_details")
            usage = {
                **usage,
                "cached_tokens": (
                    prompt_details.get("cached_tokens")
                    if isinstance(prompt_details, dict)
                    else usage.get("cached_tokens")
                ),
                "reasoning_tokens": (
                    completion_details.get("reasoning_tokens")
                    if isinstance(completion_details, dict)
                    else usage.get("reasoning_tokens")
                ),
            }
        return ProviderResult(
            provider_request_id=str(envelope["id"]) if envelope.get("id") else None,
            provider_model_identifier=str(
                envelope.get("model") or request.provider_model_identifier
            ),
            output=_json_object(content, self.provider_key),
            usage=normalize_usage(usage),
            duration_ms=0,
        )

    def _headers(self) -> dict[str, str]:
        return {**super()._headers(), "Accept": "application/json"}


class AnthropicProvider(_HTTPAIProvider):
    provider_key = "anthropic"
    endpoint = "https://api.anthropic.com/v1/messages"
    capability = AIProviderCapability(
        provider_key="anthropic",
        capabilities=("structured_generation",),
        network_required=True,
        endpoint_profile="anthropic-messages-v1",
        model_allowlist_configured=False,
    )

    async def generate_structured(self, request: ProviderRequest) -> ProviderResult:
        payload: dict[str, Any] = {
            "model": request.provider_model_identifier,
            "system": request.system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(
                        request.structured_input, ensure_ascii=False, sort_keys=True, default=str
                    ),
                }
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens or 1024,
        }
        envelope = await self._request(request, payload)
        content_blocks = envelope.get("content")
        if not isinstance(content_blocks, list):
            raise AIProviderError(
                AIProviderErrorKind.INVALID_RESPONSE, "anthropic returned no content blocks"
            )
        text_parts = [
            str(block["text"])
            for block in content_blocks
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        ]
        if not text_parts:
            raise AIProviderError(
                AIProviderErrorKind.INVALID_RESPONSE, "anthropic returned no structured content"
            )
        return ProviderResult(
            provider_request_id=str(envelope["id"]) if envelope.get("id") else None,
            provider_model_identifier=str(
                envelope.get("model") or request.provider_model_identifier
            ),
            output=_json_object("".join(text_parts), self.provider_key),
            usage=normalize_usage(envelope.get("usage")),
            duration_ms=0,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }


class GeminiProvider(_HTTPAIProvider):
    provider_key = "gemini"
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models"
    capability = AIProviderCapability(
        provider_key="gemini",
        capabilities=("structured_generation",),
        network_required=True,
        endpoint_profile="gemini-generate-content-v1beta",
        model_allowlist_configured=False,
    )

    async def generate_structured(self, request: ProviderRequest) -> ProviderResult:
        endpoint = (
            f"{self.endpoint}/{quote(request.provider_model_identifier, safe='')}:generateContent"
        )
        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": request.system_prompt}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": json.dumps(
                                request.structured_input,
                                ensure_ascii=False,
                                sort_keys=True,
                                default=str,
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": request.temperature,
                "responseMimeType": "application/json",
            },
        }
        if request.max_output_tokens is not None:
            payload["generationConfig"]["maxOutputTokens"] = request.max_output_tokens
        envelope = await self._request(request, payload, endpoint=endpoint)
        candidates = envelope.get("candidates")
        if (
            not isinstance(candidates, list)
            or not candidates
            or not isinstance(candidates[0], dict)
        ):
            raise AIProviderError(
                AIProviderErrorKind.INVALID_RESPONSE, "gemini returned no candidate"
            )
        parts = candidates[0].get("content", {}).get("parts", [])
        text_parts = [
            str(part["text"])
            for part in parts
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
        if not text_parts:
            raise AIProviderError(
                AIProviderErrorKind.INVALID_RESPONSE, "gemini returned no structured content"
            )
        return ProviderResult(
            provider_request_id=None,
            provider_model_identifier=request.provider_model_identifier,
            output=_json_object("".join(text_parts), self.provider_key),
            usage=normalize_usage(envelope.get("usageMetadata")),
            duration_ms=0,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }


PROVIDER_CAPABILITIES: dict[str, AIProviderCapability] = {
    "mock": AIProviderCapability(
        provider_key="mock",
        capabilities=("structured_generation",),
        network_required=False,
        endpoint_profile="deterministic-fixture-v1",
        model_allowlist_configured=False,
    ),
    "openai": OpenAIProvider.capability,
    "anthropic": AnthropicProvider.capability,
    "gemini": GeminiProvider.capability,
}


def provider_capability(provider_key: str) -> AIProviderCapability | None:
    return PROVIDER_CAPABILITIES.get(provider_key)


def configured_model_identifier(settings: Settings, provider_key: str) -> str:
    return {
        "mock": "deterministic-mock-v1",
        "openai": settings.ai_openai_model_identifier,
        "anthropic": settings.ai_anthropic_model_identifier,
        "gemini": settings.ai_gemini_model_identifier,
    }.get(provider_key, "")


def configured_model_pricing(settings: Settings, provider_key: str) -> dict[str, str]:
    values = {
        "openai": (
            settings.ai_openai_input_cost_per_token,
            settings.ai_openai_output_cost_per_token,
        ),
        "anthropic": (
            settings.ai_anthropic_input_cost_per_token,
            settings.ai_anthropic_output_cost_per_token,
        ),
        "gemini": (
            settings.ai_gemini_input_cost_per_token,
            settings.ai_gemini_output_cost_per_token,
        ),
    }
    selected = values.get(provider_key)
    if selected is None or selected[0] is None or selected[1] is None:
        return {}
    return {
        "input_cost_per_token": str(selected[0]),
        "output_cost_per_token": str(selected[1]),
        "pricing_version": "configured-v1",
    }


def build_provider_registry(
    settings: Settings, *, transport: AIHTTPTransport | None = None
) -> dict[str, AIProvider]:
    providers: dict[str, AIProvider] = {"mock": DeterministicMockAIProvider()}
    if not settings.ai_live_provider_execution_enabled:
        return providers
    resolved_transport = transport or HttpxAIHTTPTransport()
    if settings.ai_openai_api_key is not None:
        providers["openai"] = OpenAIProvider(
            api_key=settings.ai_openai_api_key.get_secret_value(),
            transport=resolved_transport,
            max_response_bytes=settings.ai_provider_max_response_bytes,
            user_agent=settings.ai_provider_user_agent,
            allowed_model_identifiers=tuple(
                settings.ai_openai_allowed_models or [settings.ai_openai_model_identifier]
            ),
        )
    if settings.ai_anthropic_api_key is not None:
        providers["anthropic"] = AnthropicProvider(
            api_key=settings.ai_anthropic_api_key.get_secret_value(),
            transport=resolved_transport,
            max_response_bytes=settings.ai_provider_max_response_bytes,
            user_agent=settings.ai_provider_user_agent,
            allowed_model_identifiers=tuple(
                settings.ai_anthropic_allowed_models or [settings.ai_anthropic_model_identifier]
            ),
        )
    if settings.ai_gemini_api_key is not None:
        providers["gemini"] = GeminiProvider(
            api_key=settings.ai_gemini_api_key.get_secret_value(),
            transport=resolved_transport,
            max_response_bytes=settings.ai_provider_max_response_bytes,
            user_agent=settings.ai_provider_user_agent,
            allowed_model_identifiers=tuple(
                settings.ai_gemini_allowed_models or [settings.ai_gemini_model_identifier]
            ),
        )
    return providers
