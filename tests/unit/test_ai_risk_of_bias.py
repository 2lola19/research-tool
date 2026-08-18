from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.app.ai.mock_provider import DeterministicMockAIProvider
from backend.app.ai.rob_domain import (
    aggregate_rob_metrics,
    evaluate_rob_case,
    validate_rob_output,
)
from backend.app.ai.tasks import ROB_TASK, prompt_definition
from backend.app.risk_of_bias.domain import normalize_instrument_definition
from backend.app.risk_of_bias.fixtures import DEMONSTRATION_RCT_INSTRUMENT


def _input_and_definition() -> tuple[dict[str, Any], dict[str, Any]]:
    definition = normalize_instrument_definition(DEMONSTRATION_RCT_INSTRUMENT)
    document_id = str(uuid4())
    chunk = {
        "chunk_id": "document:block:p1",
        "document_id": document_id,
        "document_version_id": document_id,
        "source_block_id": "block-id",
        "page": 2,
        "section": "Methods",
        "text": "The allocation sequence was generated centrally and outcome data were complete.",
    }
    input_data: dict[str, Any] = {
        "review_id": str(uuid4()),
        "assessment_id": str(uuid4()),
        "study_id": str(uuid4()),
        "instrument_version_id": str(uuid4()),
        "instrument_definition": definition,
        "questions": [
            {
                "key": question["key"],
                "text": question["text"],
                "allowed_answers": question["allowed_answers"],
            }
            for domain in definition["domains"]
            for question in domain["questions"]
        ],
        "source_documents": [{"document_id": document_id, "document_version_id": document_id}],
        "chunks": [chunk],
    }
    return input_data, definition


def _output(input_data: dict[str, Any], definition: dict[str, Any]) -> dict[str, Any]:
    chunk = input_data["chunks"][0]
    evidence = {
        "document_id": chunk["document_id"],
        "document_version_id": chunk["document_version_id"],
        "chunk_id": chunk["chunk_id"],
        "source_block_id": chunk["source_block_id"],
        "page": chunk["page"],
        "section": chunk["section"],
        "quote": chunk["text"],
    }
    questions = input_data["questions"]
    return {
        "instrument_version_id": input_data["instrument_version_id"],
        "assessment_id": input_data["assessment_id"],
        "answers": [
            {
                "question_key": question["key"],
                "status": "PROPOSED_ANSWER",
                "answer": "YES",
                "evidence": [evidence],
                "confidence": 0.8,
                "note": None,
            }
            for question in questions
        ],
        "rationale": "The proposal is grounded in the pinned evidence and remains advisory.",
        "model_reported_confidence": 0.8,
        "abstention": None,
    }


def test_rob_output_uses_exact_pinned_choices_and_declarative_judgment_rules() -> None:
    input_data, definition = _input_and_definition()
    output = _output(input_data, definition)
    validated = validate_rob_output(output, definition, input_data)
    assert validated["aggregate_valid"] is True
    assert validated["validator_version"] == "ai-rob-validator-1"
    assert validated["domain_suggestions"] == {
        "RANDOMIZATION": "LOW",
        "MISSING_OUTCOME_DATA": "LOW",
    }
    assert validated["overall_suggestion"] == "LOW"

    invalid = {
        **output,
        "answers": [{**output["answers"][0], "answer": "INVENTED"}, *output["answers"][1:]],
    }
    rejected = validate_rob_output(invalid, definition, input_data)
    assert rejected["aggregate_valid"] is False
    assert "ANSWER_NOT_ALLOWED" in rejected["answer_results"][0]["errors"]
    assert rejected["domain_suggestions"] == {}
    assert rejected["overall_suggestion"] is None


def test_rob_output_rejects_fabricated_chunks_and_mismatched_quotes() -> None:
    input_data, definition = _input_and_definition()
    output = _output(input_data, definition)
    evidence = output["answers"][0]["evidence"][0]
    for expected, changed in (
        ("INVALID_CHUNK_REFERENCE", {**evidence, "chunk_id": "fabricated"}),
        ("QUOTE_MISMATCH", {**evidence, "quote": "fabricated evidence"}),
        ("WRONG_SOURCE_BLOCK", {**evidence, "source_block_id": "other"}),
    ):
        altered = {
            **output,
            "answers": [
                {**output["answers"][0], "evidence": [changed]},
                *output["answers"][1:],
            ],
        }
        validated = validate_rob_output(altered, definition, input_data)
        assert expected in validated["answer_results"][0]["errors"]
        assert validated["aggregate_valid"] is False


def test_rob_abstention_is_valid_but_not_an_independent_human_assessment() -> None:
    input_data, definition = _input_and_definition()
    output = _output(input_data, definition)
    abstained = {
        **output,
        "answers": [
            {
                **answer,
                "status": "ABSTAIN",
                "answer": None,
                "evidence": [],
            }
            for answer in output["answers"]
        ],
        "abstention": "Evidence is insufficient.",
    }
    validated = validate_rob_output(abstained, definition, input_data)
    assert validated["aggregate_valid"] is True
    assert validated["domain_suggestions"] == {
        "RANDOMIZATION": None,
        "MISSING_OUTCOME_DATA": None,
    }
    evaluated = evaluate_rob_case(
        abstained,
        validated,
        {question["key"]: "YES" for question in input_data["questions"]},
    )
    assert evaluated["classification"] == "AI_ABSTAIN"
    assert evaluated["abstention"] is True


def test_rob_metrics_are_descriptive_and_surface_high_risk_errors() -> None:
    metrics = aggregate_rob_metrics(
        [
            {
                "classification": "AGREEMENT",
                "signalling_agreement": True,
                "domain_agreement": True,
                "overall_agreement": True,
                "evidence_grounding_valid": True,
                "abstention": False,
                "dangerous_underestimation": False,
            },
            {
                "classification": "DISAGREEMENT",
                "signalling_agreement": False,
                "domain_agreement": False,
                "overall_agreement": False,
                "evidence_grounding_valid": True,
                "abstention": False,
                "dangerous_underestimation": True,
            },
        ]
    )
    assert metrics["signalling_question_agreement"] == 0.5
    assert metrics["dangerous_underestimation_count"] == 1
    assert metrics["calibration"]["status"] == "DESCRIPTIVE_ONLY"
    assert metrics["threshold_label"] == "HYPOTHETICAL EVALUATION ONLY"


def test_rob_task_and_offline_fixtures_preserve_safety_boundary() -> None:
    input_data, definition = _input_and_definition()
    assert ROB_TASK.risk.value == "CRITICAL"
    prompt = prompt_definition(ROB_TASK)
    assert prompt["validation_requirements"]["ai_cannot_assess_or_adjudicate"] is True
    assert "untrusted quoted scientific data" in prompt["system_instructions"]
    success = DeterministicMockAIProvider.rob_fixture("SUCCESS", input_data)
    assert isinstance(success, dict)
    assert success["assessment_id"] == input_data["assessment_id"]
    assert DeterministicMockAIProvider.rob_fixture("FABRICATED_CHUNK", input_data)
    assert definition["name"]
