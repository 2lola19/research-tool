from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from backend.app.ai.domain import AIProviderErrorKind, ProviderResult


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    task_type: str
    provider_model_identifier: str
    system_prompt: str
    structured_input: dict[str, Any]
    output_schema: dict[str, Any]
    timeout_seconds: int
    temperature: float
    top_p: float | None
    seed: int | None


class AIProviderError(RuntimeError):
    def __init__(self, kind: AIProviderErrorKind, message: str) -> None:
        self.kind = kind
        super().__init__(message)


class AIProvider(Protocol):
    provider_key: str

    async def generate_structured(self, request: ProviderRequest) -> ProviderResult: ...
