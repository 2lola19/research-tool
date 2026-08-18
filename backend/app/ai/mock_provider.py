from __future__ import annotations

import hashlib
import json
from collections import deque
from typing import Any

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
