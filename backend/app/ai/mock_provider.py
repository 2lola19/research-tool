from __future__ import annotations

import hashlib
import json
from collections import deque
from typing import Any

from backend.app.ai.domain import AIProviderErrorKind, ProviderResult
from backend.app.ai.provider import AIProviderError, ProviderRequest


class DeterministicMockAIProvider:
    """Fixture-driven provider for safe execution, retry, and validation tests."""

    provider_key = "mock"

    def __init__(
        self, fixtures: list[dict[str, Any] | str | AIProviderErrorKind] | None = None
    ) -> None:
        self._fixtures = deque(fixtures or [])

    async def generate_structured(self, request: ProviderRequest) -> ProviderResult:
        fixture: dict[str, Any] | str | AIProviderErrorKind
        fixture = self._fixtures.popleft() if self._fixtures else self._default_output(request)
        if isinstance(fixture, AIProviderErrorKind):
            raise AIProviderError(fixture, f"deterministic {fixture.value.lower()} fixture")
        encoded = json.dumps(request.structured_input, sort_keys=True, default=str).encode()
        return ProviderResult(
            provider_request_id=f"mock-{hashlib.sha256(encoded).hexdigest()[:16]}",
            provider_model_identifier=request.provider_model_identifier,
            output=fixture,
            usage={
                "input_tokens": 12,
                "output_tokens": 8,
                "cached_tokens": 0,
                "reasoning_tokens": 0,
            },
            duration_ms=1,
        )

    @staticmethod
    def _default_output(request: ProviderRequest) -> dict[str, Any]:
        if request.task_type == "SCREENING_SUGGESTION":
            return {
                "suggestion": "MAYBE",
                "exclusion_criterion_ids": [],
                "rationale": "The deterministic mock retains uncertain citations for human review.",
                "evidence": [],
                "model_reported_confidence": 0.5,
                "uncertainty_reason": "Deterministic mock output requires human screening.",
            }
        return {
            "query": str(request.structured_input.get("query", "")),
            "rationale": "Deterministic mock suggestion for human review.",
            "evidence_references": [],
            "model_reported_confidence": None,
            "abstention": "NEEDS_HUMAN_REVIEW",
        }
