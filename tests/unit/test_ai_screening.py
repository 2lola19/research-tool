from __future__ import annotations

from uuid import uuid4

import pytest

from backend.app.ai.domain import AITaskType
from backend.app.ai.mock_provider import DeterministicMockAIProvider
from backend.app.ai.provider import ProviderRequest
from backend.app.ai.screening_domain import (
    AIScreeningDisagreement,
    AIScreeningSuggestion,
    ScreeningEvaluationPolicy,
    ScreeningReferenceDecision,
    classify_disagreement,
)
from backend.app.ai.screening_metrics import ScreeningPrediction, evaluate_screening_predictions
from backend.app.ai.service import AIExecutionService
from backend.app.ai.tasks import SCREENING_TASK


def test_screening_disagreement_classification_is_explicit() -> None:
    assert (
        classify_disagreement(AIScreeningSuggestion.EXCLUDE, ScreeningReferenceDecision.RETAIN)
        is AIScreeningDisagreement.AI_EXCLUDE_HUMAN_INCLUDE
    )
    assert (
        classify_disagreement(AIScreeningSuggestion.INCLUDE, ScreeningReferenceDecision.EXCLUDE)
        is AIScreeningDisagreement.AI_INCLUDE_HUMAN_EXCLUDE
    )
    assert (
        classify_disagreement(AIScreeningSuggestion.ABSTAIN, ScreeningReferenceDecision.RETAIN)
        is AIScreeningDisagreement.AI_ABSTAIN
    )


def test_conservative_screening_metrics_surface_false_negatives_and_coverage() -> None:
    predictions = [
        ScreeningPrediction(
            case_id=uuid4(),
            article_id=uuid4(),
            proposal_id=uuid4(),
            reference=ScreeningReferenceDecision.RETAIN,
            suggestion=AIScreeningSuggestion.EXCLUDE,
            confidence=0.95,
        ),
        ScreeningPrediction(
            case_id=uuid4(),
            article_id=uuid4(),
            proposal_id=uuid4(),
            reference=ScreeningReferenceDecision.EXCLUDE,
            suggestion=AIScreeningSuggestion.EXCLUDE,
            confidence=0.85,
        ),
        ScreeningPrediction(
            case_id=uuid4(),
            article_id=uuid4(),
            proposal_id=uuid4(),
            reference=ScreeningReferenceDecision.RETAIN,
            suggestion=AIScreeningSuggestion.MAYBE,
            confidence=0.3,
        ),
    ]
    metrics = evaluate_screening_predictions(predictions, ScreeningEvaluationPolicy.CONSERVATIVE)
    assert metrics["confusion_matrix"] == {"tp": 1, "tn": 1, "fp": 0, "fn": 1}
    assert metrics["sensitivity"] == 0.5
    assert metrics["coverage"] == 1.0
    assert metrics["high_risk_disagreements"][0]["classification"] == (
        AIScreeningDisagreement.AI_EXCLUDE_HUMAN_INCLUDE.value
    )
    assert metrics["zero_observed_false_negative_threshold"] == 1.0


def test_screening_output_validation_rejects_forged_evidence_and_criteria() -> None:
    errors = AIExecutionService._validate_output(
        {
            "suggestion": "EXCLUDE",
            "exclusion_criterion_ids": ["exclusion-99"],
            "rationale": "not enough",
            "evidence": [{"quote": "not present"}],
            "model_reported_confidence": 0.7,
            "uncertainty_reason": "",
        },
        SCREENING_TASK,
        {
            "title": "A title",
            "abstract": "An abstract",
            "exclusion_criteria": [{"id": "exclusion-1", "text": "Wrong design"}],
        },
    )
    assert {error["code"] for error in errors} >= {
        "UNKNOWN_CRITERION",
        "EVIDENCE_NOT_IN_SOURCE",
    }


@pytest.mark.asyncio
async def test_screening_mock_output_matches_the_versioned_task_contract() -> None:
    result = await DeterministicMockAIProvider().generate_structured(
        ProviderRequest(
            task_type=AITaskType.SCREENING_SUGGESTION.value,
            provider_model_identifier="deterministic-mock-v1",
            system_prompt="screen",
            structured_input={"title": "A title"},
            output_schema=SCREENING_TASK.output_schema,
            timeout_seconds=10,
            temperature=0.0,
            top_p=None,
            seed=23,
        )
    )
    assert result.output["suggestion"] == "MAYBE"
    assert result.output["exclusion_criterion_ids"] == []
