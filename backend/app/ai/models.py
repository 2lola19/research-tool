from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ModelDefinition:
    internal_model_id: str
    provider: str
    model_name: str
    model_version: str
    task: str
    configuration: dict[str, Any]
    temperature: float
    structured_output_schema: dict[str, Any]
    enabled: bool


MODEL_REGISTRY: tuple[ModelDefinition, ...] = (
    ModelDefinition(
        internal_model_id="mock-default-v1",
        provider="mock",
        model_name="deterministic-mock",
        model_version="1",
        task="development",
        configuration={},
        temperature=0.0,
        structured_output_schema={"type": "object"},
        enabled=True,
    ),
)
