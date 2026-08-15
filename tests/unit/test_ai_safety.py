from __future__ import annotations

import pytest

from backend.app.ai.domain import AIProviderErrorKind
from backend.app.ai.mock_provider import DeterministicMockAIProvider
from backend.app.ai.provider import AIProviderError, ProviderRequest
from backend.app.ai.service import AIExecutionService


def _request() -> ProviderRequest:
    return ProviderRequest(
        task_type="SEARCH_QUERY_SUGGESTION",
        provider_model_identifier="mock-v1",
        system_prompt="bounded",
        structured_input={"query": "q", "objective": "o"},
        output_schema={},
        timeout_seconds=1,
        temperature=0,
        top_p=None,
        seed=23,
    )


@pytest.mark.asyncio
async def test_mock_provider_supports_bounded_retry_and_permanent_failure_fixtures() -> None:
    provider = DeterministicMockAIProvider(
        [
            AIProviderErrorKind.TIMEOUT,
            AIProviderErrorKind.RATE_LIMIT,
            {
                "query": "q",
                "rationale": "r",
                "evidence_references": [],
                "model_reported_confidence": None,
                "abstention": "NEEDS_HUMAN_REVIEW",
            },
        ]
    )
    for kind in (AIProviderErrorKind.TIMEOUT, AIProviderErrorKind.RATE_LIMIT):
        with pytest.raises(AIProviderError) as error:
            await provider.generate_structured(_request())
        assert error.value.kind is kind
    assert (await provider.generate_structured(_request())).output[
        "abstention"
    ] == "NEEDS_HUMAN_REVIEW"
    with pytest.raises(AIProviderError) as permanent:
        await DeterministicMockAIProvider([AIProviderErrorKind.PERMANENT]).generate_structured(
            _request()
        )
    assert permanent.value.kind is AIProviderErrorKind.PERMANENT


@pytest.mark.parametrize(
    "output,code",
    [
        ("not-json", "INVALID_JSON_OBJECT"),
        ({}, "MISSING_FIELD"),
        (
            {
                "query": "q",
                "rationale": "r",
                "evidence_references": "forged",
                "model_reported_confidence": None,
                "abstention": "NEEDS_HUMAN_REVIEW",
            },
            "INVALID_EVIDENCE",
        ),
        (
            {
                "query": "q",
                "rationale": "r",
                "evidence_references": [],
                "model_reported_confidence": 4,
                "abstention": "NEEDS_HUMAN_REVIEW",
            },
            "INVALID_CONFIDENCE",
        ),
    ],
)
def test_malformed_outputs_fail_deterministic_validation(output: object, code: str) -> None:
    errors = AIExecutionService._validate_output(output)  # type: ignore[arg-type]
    assert code in {item["code"] for item in errors}


def test_secret_markers_and_oversized_input_are_rejected() -> None:
    with pytest.raises(ValueError, match="secret"):
        AIExecutionService._validate_input(
            {"query": "Authorization: Bearer forbidden", "objective": "test"}
        )
    with pytest.raises(ValueError, match="too large"):
        AIExecutionService._validate_input({"query": "x" * 70_000, "objective": "test"})
