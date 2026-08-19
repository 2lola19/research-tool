from __future__ import annotations

from backend.app.ai.mock_provider import DeterministicMockAIProvider
from backend.app.ai.outcome_domain import (
    AIOutcomeCandidateType,
    allowed_mapping_manifest,
    outcome_evaluation_metrics,
    validate_outcome_output,
)
from backend.app.ai.service import AIExecutionService
from backend.app.ai.tasks import OUTCOME_TASK


def _input() -> dict[str, object]:
    return {
        "review_id": "00000000-0000-0000-0000-000000000001",
        "study_id": "00000000-0000-0000-0000-000000000002",
        "extraction_value_id": "00000000-0000-0000-0000-000000000003",
        "outcome_version_id": "00000000-0000-0000-0000-000000000004",
        "outcome_definition": {
            "name": "All-cause mortality",
            "compatible_effect_measures": ["RR", "OR"],
        },
        "extraction_value": {
            "reported_value": "10",
            "verified": True,
        },
        "allowed_mappings": {
            "compatible_effect_measures": ["RR", "OR"],
            "allowed_unit_ids": [],
            "allowed_timepoint_window_ids": [],
            "allowed_scale_ids": [],
            "allowed_direction_transformations": ["NONE", "SIGN_REVERSED"],
            "allowed_time_units": ["DAY", "WEEK"],
            "allowed_time_anchors": ["BASELINE", "RANDOMIZATION"],
        },
        "source_documents": [
            {
                "document_id": "doc-1",
                "document_version_id": "doc-1",
            }
        ],
        "chunks": [
            {
                "chunk_id": "chunk-1",
                "document_id": "doc-1",
                "document_version_id": "doc-1",
                "source_block_id": "block-1",
                "page": 1,
                "section": "Results",
                "text": "Ten participants experienced the outcome.",
            }
        ],
    }


def test_outcome_fixture_is_identity_pinned_and_grounded() -> None:
    input_data = _input()
    proposal = DeterministicMockAIProvider.outcome_fixture("SUCCESS_MAPPING", input_data)
    assert isinstance(proposal, dict)
    assert validate_outcome_output(proposal, input_data) == []
    assert proposal["candidate_type"] == AIOutcomeCandidateType.MAPPING.value


def test_outcome_validation_rejects_unsupported_or_fabricated_proposals() -> None:
    input_data = _input()
    fabricated = DeterministicMockAIProvider.outcome_fixture("FABRICATED_CHUNK", input_data)
    assert isinstance(fabricated, dict)
    errors = {item["code"] for item in validate_outcome_output(fabricated, input_data)}
    assert "FABRICATED_CHUNK" in errors

    conversion = DeterministicMockAIProvider.outcome_fixture("CALCULATION_ATTEMPT", input_data)
    assert isinstance(conversion, dict)
    errors = {item["code"] for item in validate_outcome_output(conversion, input_data)}
    assert "UNALLOWED_REFERENCE" in errors


def test_outcome_validation_rejects_wrong_version_and_changed_reported_value() -> None:
    input_data = _input()
    proposal = DeterministicMockAIProvider.outcome_fixture("SUCCESS_MAPPING", input_data)
    assert isinstance(proposal, dict)
    proposal["outcome_version_id"] = "wrong"
    proposal["mapping"]["reported_value"] = "11"  # type: ignore[index]
    errors = {item["code"] for item in validate_outcome_output(proposal, input_data)}
    assert {"WRONG_OUTCOME_VERSION", "REPORTED_VALUE_CHANGED"} <= errors


def test_outcome_evaluation_metrics_are_descriptive_only() -> None:
    metrics = outcome_evaluation_metrics(
        [
            {
                "validation_valid": True,
                "candidate_type": "ABSTAIN",
                "reference_type": "MAPPING",
                "reference_match": False,
                "error_categories": [],
            },
            {
                "validation_valid": False,
                "candidate_type": "MAPPING",
                "reference_type": None,
                "reference_match": False,
                "error_categories": ["UNSUPPORTED_CONVERSION"],
            },
        ]
    )
    assert metrics["abstention_rate"] == 0.5
    assert metrics["unsupported_conversion_count"] == 1
    assert "no threshold" in metrics["calibration"]


def test_outcome_task_is_governed_and_deterministic_post_processed() -> None:
    assert OUTCOME_TASK.human_review_required is True
    assert OUTCOME_TASK.deterministic_post_processing is True
    errors = AIExecutionService._validate_input(_input(), OUTCOME_TASK)
    assert errors is None


def test_outcome_manifest_respects_version_allowed_references() -> None:
    manifest = allowed_mapping_manifest(
        {
            "compatible_effect_measures": ["MD"],
            "allowed_unit_ids": ["unit-2"],
            "allowed_scale_ids": ["scale-2"],
            "expected_timepoint_window_ids": ["window-2"],
        },
        units=[{"id": "unit-1"}, {"id": "unit-2"}],
        windows=[{"id": "window-1"}, {"id": "window-2"}],
        scales=[{"id": "scale-1"}, {"id": "scale-2"}],
    )
    assert manifest["allowed_unit_ids"] == ["unit-2"]
    assert manifest["allowed_timepoint_window_ids"] == ["window-2"]
    assert manifest["allowed_scale_ids"] == ["scale-2"]


def test_reported_effect_requires_explicit_scale_and_safe_values() -> None:
    input_data = _input()
    proposal = DeterministicMockAIProvider.outcome_fixture("EFFECT_REPORTED", input_data)
    assert isinstance(proposal, dict)
    proposal["effect"]["variance_scale"] = None  # type: ignore[index]
    errors = {item["code"] for item in validate_outcome_output(proposal, input_data)}
    assert "INVALID_VARIANCE_SCALE" in errors
