from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any
from uuid import UUID

from backend.app.ai.domain import content_hash
from backend.app.ai.full_text_domain import FullTextDocumentRole, normalize_evidence_text
from backend.app.ai.screening_domain import AIScreeningMode
from backend.app.documents.domain import Document, DocumentBlock, DocumentProcessingRun
from backend.app.extraction.domain import ExtractionFieldType, MissingnessState


class AIExtractionReadiness(StrEnum):
    READY = "READY"
    BLOCKED_NO_SCHEMA = "BLOCKED_NO_SCHEMA"
    BLOCKED_SCHEMA_NOT_APPROVED = "BLOCKED_SCHEMA_NOT_APPROVED"
    BLOCKED_NO_ASSIGNMENT = "BLOCKED_NO_ASSIGNMENT"
    BLOCKED_NO_DOCUMENT = "BLOCKED_NO_DOCUMENT"
    BLOCKED_DOCUMENT_PROCESSING = "BLOCKED_DOCUMENT_PROCESSING"
    BLOCKED_NO_PARSED_TEXT = "BLOCKED_NO_PARSED_TEXT"
    BLOCKED_UNSUPPORTED_FIELD_TYPE = "BLOCKED_UNSUPPORTED_FIELD_TYPE"
    BLOCKED_STALE_SOURCE = "BLOCKED_STALE_SOURCE"
    BLOCKED_SOURCE_SCOPE = "BLOCKED_SOURCE_SCOPE"
    BLOCKED_OTHER = "BLOCKED_OTHER"


class AIExtractionFieldStatus(StrEnum):
    PROPOSED_VALUE = "PROPOSED_VALUE"
    NOT_REPORTED = "NOT_REPORTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNCLEAR = "UNCLEAR"
    CONFLICTING_SOURCE_VALUES = "CONFLICTING_SOURCE_VALUES"
    REQUIRES_TABLE_OR_FIGURE = "REQUIRES_TABLE_OR_FIGURE"
    REQUIRES_SUPPLEMENT = "REQUIRES_SUPPLEMENT"
    RELATED_REPORT_REQUIRED = "RELATED_REPORT_REQUIRED"
    PARSER_LIMITATION = "PARSER_LIMITATION"
    DOCUMENT_INCOMPLETE = "DOCUMENT_INCOMPLETE"
    ABSTAIN = "ABSTAIN"


class AIExtractionFieldReviewAction(StrEnum):
    ACCEPTED = "ACCEPTED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"
    UNRESOLVED = "UNRESOLVED"


class AIExtractionReferenceStandard(StrEnum):
    ADJUDICATED_EXTRACTION = "ADJUDICATED_EXTRACTION"
    VERIFIED_DUAL_HUMAN = "VERIFIED_DUAL_HUMAN"
    CURATED_GOLD = "CURATED_GOLD"
    FINAL_CANONICAL_VERIFIED = "FINAL_CANONICAL_VERIFIED"


class AIExtractionMatchClass(StrEnum):
    EXACT_MATCH = "EXACT_MATCH"
    NORMALIZED_MATCH = "NORMALIZED_MATCH"
    ACCEPTABLE_WITH_TOLERANCE = "ACCEPTABLE_WITH_TOLERANCE"
    MISMATCH = "MISMATCH"
    AI_MISSING_REFERENCE_VALUE = "AI_MISSING_REFERENCE_VALUE"
    AI_VALUE_REFERENCE_MISSING = "AI_VALUE_REFERENCE_MISSING"
    AI_ABSTAIN = "AI_ABSTAIN"
    INVALID_PROPOSAL = "INVALID_PROPOSAL"
    EVIDENCE_INVALID = "EVIDENCE_INVALID"


class AIExtractionErrorCategory(StrEnum):
    WRONG_VALUE = "WRONG_VALUE"
    WRONG_FIELD = "WRONG_FIELD"
    WRONG_OPTION = "WRONG_OPTION"
    WRONG_UNIT = "WRONG_UNIT"
    WRONG_TIMEPOINT = "WRONG_TIMEPOINT"
    WRONG_ARM = "WRONG_ARM"
    WRONG_POPULATION = "WRONG_POPULATION"
    WRONG_DENOMINATOR = "WRONG_DENOMINATOR"
    HALLUCINATED_VALUE = "HALLUCINATED_VALUE"
    FALSE_NOT_REPORTED = "FALSE_NOT_REPORTED"
    MISSED_REPORTED_VALUE = "MISSED_REPORTED_VALUE"
    CALCULATION_ATTEMPT = "CALCULATION_ATTEMPT"
    CONFLICT_MISSED = "CONFLICT_MISSED"
    SUPPLEMENT_MISSED = "SUPPLEMENT_MISSED"
    TABLE_REQUIRED = "TABLE_REQUIRED"
    PARSER_OMISSION = "PARSER_OMISSION"
    FABRICATED_EVIDENCE = "FABRICATED_EVIDENCE"
    WRONG_DOCUMENT = "WRONG_DOCUMENT"
    QUOTE_MISMATCH = "QUOTE_MISMATCH"
    SCHEMA_MISINTERPRETATION = "SCHEMA_MISINTERPRETATION"
    OTHER = "OTHER"


SAFE_AI_FIELD_TYPES = frozenset(
    {
        ExtractionFieldType.INTEGER,
        ExtractionFieldType.DECIMAL,
        ExtractionFieldType.TEXT,
        ExtractionFieldType.BOOLEAN,
        ExtractionFieldType.CATEGORICAL,
        ExtractionFieldType.ENUM,
        ExtractionFieldType.DATE,
        ExtractionFieldType.CITATION,
    }
)


@dataclass(frozen=True, slots=True)
class PreparedExtractionInput:
    chunks: tuple[dict[str, Any], ...]
    selected_chunk_ids: tuple[str, ...]
    omitted_chunks: tuple[dict[str, Any], ...]
    field_targets: dict[str, tuple[str, ...]]
    selection_method: str
    chunk_manifest_hash: str
    selected_text_hash: str


@dataclass(frozen=True, slots=True)
class ExtractionSource:
    document: Document
    processing: DocumentProcessingRun
    role: FullTextDocumentRole
    blocks: tuple[DocumentBlock, ...]


@dataclass(frozen=True, slots=True)
class AIExtractionPolicy:
    id: UUID
    organization_id: UUID
    review_id: UUID
    version: int
    mode: AIScreeningMode
    maximum_batch_size: int
    created_by_user_id: UUID


@dataclass(frozen=True, slots=True)
class AIExtractionProposalLink:
    id: UUID
    organization_id: UUID
    review_id: UUID
    proposal_id: UUID
    ai_run_id: UUID
    assignment_id: UUID
    study_id: UUID
    schema_version_id: UUID
    schema_hash: str
    ordered_field_hash: str
    task_definition_version: int
    assistance_mode: AIScreeningMode
    source_manifest: list[dict[str, Any]]
    selected_chunk_ids: tuple[str, ...]
    omitted_chunks: tuple[dict[str, Any], ...]
    field_targets: dict[str, list[str]]
    selection_method: str
    chunk_manifest_hash: str
    selected_text_hash: str
    validation_results: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AIExtractionEvaluationDataset:
    id: UUID
    organization_id: UUID
    review_id: UUID
    schema_version_id: UUID
    logical_key: str
    version: int
    name: str
    reference_standard: AIExtractionReferenceStandard
    content_hash: str


def ordered_field_hash(fields: list[dict[str, Any]]) -> str:
    return content_hash(
        [
            {
                "key": item.get("key"),
                "field_type": item.get("field_type"),
                "allowed_options": item.get("allowed_options", []),
                "unit": item.get("unit"),
                "required": bool(item.get("required")),
                "display_order": item.get("display_order", position),
            }
            for position, item in enumerate(fields)
        ]
    )


def prepare_extraction_input(
    fields: list[dict[str, Any]],
    sources: list[ExtractionSource],
    *,
    maximum_characters: int = 24_000,
    maximum_chunks: int = 80,
    characters_per_chunk: int = 3_000,
) -> PreparedExtractionInput:
    """Build a bounded deterministic field-aware snapshot without AI retrieval."""
    if maximum_characters < 1 or maximum_chunks < 1 or characters_per_chunk < 1:
        raise ValueError("extraction input limits must be positive")
    candidates: list[dict[str, Any]] = []
    for source_ordinal, source in enumerate(sources):
        for block in sorted(source.blocks, key=lambda item: (item.block_order, item.block_id)):
            text = normalize_evidence_text(block.text)
            if not text:
                continue
            for part_index, start in enumerate(range(0, len(text), characters_per_chunk), 1):
                part = text[start : start + characters_per_chunk]
                chunk_id = f"{source.document.id}:{block.block_id}:p{part_index}"
                candidates.append(
                    {
                        "chunk_id": chunk_id,
                        "document_id": str(source.document.id),
                        "document_version_id": str(source.document.id),
                        "article_id": str(source.document.article_id),
                        "source_block_id": str(block.id),
                        "parser_block_id": block.block_id,
                        "document_role": source.role.value,
                        "source_ordinal": source_ordinal,
                        "block_order": block.block_order,
                        "block_type": block.block_type.value,
                        "page": block.page_number,
                        "section_path": list(block.section_path),
                        "section": block.section_path[-1] if block.section_path else None,
                        "table_id": block.table_id,
                        "figure_id": block.figure_id,
                        "text": part,
                        "text_hash": content_hash(part),
                    }
                )

    field_targets: dict[str, tuple[str, ...]] = {}
    priority: dict[str, int] = {str(item["chunk_id"]): 0 for item in candidates}
    for field in fields:
        field_id = str(field["key"])
        terms = _field_terms(field)
        ranked = sorted(
            candidates,
            key=lambda item: (
                -_chunk_score(item, terms),
                int(item["source_ordinal"]),
                int(item["block_order"]),
                str(item["chunk_id"]),
            ),
        )
        targeted = tuple(
            str(item["chunk_id"]) for item in ranked[:2] if _chunk_score(item, terms) > 0
        )
        field_targets[field_id] = targeted
        for rank, chunk_id in enumerate(targeted):
            priority[chunk_id] += 2 - rank

    ordered = sorted(
        candidates,
        key=lambda item: (
            -priority[str(item["chunk_id"])],
            int(item["source_ordinal"]),
            int(item["block_order"]),
            str(item["chunk_id"]),
        ),
    )
    selected: list[dict[str, Any]] = []
    omitted: list[dict[str, Any]] = []
    used = 0
    for chunk in ordered:
        size = len(str(chunk["text"]))
        if len(selected) < maximum_chunks and used + size <= maximum_characters:
            selected.append(chunk)
            used += size
        else:
            omitted.append(
                {
                    "chunk_id": str(chunk["chunk_id"]),
                    "document_id": str(chunk["document_id"]),
                    "document_version_id": str(chunk["document_version_id"]),
                    "article_id": str(chunk["article_id"]),
                    "source_block_id": str(chunk["source_block_id"]),
                    "page": chunk["page"],
                    "section": chunk["section"],
                    "table_id": chunk["table_id"],
                    "figure_id": chunk["figure_id"],
                    "text_hash": str(chunk["text_hash"]),
                    "character_count": size,
                }
            )
    selected_ids = {str(item["chunk_id"]) for item in selected}
    field_targets = {
        key: tuple(chunk_id for chunk_id in value if chunk_id in selected_ids)
        for key, value in field_targets.items()
    }
    manifest = [
        {
            "chunk_id": item["chunk_id"],
            "document_id": item["document_id"],
            "text_hash": item["text_hash"],
            "page": item["page"],
            "section": item["section"],
            "table_id": item["table_id"],
            "figure_id": item["figure_id"],
        }
        for item in candidates
    ]
    return PreparedExtractionInput(
        chunks=tuple(selected),
        selected_chunk_ids=tuple(str(item["chunk_id"]) for item in selected),
        omitted_chunks=tuple(omitted),
        field_targets=field_targets,
        selection_method="field-aware-structured-bounded-v1",
        chunk_manifest_hash=content_hash(manifest),
        selected_text_hash=content_hash(
            [{"chunk_id": item["chunk_id"], "text_hash": item["text_hash"]} for item in selected]
        ),
    )


def validate_extraction_output(
    value: dict[str, Any], schema_fields: list[dict[str, Any]], input_data: dict[str, Any]
) -> dict[str, Any]:
    """Return persisted aggregate and per-field deterministic validation results."""
    expected = {str(item["key"]): item for item in schema_fields}
    raw_fields = value.get("fields")
    if not isinstance(raw_fields, list):
        raw_fields = []
    occurrences: dict[str, list[dict[str, Any]]] = {}
    malformed: list[dict[str, Any]] = []
    for item in raw_fields:
        if not isinstance(item, dict) or not isinstance(item.get("field_id"), str):
            malformed.append({"field_id": None, "errors": ["INVALID_FIELD_ENVELOPE"]})
            continue
        occurrences.setdefault(str(item["field_id"]), []).append(item)

    field_results: list[dict[str, Any]] = []
    for field_id, field in expected.items():
        items = occurrences.get(field_id, [])
        if not items:
            field_results.append(
                {"field_id": field_id, "valid": False, "errors": ["MISSING_FIELD_RESULT"]}
            )
            continue
        if len(items) > 1:
            field_results.append(
                {"field_id": field_id, "valid": False, "errors": ["DUPLICATE_FIELD"]}
            )
            continue
        errors = _validate_field(items[0], field, input_data)
        field_results.append({"field_id": field_id, "valid": not errors, "errors": errors})

    unexpected = sorted(set(occurrences) - set(expected))
    for field_id in unexpected:
        field_results.append({"field_id": field_id, "valid": False, "errors": ["UNKNOWN_FIELD"]})
    field_results.extend(malformed)
    valid_count = sum(item.get("valid") is True for item in field_results)
    complete = len(raw_fields) == len(schema_fields) and not unexpected and not malformed
    all_valid = complete and valid_count == len(schema_fields)
    return {
        "validator_version": "ai-extraction-validator-1",
        "aggregate_valid": all_valid,
        "acceptance_ready": all_valid,
        "complete": complete,
        "requested_field_count": len(schema_fields),
        "returned_field_count": len(raw_fields),
        "valid_field_count": valid_count,
        "field_results": field_results,
    }


def field_validation(validation: dict[str, Any], field_id: str) -> dict[str, Any] | None:
    return next(
        (item for item in validation.get("field_results", []) if item.get("field_id") == field_id),
        None,
    )


def manual_missingness(status: AIExtractionFieldStatus) -> MissingnessState:
    mapping = {
        AIExtractionFieldStatus.PROPOSED_VALUE: MissingnessState.VALUE_REPORTED,
        AIExtractionFieldStatus.NOT_REPORTED: MissingnessState.NOT_REPORTED,
        AIExtractionFieldStatus.NOT_APPLICABLE: MissingnessState.NOT_APPLICABLE,
        AIExtractionFieldStatus.UNCLEAR: MissingnessState.UNCLEAR,
    }
    return mapping.get(status, MissingnessState.NEEDS_REVIEW)


def _validate_field(
    item: dict[str, Any], field: dict[str, Any], input_data: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    allowed_keys = {
        "field_id",
        "status",
        "value",
        "reported_value",
        "unit",
        "option_id",
        "evidence",
        "confidence",
        "note",
    }
    if set(item) - allowed_keys:
        errors.append("UNEXPECTED_FIELD_PROPERTY")
    try:
        status = AIExtractionFieldStatus(str(item.get("status", "")))
    except ValueError:
        return [*errors, "INVALID_STATUS"]
    confidence = item.get("confidence")
    if confidence is not None and (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        errors.append("INVALID_CONFIDENCE")
    note = item.get("note")
    if note is not None and (not isinstance(note, str) or len(note) > 2_000):
        errors.append("INVALID_NOTE")

    proposed = status is AIExtractionFieldStatus.PROPOSED_VALUE
    if not proposed:
        if any(item.get(key) is not None for key in ("value", "reported_value", "option_id")):
            errors.append("MISSINGNESS_WITH_VALUE")
        if item.get("unit") is not None:
            errors.append("MISSINGNESS_WITH_UNIT")
        evidence = item.get("evidence")
        if not isinstance(evidence, list):
            errors.append("INVALID_EVIDENCE")
        return errors

    field_type = ExtractionFieldType(str(field["field_type"]))
    if field_type not in SAFE_AI_FIELD_TYPES:
        errors.append("UNSUPPORTED_FIELD_TYPE")
        return errors
    value = item.get("value")
    if value is None:
        errors.append("PROPOSED_VALUE_REQUIRED")
    else:
        errors.extend(_type_errors(value, item.get("option_id"), field_type, field))
    reported = item.get("reported_value")
    if not isinstance(reported, str) or not reported.strip() or len(reported) > 500:
        errors.append("INVALID_REPORTED_VALUE")
    expected_unit = field.get("unit")
    unit = item.get("unit")
    if (expected_unit is not None and unit != expected_unit) or (
        unit is not None and not isinstance(unit, str)
    ):
        errors.append("INVALID_UNIT")
    errors.extend(_evidence_errors(item, input_data, value, reported, field_type))
    return errors


def _type_errors(
    value: Any,
    option_id: Any,
    field_type: ExtractionFieldType,
    field: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    try:
        if field_type is ExtractionFieldType.INTEGER:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError
        elif field_type is ExtractionFieldType.DECIMAL:
            if isinstance(value, bool):
                raise ValueError
            parsed = Decimal(str(value))
            if not parsed.is_finite():
                raise ValueError
        elif field_type is ExtractionFieldType.BOOLEAN:
            if not isinstance(value, bool):
                raise ValueError
        elif field_type is ExtractionFieldType.DATE:
            if not isinstance(value, str):
                raise ValueError
            date.fromisoformat(value)
        elif field_type in {ExtractionFieldType.CATEGORICAL, ExtractionFieldType.ENUM}:
            if option_id is None or option_id != value:
                errors.append("OPTION_ID_REQUIRED")
            if value not in field.get("allowed_options", []):
                errors.append("INVALID_OPTION")
        elif not isinstance(value, str):
            raise ValueError
    except (ValueError, TypeError, InvalidOperation):
        errors.append("WRONG_TYPE")
    return errors


def _evidence_errors(
    item: dict[str, Any],
    input_data: dict[str, Any],
    value: Any,
    reported: Any,
    field_type: ExtractionFieldType,
) -> list[str]:
    errors: list[str] = []
    chunks = {
        str(chunk.get("chunk_id")): chunk
        for chunk in input_data.get("chunks", [])
        if isinstance(chunk, dict)
    }
    allowed_documents = {
        str(source.get("document_id")): source
        for source in input_data.get("source_documents", [])
        if isinstance(source, dict)
    }
    evidence = item.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return ["MISSING_EVIDENCE"]
    reported_supported = False
    numeric_supported = False
    normalized_quotes: list[str] = []
    for span in evidence:
        if not isinstance(span, dict):
            errors.append("INVALID_EVIDENCE")
            continue
        document_id = str(span.get("document_id", ""))
        source = allowed_documents.get(document_id)
        if source is None:
            errors.append("WRONG_DOCUMENT")
        elif str(span.get("document_version_id", "")) != str(source.get("document_version_id", "")):
            errors.append("WRONG_DOCUMENT_VERSION")
        chunk = chunks.get(str(span.get("chunk_id", "")))
        if chunk is None:
            errors.append("INVALID_CHUNK_REFERENCE")
            continue
        if str(chunk.get("document_id")) != document_id:
            errors.append("WRONG_DOCUMENT")
        if span.get("page") != chunk.get("page"):
            errors.append("PAGE_MISMATCH")
        if span.get("section") != chunk.get("section"):
            errors.append("SECTION_MISMATCH")
        if span.get("table_id") != chunk.get("table_id"):
            errors.append("TABLE_MISMATCH")
        quote = span.get("quote")
        if not isinstance(quote, str) or not quote.strip():
            errors.append("MISSING_EVIDENCE_QUOTE")
            continue
        if len(quote) > 500:
            errors.append("EVIDENCE_TOO_LARGE")
            continue
        normalized_quote = normalize_evidence_text(quote)
        if normalized_quote not in normalize_evidence_text(str(chunk.get("text", ""))):
            errors.append("QUOTE_MISMATCH")
            continue
        normalized_quotes.append(normalized_quote)
        if isinstance(reported, str) and normalize_evidence_text(reported) in normalized_quote:
            reported_supported = True
        if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
            numeric_supported = numeric_supported or _numeric_in_text(value, normalized_quote)
    if not reported_supported:
        errors.append("REPORTED_VALUE_NOT_SUPPORTED_BY_QUOTE")
    if (
        isinstance(value, (int, float, Decimal))
        and not isinstance(value, bool)
        and not numeric_supported
    ):
        errors.append("VALUE_NOT_SUPPORTED_BY_QUOTE")
    if normalized_quotes and not _normalized_value_supported(value, field_type, normalized_quotes):
        errors.append("VALUE_NOT_SUPPORTED_BY_QUOTE")
    return list(dict.fromkeys(errors))


def _normalized_value_supported(
    value: Any, field_type: ExtractionFieldType, quotes: list[str]
) -> bool:
    if field_type in {ExtractionFieldType.INTEGER, ExtractionFieldType.DECIMAL}:
        return True  # Numeric source support is checked without binary-float comparison above.
    text = " ".join(quotes).casefold()
    if field_type is ExtractionFieldType.BOOLEAN:
        if value is True:
            return re.search(r"\b(true|yes|present)\b", text) is not None
        if value is False:
            return re.search(r"\b(false|no|not|absent|without)\b", text) is not None
        return False
    normalized = normalize_evidence_text(str(value)).casefold().replace("_", " ").replace("-", " ")
    normalized_text = text.replace("_", " ").replace("-", " ")
    return bool(normalized) and normalized in normalized_text


def _numeric_in_text(value: int | float | Decimal, text: str) -> bool:
    target = Decimal(str(value))
    for token in re.findall(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])", text.replace(",", "")):
        try:
            if Decimal(token) == target:
                return True
        except InvalidOperation:
            continue
    return False


def _field_terms(field: dict[str, Any]) -> tuple[str, ...]:
    raw = " ".join(
        str(field.get(key) or "")
        for key in ("key", "label", "description", "section", "instructions")
    ).casefold()
    tokens = {token for token in re.findall(r"[a-z0-9]+", raw) if len(token) >= 3}
    aliases = {
        "sample": {"participants", "randomized", "enrolled", "consort"},
        "age": {"baseline", "participants", "characteristics", "years"},
        "intervention": {"methods", "procedures", "dose", "schedule"},
        "outcome": {"results", "endpoint", "follow-up"},
    }
    for key, values in aliases.items():
        if key in tokens:
            tokens.update(values)
    return tuple(sorted(tokens))


def _chunk_score(chunk: dict[str, Any], terms: tuple[str, ...]) -> int:
    section = str(chunk.get("section") or "").casefold()
    text = str(chunk.get("text") or "").casefold()
    return sum(4 for term in terms if term in section) + sum(1 for term in terms if term in text)
