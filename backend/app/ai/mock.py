from __future__ import annotations

import hashlib
import json

from backend.app.ai.contracts import AIRequest, AIResponse


class MockAIProvider:
    """Deterministic development provider that cannot invent scientific values."""

    name = "mock"

    async def generate_structured(self, request: AIRequest) -> AIResponse:
        canonical_input = json.dumps(request.input_data, sort_keys=True, default=str)
        fingerprint = hashlib.sha256(canonical_input.encode()).hexdigest()[:16]
        return AIResponse(
            provider=self.name,
            model_name="deterministic-mock",
            model_version="1",
            prompt_version=request.prompt_version,
            output={
                "status": "NEEDS_REVIEW",
                "reason": "Mock provider does not make scientific determinations.",
                "input_fingerprint": fingerprint,
            },
            usage={"input_tokens": 0, "output_tokens": 0},
        )
