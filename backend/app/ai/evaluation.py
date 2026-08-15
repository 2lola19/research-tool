from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app.ai.domain import AITaskType, content_hash


@dataclass(frozen=True, slots=True)
class AIEvaluationCase:
    key: str
    version: int
    task_type: AITaskType
    input_data: dict[str, Any]
    expected_output: dict[str, Any]
    content_hash: str

    @classmethod
    def create(
        cls,
        *,
        key: str,
        version: int,
        task_type: AITaskType,
        input_data: dict[str, Any],
        expected_output: dict[str, Any],
    ) -> AIEvaluationCase:
        scientific_content = {
            "key": key,
            "version": version,
            "task_type": task_type.value,
            "input_data": input_data,
            "expected_output": expected_output,
        }
        return cls(
            key=key,
            version=version,
            task_type=task_type,
            input_data=input_data,
            expected_output=expected_output,
            content_hash=content_hash(scientific_content),
        )


@dataclass(frozen=True, slots=True)
class AIEvaluationResult:
    case_key: str
    case_version: int
    exact_match: bool
    expected_hash: str
    observed_hash: str


def evaluate_exact_match(
    case: AIEvaluationCase, observed_output: dict[str, Any]
) -> AIEvaluationResult:
    expected_hash = content_hash(case.expected_output)
    observed_hash = content_hash(observed_output)
    return AIEvaluationResult(
        case_key=case.key,
        case_version=case.version,
        exact_match=expected_hash == observed_hash,
        expected_hash=expected_hash,
        observed_hash=observed_hash,
    )
