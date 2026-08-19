from __future__ import annotations

import hashlib
import json
from collections import deque
from typing import Any, cast

from backend.app.ai.domain import AIProviderErrorKind, ProviderResult
from backend.app.ai.provider import AIProviderError, ProviderRequest


class DeterministicMockAIProvider:
    """Fixture-driven provider for safe execution, retry, and validation tests."""

    provider_key = "mock"

    def __init__(
        self, fixtures: list[dict[str, Any] | str | AIProviderErrorKind] | None = None
    ) -> None:
        self._fixtures = deque(fixtures or [])

    async def generate_structured(self, request: ProviderRequest) -> ProviderResult:
        fixture: dict[str, Any] | str | AIProviderErrorKind
        fixture = self._fixtures.popleft() if self._fixtures else self._default_output(request)
        if isinstance(fixture, AIProviderErrorKind):
            raise AIProviderError(fixture, f"deterministic {fixture.value.lower()} fixture")
        encoded = json.dumps(request.structured_input, sort_keys=True, default=str).encode()
        return ProviderResult(
            provider_request_id=f"mock-{hashlib.sha256(encoded).hexdigest()[:16]}",
            provider_model_identifier=request.provider_model_identifier,
            output=fixture,
            usage={
                "input_tokens": 12,
                "output_tokens": 8,
                "cached_tokens": 0,
                "reasoning_tokens": 0,
            },
            duration_ms=1,
        )

    @staticmethod
    def _default_output(request: ProviderRequest) -> dict[str, Any]:
        if request.task_type == "EXTRACTION_SUGGESTION":
            schema = request.structured_input.get("schema_identity", {})
            fields = request.structured_input.get("schema_fields", [])
            return {
                "schema_version_id": str(schema.get("schema_version_id", "")),
                "fields": [
                    {
                        "field_id": str(field.get("field_id", "")),
                        "status": "ABSTAIN",
                        "value": None,
                        "reported_value": None,
                        "unit": None,
                        "option_id": None,
                        "evidence": [],
                        "confidence": None,
                        "note": "Deterministic mock requires human extraction.",
                    }
                    for field in fields
                ],
            }
        if request.task_type == "ROB_SUGGESTION":
            return cast(
                dict[str, Any],
                DeterministicMockAIProvider.rob_fixture("ABSTAIN", request.structured_input),
            )
        if request.task_type == "OUTCOME_MAPPING_SUGGESTION":
            return cast(
                dict[str, Any],
                DeterministicMockAIProvider.outcome_fixture("ABSTAIN", request.structured_input),
            )
        if request.task_type == "CERTAINTY_SUGGESTION":
            return cast(
                dict[str, Any],
                DeterministicMockAIProvider.certainty_fixture("ABSTAIN", request.structured_input),
            )
        if request.task_type == "REVIEW_COPILOT":
            return {
                "answer": (
                    "The deterministic copilot abstains; review the cited canonical records "
                    "directly."
                ),
                "citations": [],
                "abstention": "NEEDS_HUMAN_REVIEW",
                "uncertainty_reason": "The offline fixture does not make project-status claims.",
                "model_reported_confidence": None,
            }
        if request.task_type == "FULL_TEXT_SCREENING_SUGGESTION":
            return {
                "suggestion": "MAYBE",
                "exclusion_criterion_ids": [],
                "rationale": "The deterministic mock retains uncertain full texts for review.",
                "evidence": [],
                "missing_information": ["STUDY_DESIGN_UNCLEAR"],
                "model_reported_confidence": 0.5,
                "uncertainty_reason": "Human verification is required.",
            }
        if request.task_type == "SCREENING_SUGGESTION":
            return {
                "suggestion": "MAYBE",
                "exclusion_criterion_ids": [],
                "rationale": "The deterministic mock retains uncertain citations for human review.",
                "evidence": [],
                "model_reported_confidence": 0.5,
                "uncertainty_reason": "Deterministic mock output requires human screening.",
            }
        return {
            "query": str(request.structured_input.get("query", "")),
            "rationale": "Deterministic mock suggestion for human review.",
            "evidence_references": [],
            "model_reported_confidence": None,
            "abstention": "NEEDS_HUMAN_REVIEW",
        }

    @staticmethod
    def full_text_fixture(
        scenario: str, structured_input: dict[str, Any]
    ) -> dict[str, Any] | str | AIProviderErrorKind:
        """Named offline fixtures for the governed full-text task."""
        errors = {
            "timeout": AIProviderErrorKind.TIMEOUT,
            "rate_limit": AIProviderErrorKind.RATE_LIMIT,
            "transient_failure": AIProviderErrorKind.UNAVAILABLE,
            "permanent_failure": AIProviderErrorKind.PERMANENT,
        }
        if scenario in errors:
            return errors[scenario]
        if scenario == "malformed":
            return "not-a-structured-object"
        identity = structured_input.get("document_identity", {})
        chunks = structured_input.get("chunks", [])
        first_chunk = chunks[0] if chunks else {}
        criteria = structured_input.get("exclusion_criteria", [])
        first_criterion = criteria[0].get("id") if criteria else "exclusion-1"
        base: dict[str, Any] = {
            "suggestion": "MAYBE",
            "exclusion_criterion_ids": [],
            "rationale": "Deterministic full-text fixture for human review.",
            "evidence": [],
            "missing_information": ["STUDY_DESIGN_UNCLEAR"],
            "model_reported_confidence": 0.5,
            "uncertainty_reason": "Eligibility remains uncertain.",
        }
        if scenario == "include":
            return {
                **base,
                "suggestion": "INCLUDE",
                "missing_information": [],
                "uncertainty_reason": None,
            }
        if scenario == "maybe":
            return base
        if scenario == "abstain":
            return {
                **base,
                "suggestion": "ABSTAIN",
                "missing_information": ["SUPPLEMENT_REQUIRED"],
                "uncertainty_reason": "A required supplement is unavailable.",
            }
        evidence = {
            "document_id": str(identity.get("document_id", "")),
            "document_version_id": str(identity.get("document_version_id", "")),
            "chunk_id": str(first_chunk.get("chunk_id", "")),
            "page": first_chunk.get("page"),
            "section": first_chunk.get("section"),
            "quoted_text": str(first_chunk.get("text", ""))[:80],
        }
        excluded = {
            **base,
            "suggestion": "EXCLUDE",
            "exclusion_criterion_ids": [first_criterion],
            "evidence": [evidence],
            "missing_information": [],
            "uncertainty_reason": None,
            "model_reported_confidence": 0.9,
        }
        if scenario == "exclude_valid":
            return excluded
        if scenario == "fabricated_criterion":
            return {**excluded, "exclusion_criterion_ids": ["fabricated-criterion"]}
        if scenario == "fabricated_chunk":
            return {**excluded, "evidence": [{**evidence, "chunk_id": "fabricated:chunk"}]}
        if scenario == "wrong_page":
            return {**excluded, "evidence": [{**evidence, "page": 999999}]}
        if scenario == "quote_mismatch":
            return {**excluded, "evidence": [{**evidence, "quoted_text": "fabricated quote"}]}
        if scenario == "wrong_document":
            return {**excluded, "evidence": [{**evidence, "document_id": "wrong-document"}]}
        if scenario == "oversized_output":
            return {**base, "rationale": "x" * 40_000}
        raise ValueError(f"unknown full-text mock fixture: {scenario}")

    @staticmethod
    def extraction_fixture(
        scenario: str, structured_input: dict[str, Any]
    ) -> dict[str, Any] | str | AIProviderErrorKind:
        """Named deterministic fixtures for schema-pinned structured extraction."""
        scenario = scenario.upper()
        errors = {
            "TIMEOUT": AIProviderErrorKind.TIMEOUT,
            "RATE_LIMIT": AIProviderErrorKind.RATE_LIMIT,
            "TRANSIENT_FAILURE": AIProviderErrorKind.UNAVAILABLE,
            "PERMANENT_FAILURE": AIProviderErrorKind.PERMANENT,
        }
        if scenario in errors:
            return errors[scenario]
        if scenario == "MALFORMED_JSON":
            return "not-a-structured-object"
        schema = structured_input.get("schema_identity", {})
        fields = structured_input.get("schema_fields", [])
        chunks = structured_input.get("chunks", [])
        chunk = chunks[0] if chunks else {}
        sources = structured_input.get("source_documents", [])
        source = sources[0] if sources else {}

        def abstain(field: dict[str, Any]) -> dict[str, Any]:
            return {
                "field_id": str(field.get("field_id", "")),
                "status": "ABSTAIN",
                "value": None,
                "reported_value": None,
                "unit": None,
                "option_id": None,
                "evidence": [],
                "confidence": None,
                "note": "Human extraction is required.",
            }

        output = {
            "schema_version_id": str(schema.get("schema_version_id", "")),
            "fields": [abstain(field) for field in fields],
        }
        if scenario in {"SUCCESS_PARTIAL", "ABSTAIN"}:
            return output
        status_map = {
            "NOT_REPORTED": "NOT_REPORTED",
            "UNCLEAR": "UNCLEAR",
            "CONFLICTING_VALUES": "CONFLICTING_SOURCE_VALUES",
            "REQUIRES_SUPPLEMENT": "REQUIRES_SUPPLEMENT",
            "REQUIRES_TABLE": "REQUIRES_TABLE_OR_FIGURE",
        }
        if scenario in status_map:
            return {
                **output,
                "fields": [{**abstain(field), "status": status_map[scenario]} for field in fields],
            }
        if not fields:
            return output
        field = fields[0]
        quote = str(chunk.get("text", ""))[:120]
        evidence = {
            "document_id": str(source.get("document_id", chunk.get("document_id", ""))),
            "document_version_id": str(
                source.get("document_version_id", chunk.get("document_version_id", ""))
            ),
            "chunk_id": str(chunk.get("chunk_id", "")),
            "page": chunk.get("page"),
            "section": chunk.get("section"),
            "table_id": chunk.get("table_id"),
            "figure_id": chunk.get("figure_id"),
            "quote": quote,
        }
        proposed = {
            **abstain(field),
            "status": "PROPOSED_VALUE",
            "value": 148,
            "reported_value": "148",
            "unit": field.get("unit"),
            "evidence": [evidence],
            "confidence": 0.91,
            "note": None,
        }
        result_fields = [proposed, *[abstain(item) for item in fields[1:]]]
        if scenario in {"SUCCESS_COMPLETE", "PROMPT_INJECTION_SOURCE"}:
            return {**output, "fields": result_fields}
        if scenario == "UNKNOWN_FIELD":
            return {**output, "fields": [*result_fields, {**abstain(field), "field_id": "unknown"}]}
        if scenario == "DUPLICATE_FIELD":
            return {**output, "fields": [proposed, proposed, *result_fields[1:]]}
        if scenario == "WRONG_TYPE":
            return {**output, "fields": [{**proposed, "value": "twenty"}, *result_fields[1:]]}
        if scenario == "INVALID_OPTION":
            return {
                **output,
                "fields": [
                    {**proposed, "value": "INVENTED", "option_id": "INVENTED"},
                    *result_fields[1:],
                ],
            }
        if scenario == "INVALID_UNIT":
            return {**output, "fields": [{**proposed, "unit": "invented"}, *result_fields[1:]]}
        if scenario == "FABRICATED_CHUNK":
            return {
                **output,
                "fields": [
                    {**proposed, "evidence": [{**evidence, "chunk_id": "fabricated:chunk"}]},
                    *result_fields[1:],
                ],
            }
        if scenario == "WRONG_DOCUMENT":
            return {
                **output,
                "fields": [
                    {**proposed, "evidence": [{**evidence, "document_id": "wrong"}]},
                    *result_fields[1:],
                ],
            }
        if scenario == "WRONG_PAGE":
            return {
                **output,
                "fields": [
                    {**proposed, "evidence": [{**evidence, "page": 999999}]},
                    *result_fields[1:],
                ],
            }
        if scenario == "QUOTE_MISMATCH":
            return {
                **output,
                "fields": [
                    {**proposed, "evidence": [{**evidence, "quote": "fabricated quote"}]},
                    *result_fields[1:],
                ],
            }
        if scenario == "VALUE_NOT_SUPPORTED_BY_QUOTE":
            return {
                **output,
                "fields": [{**proposed, "value": 999, "reported_value": "999"}, *result_fields[1:]],
            }
        if scenario == "OVERSIZED_OUTPUT":
            return {**output, "fields": [{**proposed, "note": "x" * 40_000}]}
        raise ValueError(f"unknown extraction mock fixture: {scenario}")

    @staticmethod
    def rob_fixture(
        scenario: str, structured_input: dict[str, Any]
    ) -> dict[str, Any] | str | AIProviderErrorKind:
        """Named offline fixtures for document-grounded Risk of Bias assistance."""
        scenario = scenario.upper()
        errors = {
            "TIMEOUT": AIProviderErrorKind.TIMEOUT,
            "RATE_LIMIT": AIProviderErrorKind.RATE_LIMIT,
            "TRANSIENT_FAILURE": AIProviderErrorKind.UNAVAILABLE,
            "PERMANENT_FAILURE": AIProviderErrorKind.PERMANENT,
        }
        if scenario in errors:
            return errors[scenario]
        if scenario == "MALFORMED_JSON":
            return "not-a-structured-object"
        questions = structured_input.get("questions", [])
        chunks = structured_input.get("chunks", [])
        first_chunk = chunks[0] if chunks else {}
        base_answers: list[dict[str, Any]] = [
            {
                "question_key": str(question.get("key", "")),
                "status": "ABSTAIN",
                "answer": None,
                "evidence": [],
                "confidence": None,
                "note": "Human Risk of Bias assessment is required.",
            }
            for question in questions
        ]
        base: dict[str, Any] = {
            "instrument_version_id": str(structured_input.get("instrument_version_id", "")),
            "assessment_id": str(structured_input.get("assessment_id", "")),
            "answers": base_answers,
            "rationale": "The deterministic mock abstains pending human assessment.",
            "model_reported_confidence": 0.5,
            "abstention": "HUMAN_ASSESSMENT_REQUIRED",
        }
        if scenario in {"ABSTAIN", "SUCCESS_ABSTAIN"}:
            return base
        if not questions:
            return base
        question = questions[0]
        allowed = list(question.get("allowed_answers", []))
        answer = allowed[0] if allowed else ""
        evidence = {
            "document_id": str(first_chunk.get("document_id", "")),
            "document_version_id": str(first_chunk.get("document_version_id", "")),
            "chunk_id": str(first_chunk.get("chunk_id", "")),
            "source_block_id": str(first_chunk.get("source_block_id", "")),
            "page": first_chunk.get("page"),
            "section": first_chunk.get("section"),
            "quote": str(first_chunk.get("text", ""))[:120],
        }
        proposed = {
            **base_answers[0],
            "status": "PROPOSED_ANSWER",
            "answer": answer,
            "evidence": [evidence],
            "confidence": 0.8,
            "note": None,
        }
        if scenario in {"SUCCESS", "SUCCESS_PARTIAL"}:
            return {**base, "answers": [proposed, *base_answers[1:]], "abstention": None}
        if scenario == "WRONG_ANSWER":
            return {
                **base,
                "answers": [{**proposed, "answer": "INVENTED"}, *base_answers[1:]],
                "abstention": None,
            }
        if scenario == "FABRICATED_CHUNK":
            return {
                **base,
                "answers": [
                    {**proposed, "evidence": [{**evidence, "chunk_id": "fabricated"}]},
                    *base_answers[1:],
                ],
                "abstention": None,
            }
        if scenario == "QUOTE_MISMATCH":
            return {
                **base,
                "answers": [
                    {**proposed, "evidence": [{**evidence, "quote": "fabricated quote"}]},
                    *base_answers[1:],
                ],
                "abstention": None,
            }
        if scenario == "WRONG_DOCUMENT":
            return {
                **base,
                "answers": [
                    {**proposed, "evidence": [{**evidence, "document_id": "wrong"}]},
                    *base_answers[1:],
                ],
                "abstention": None,
            }
        if scenario == "OVERSIZED_OUTPUT":
            return {**base, "rationale": "x" * 40_000}
        raise ValueError(f"unknown Risk of Bias mock fixture: {scenario}")

    @staticmethod
    def outcome_fixture(
        scenario: str, structured_input: dict[str, Any]
    ) -> dict[str, Any] | str | AIProviderErrorKind:
        """Named offline fixtures for governed outcome harmonization assistance."""
        scenario = scenario.upper()
        errors = {
            "TIMEOUT": AIProviderErrorKind.TIMEOUT,
            "RATE_LIMIT": AIProviderErrorKind.RATE_LIMIT,
            "TRANSIENT_FAILURE": AIProviderErrorKind.UNAVAILABLE,
            "PERMANENT_FAILURE": AIProviderErrorKind.PERMANENT,
        }
        if scenario in errors:
            return errors[scenario]
        if scenario == "MALFORMED_JSON":
            return "not-a-structured-object"
        base: dict[str, Any] = {
            "outcome_version_id": str(structured_input.get("outcome_version_id", "")),
            "extraction_value_id": str(structured_input.get("extraction_value_id", "")),
            "candidate_type": "ABSTAIN",
            "mapping": None,
            "effect": None,
            "evidence": [],
            "rationale": "The deterministic mock abstains pending human harmonization.",
            "model_reported_confidence": 0.5,
            "abstention": "HUMAN_HARMONIZATION_REQUIRED",
        }
        if scenario in {"ABSTAIN", "SUCCESS_ABSTAIN"}:
            return base
        chunks = structured_input.get("chunks", [])
        first = chunks[0] if chunks else {}
        outcome = structured_input.get("outcome_definition", {})
        measures = list(outcome.get("compatible_effect_measures", []))
        mapping = {
            "reported_value": structured_input.get("extraction_value", {}).get("reported_value"),
            "reported_unit_id": None,
            "normalized_unit_id": None,
            "reported_time_value": None,
            "reported_time_unit": None,
            "reported_time_anchor": None,
            "timepoint_window_id": None,
            "measurement_scale_id": None,
            "direction_transformation": "NONE",
            "transformation_reason": None,
        }
        evidence = {
            "document_id": str(first.get("document_id", "")),
            "document_version_id": str(first.get("document_version_id", "")),
            "chunk_id": str(first.get("chunk_id", "")),
            "source_block_id": str(first.get("source_block_id", "")),
            "page": first.get("page"),
            "section": first.get("section"),
            "quote": str(first.get("text", ""))[:120],
        }
        proposed = {
            **base,
            "candidate_type": "MAPPING",
            "mapping": mapping,
            "evidence": [evidence],
            "rationale": "Deterministic outcome mapping fixture for human review.",
            "model_reported_confidence": 0.8,
            "abstention": None,
        }
        if scenario in {"SUCCESS", "SUCCESS_MAPPING"}:
            return proposed
        if scenario == "UNSUPPORTED_MEASURE":
            return {
                **proposed,
                "candidate_type": "EFFECT_ESTIMATE",
                "mapping": None,
                "effect": {"effect_measure": "INVENTED", "estimate": "2"},
            }
        if scenario == "WRONG_VERSION":
            return {**proposed, "outcome_version_id": "wrong-version"}
        if scenario == "WRONG_EXTRACTION":
            return {**proposed, "extraction_value_id": "wrong-extraction"}
        if scenario == "FABRICATED_CHUNK":
            return {**proposed, "evidence": [{**evidence, "chunk_id": "fabricated"}]}
        if scenario == "QUOTE_MISMATCH":
            return {**proposed, "evidence": [{**evidence, "quote": "fabricated quote"}]}
        if scenario == "WRONG_DOCUMENT":
            return {**proposed, "evidence": [{**evidence, "document_id": "wrong"}]}
        if scenario == "CALCULATION_ATTEMPT":
            return {
                **proposed,
                "mapping": {**mapping, "normalized_unit_id": "invented-conversion"},
                "rationale": "Converted 10 mg to 0.01 g automatically.",
            }
        if scenario == "OVERSIZED_OUTPUT":
            return {**base, "rationale": "x" * 40_000}
        if scenario == "EFFECT_REPORTED":
            measure = measures[0] if measures else "RR"
            return {
                **proposed,
                "candidate_type": "EFFECT_ESTIMATE",
                "mapping": None,
                "effect": {
                    "effect_measure": measure,
                    "estimate": "1.2",
                    "standard_error": "0.2",
                    "variance": "0.04",
                    "variance_scale": "LOG" if measure in {"RR", "OR", "HR"} else "NATURAL",
                    "ci_lower": None,
                    "ci_upper": None,
                    "confidence_level": None,
                    "adjustment": "UNADJUSTED",
                    "analysis_population": "UNCLEAR",
                    "components": {},
                },
            }
        raise ValueError(f"unknown outcome mock fixture: {scenario}")

    @staticmethod
    def certainty_fixture(
        scenario: str, structured_input: dict[str, Any]
    ) -> dict[str, Any] | str | AIProviderErrorKind:
        """Named deterministic fixtures for governed certainty drafting assistance."""
        scenario = scenario.upper()
        errors = {
            "TIMEOUT": AIProviderErrorKind.TIMEOUT,
            "RATE_LIMIT": AIProviderErrorKind.RATE_LIMIT,
            "TRANSIENT_FAILURE": AIProviderErrorKind.UNAVAILABLE,
            "PERMANENT_FAILURE": AIProviderErrorKind.PERMANENT,
        }
        if scenario in errors:
            return errors[scenario]
        if scenario == "MALFORMED_JSON":
            return "not-a-structured-object"
        base: dict[str, Any] = {
            "assessment_id": str(structured_input.get("assessment_id", "")),
            "outcome_version_id": str(structured_input.get("outcome_version_id", "")),
            "framework_version_id": str(structured_input.get("framework_version_id", "")),
            "evidence_summary": None,
            "evidence_summary_evidence": [],
            "domain_suggestions": [],
            "model_reported_confidence": 0.5,
            "abstention": "HUMAN_CERTAINTY_JUDGMENT_REQUIRED",
        }
        if scenario in {"ABSTAIN", "SUCCESS_ABSTAIN"}:
            return base
        framework = structured_input.get("framework_definition", {})
        domains = framework.get("domains", []) if isinstance(framework, dict) else []
        chunks = structured_input.get("chunks", [])
        first = chunks[0] if chunks else {}
        evidence = {
            "document_id": str(first.get("document_id", "")),
            "document_version_id": str(first.get("document_version_id", "")),
            "chunk_id": str(first.get("chunk_id", "")),
            "source_block_id": str(first.get("source_block_id", "")),
            "page": first.get("page"),
            "section": first.get("section"),
            "quote": str(first.get("text", ""))[:80],
        }
        first_domain = domains[0] if domains else {}
        choices = first_domain.get("choices", []) if isinstance(first_domain, dict) else []
        choice = choices[0] if choices else {"value": "NO_DOWNGRADE", "magnitude": 0}
        suggestion = {
            "domain_key": first_domain.get("key", ""),
            "direction": first_domain.get("direction", "DOWNGRADE"),
            "judgment": choice.get("value"),
            "magnitude": choice.get("magnitude", 0),
            "rationale": "The supplied evidence is presented for human certainty review.",
            "evidence": [evidence],
            "confidence": 0.5,
        }
        if scenario == "SUCCESS_SUGGESTION":
            return {
                **base,
                "evidence_summary": "The supplied evidence requires explicit human appraisal.",
                "evidence_summary_evidence": [evidence],
                "domain_suggestions": [suggestion],
                "abstention": None,
            }
        if scenario == "UNSUPPORTED_DIRECTION":
            return {
                **base,
                "domain_suggestions": [{**suggestion, "direction": "UPGRADE"}],
                "abstention": None,
            }
        if scenario == "WRONG_MAGNITUDE":
            return {
                **base,
                "domain_suggestions": [{**suggestion, "magnitude": 2}],
                "abstention": None,
            }
        if scenario == "FORBIDDEN_FINAL":
            return {**base, "final_certainty": "HIGH"}
        if scenario == "FABRICATED_EVIDENCE":
            return {
                **base,
                "domain_suggestions": [
                    {**suggestion, "evidence": [{**evidence, "quote": "fabricated"}]}
                ],
                "abstention": None,
            }
        if scenario == "OVERSIZED_OUTPUT":
            return {**base, "evidence_summary": "x" * 40_000}
        raise ValueError(f"unknown certainty mock fixture: {scenario}")
