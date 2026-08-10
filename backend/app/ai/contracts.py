from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class AIRequest(BaseModel):
    task: str
    prompt_id: str
    prompt_version: str
    input_data: dict[str, Any]
    model_id: str
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)


class AIResponse(BaseModel):
    provider: str
    model_name: str
    model_version: str
    prompt_version: str
    output: dict[str, Any]
    usage: dict[str, int] = Field(default_factory=dict)


class AIProvider(Protocol):
    name: str

    async def generate_structured(self, request: AIRequest) -> AIResponse: ...
