from __future__ import annotations

from backend.app.ai.certainty_domain import (
    AICertaintyErrorCategory,
    certainty_evaluation_metrics,
    validate_certainty_output,
)


def _input() -> dict[str, object]:
    return {
        "assessment_id": "assessment-1",
        "outcome_version_id": "outcome-1",
        "framework_version_id": "framework-1",
        "framework_definition": {
            "domains": [
                {
                    "key": "IMPRECISION",
                    "direction": "DOWNGRADE",
                    "label": "Imprecision",
                    "choices": [
                        {"value": "NO_DOWNGRADE", "magnitude": 0},
                        {"value": "DOWNGRADE_ONE", "magnitude": 1},
                    ],
                }
            ]
        },
        "source_documents": [{"document_id": "doc-1", "document_version_id": "doc-1"}],
        "chunks": [
            {
                "chunk_id": "chunk-1",
                "document_id": "doc-1",
                "document_version_id": "doc-1",
                "source_block_id": "block-1",
                "page": 3,
                "section": "Results",
                "text": "The confidence interval was wide.",
            }
        ],
    }


def _valid() -> dict[str, object]:
    evidence = {
        "document_id": "doc-1",
        "document_version_id": "doc-1",
        "chunk_id": "chunk-1",
        "source_block_id": "block-1",
        "page": 3,
        "section": "Results",
        "quote": "confidence interval was wide",
    }
    return {
        "assessment_id": "assessment-1",
        "outcome_version_id": "outcome-1",
        "framework_version_id": "framework-1",
        "evidence_summary": "The confidence interval was wide.",
        "evidence_summary_evidence": [evidence],
        "domain_suggestions": [
            {
                "domain_key": "IMPRECISION",
                "direction": "DOWNGRADE",
                "judgment": "DOWNGRADE_ONE",
                "magnitude": 1,
                "rationale": "The interval is wide in the supplied evidence.",
                "evidence": [evidence],
                "confidence": 0.7,
            }
        ],
        "model_reported_confidence": 0.7,
        "abstention": None,
    }


def test_certainty_output_accepts_only_framework_permitted_grounded_suggestions() -> None:
    assert validate_certainty_output(_valid(), _input()) == []


def test_certainty_output_rejects_unsupported_adjustment_and_final_decision() -> None:
    value = _valid()
    value["final_certainty"] = "HIGH"
    value["domain_suggestions"] = [
        {
            **value["domain_suggestions"][0],  # type: ignore[index]
            "direction": "UPGRADE",
            "magnitude": 2,
        }
    ]
    codes = {item["code"] for item in validate_certainty_output(value, _input())}
    assert "UNSUPPORTED_SCIENTIFIC_DECISION" in codes
    assert "UNSUPPORTED_UPGRADE" in codes
    assert "WRONG_MAGNITUDE" in codes


def test_certainty_output_rejects_fabricated_quote() -> None:
    value = _valid()
    value["evidence_summary_evidence"] = [
        {**value["evidence_summary_evidence"][0], "quote": "not in source"}  # type: ignore[index]
    ]
    codes = {item["code"] for item in validate_certainty_output(value, _input())}
    assert "QUOTE_MISMATCH" in codes


def test_certainty_abstention_cannot_smuggle_a_domain_suggestion() -> None:
    value = _valid()
    value["abstention"] = "The evidence is insufficient."
    codes = {item["code"] for item in validate_certainty_output(value, _input())}
    assert "ABSTENTION_HAS_SUGGESTIONS" in codes


def test_certainty_evaluation_is_descriptive_and_flags_high_risk_categories() -> None:
    metrics = certainty_evaluation_metrics(
        [
            {
                "validation_valid": True,
                "abstention": False,
                "reference_type": "HUMAN_RATIONALE",
                "reference_match": True,
                "error_categories": [],
            },
            {
                "validation_valid": False,
                "abstention": True,
                "reference_type": None,
                "reference_match": False,
                "error_categories": [AICertaintyErrorCategory.UNSUPPORTED_FINAL_DECISION.value],
            },
        ]
    )
    assert metrics["case_count"] == 2
    assert metrics["abstention_count"] == 1
    assert metrics["high_risk_error_count"] == 1
    assert metrics["calibration"]["status"] == "DESCRIPTIVE_ONLY"
