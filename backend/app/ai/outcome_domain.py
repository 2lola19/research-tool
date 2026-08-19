from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any
from uuid import UUID

from backend.app.ai.domain import content_hash
from backend.app.ai.extraction_domain import ExtractionSource, prepare_extraction_input
from backend.app.ai.full_text_domain import normalize_evidence_text


class AIOutcomeReadiness(StrEnum):
    READY = "READY"
    BLOCKED_NO_EXTRACTION = "BLOCKED_NO_EXTRACTION"
    BLOCKED_UNVERIFIED_EXTRACTION = "BLOCKED_UNVERIFIED_EXTRACTION"
    BLOCKED_OUTCOME_VERSION = "BLOCKED_OUTCOME_VERSION"
    BLOCKED_SOURCE_SCOPE = "BLOCKED_SOURCE_SCOPE"
    BLOCKED_DOCUMENT_PROCESSING = "BLOCKED_DOCUMENT_PROCESSING"
    BLOCKED_NO_PARSED_TEXT = "BLOCKED_NO_PARSED_TEXT"
    BLOCKED_OTHER = "BLOCKED_OTHER"


class AIOutcomeCandidateType(StrEnum):
    MAPPING = "MAPPING"
    EFFECT_ESTIMATE = "EFFECT_ESTIMATE"
    ABSTAIN = "ABSTAIN"


class AIOutcomeReviewAction(StrEnum):
    ACCEPTED = "ACCEPTED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"
    UNRESOLVED = "UNRESOLVED"


class AIOutcomeAccessType(StrEnum):
    ASSISTED_VIEW = "ASSISTED_VIEW"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class AIOutcomeReferenceStandard(StrEnum):
    HUMAN_HARMONIZED = "HUMAN_HARMONIZED"
    CURATED_GOLD = "CURATED_GOLD"
    FINAL_CANONICAL = "FINAL_CANONICAL"


class AIOutcomeErrorCategory(StrEnum):
    WRONG_OUTCOME = "WRONG_OUTCOME"
    WRONG_EXTRACTION = "WRONG_EXTRACTION"
    WRONG_UNIT = "WRONG_UNIT"
    WRONG_TIMEPOINT = "WRONG_TIMEPOINT"
    WRONG_SCALE = "WRONG_SCALE"
    WRONG_MEASURE = "WRONG_MEASURE"
    UNSUPPORTED_CONVERSION = "UNSUPPORTED_CONVERSION"
    CALCULATION_ATTEMPT = "CALCULATION_ATTEMPT"
    HALLUCINATED_COMPONENT = "HALLUCINATED_COMPONENT"
    FABRICATED_EVIDENCE = "FABRICATED_EVIDENCE"
    WRONG_DOCUMENT = "WRONG_DOCUMENT"
    QUOTE_MISMATCH = "QUOTE_MISMATCH"
    UNSUPPORTED_ABSOLUTE_EFFECT = "UNSUPPORTED_ABSOLUTE_EFFECT"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class PreparedOutcomeInput:
    chunks: tuple[dict[str, Any], ...]
    selected_chunk_ids: tuple[str, ...]
    omitted_chunks: tuple[dict[str, Any], ...]
    selection_method: str
    chunk_manifest_hash: str
    selected_text_hash: str


@dataclass(frozen=True, slots=True)
class AIOutcomePolicy:
    id: UUID
    organization_id: UUID
    review_id: UUID
    version: int
    maximum_batch_size: int
    created_by_user_id: UUID


@dataclass(frozen=True, slots=True)
class AIOutcomeProposalLink:
    id: UUID
    organization_id: UUID
    review_id: UUID
    proposal_id: UUID
    ai_run_id: UUID
    study_id: UUID
    extraction_value_id: UUID
    outcome_version_id: UUID
    outcome_version_hash: str
    extraction_snapshot_hash: str
    task_definition_version: int
    source_manifest: list[dict[str, Any]]
    selected_chunk_ids: tuple[str, ...]
    omitted_chunks: tuple[dict[str, Any], ...]
    selection_method: str
    chunk_manifest_hash: str
    selected_text_hash: str
    validation_results: dict[str, Any]


def prepare_outcome_input(
    outcome_definition: dict[str, Any],
    sources: list[ExtractionSource],
    *,
    maximum_characters: int = 24_000,
    maximum_chunks: int = 80,
) -> PreparedOutcomeInput:
    """Use the deterministic extraction chunk selector for outcome evidence."""
    fields = [
        {
            "key": "outcome_reported_value",
            "label": outcome_definition.get("name", "reported outcome"),
            "description": outcome_definition.get("description"),
            "field_type": "TEXT",
            "required": True,
            "instructions": "Locate the exact reported outcome value; never normalize it.",
        }
    ]
    prepared = prepare_extraction_input(
        fields,
        sources,
        maximum_characters=maximum_characters,
        maximum_chunks=maximum_chunks,
    )
    return PreparedOutcomeInput(
        chunks=prepared.chunks,
        selected_chunk_ids=prepared.selected_chunk_ids,
        omitted_chunks=prepared.omitted_chunks,
        selection_method=prepared.selection_method,
        chunk_manifest_hash=prepared.chunk_manifest_hash,
        selected_text_hash=prepared.selected_text_hash,
    )


def source_manifest(sources: list[ExtractionSource]) -> list[dict[str, Any]]:
    return [
        {
            "article_id": str(source.document.article_id),
            "document_id": str(source.document.id),
            "document_version_id": str(source.document.id),
            "document_role": source.role.value,
            "document_content_hash": source.document.sha256
            or content_hash(
                {
                    "document_id": str(source.document.id),
                    "source_identifier": source.document.source_identifier,
                }
            ),
            "processing_run_id": str(source.processing.id),
            "parser_name": source.processing.parser_name,
            "parser_version": source.processing.parser_version,
            "parsed_content_hash": content_hash(
                [
                    {
                        "block_id": block.block_id,
                        "block_type": block.block_type.value,
                        "order": block.block_order,
                        "page": block.page_number,
                        "section_path": block.section_path,
                        "table_id": block.table_id,
                        "figure_id": block.figure_id,
                        "text_hash": content_hash(block.text),
                    }
                    for block in source.blocks
                ]
            ),
            "block_count": len(source.blocks),
        }
        for source in sources
    ]


def allowed_mapping_manifest(
    outcome_definition: dict[str, Any],
    *,
    units: list[dict[str, Any]],
    windows: list[dict[str, Any]],
    scales: list[dict[str, Any]],
) -> dict[str, Any]:
    def permitted_items(items: list[dict[str, Any]], definition_key: str) -> list[str]:
        declared = {
            str(item) for item in outcome_definition.get(definition_key, []) if str(item).strip()
        }
        return [
            str(item.get("id")) for item in items if not declared or str(item.get("id")) in declared
        ]

    return {
        "compatible_effect_measures": list(
            outcome_definition.get("compatible_effect_measures", [])
        ),
        "allowed_unit_ids": permitted_items(units, "allowed_unit_ids"),
        "allowed_timepoint_window_ids": permitted_items(windows, "expected_timepoint_window_ids"),
        "allowed_scale_ids": permitted_items(scales, "allowed_scale_ids"),
        "allowed_direction_transformations": ["NONE", "SIGN_REVERSED"],
        "allowed_time_units": ["DAY", "WEEK", "MONTH", "YEAR"],
        "allowed_time_anchors": [
            "BASELINE",
            "RANDOMIZATION",
            "INTERVENTION_START",
            "DIAGNOSIS",
            "OTHER",
        ],
    }


def validate_outcome_output(
    value: dict[str, Any], input_data: dict[str, Any]
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if str(value.get("outcome_version_id", "")) != str(input_data.get("outcome_version_id", "")):
        errors.append(
            {"code": "WRONG_OUTCOME_VERSION", "message": "outcome version does not match"}
        )
    if str(value.get("extraction_value_id", "")) != str(input_data.get("extraction_value_id", "")):
        errors.append(
            {"code": "WRONG_EXTRACTION_VALUE", "message": "extraction value does not match"}
        )
    try:
        candidate = AIOutcomeCandidateType(str(value.get("candidate_type", "")))
    except ValueError:
        errors.append({"code": "INVALID_CANDIDATE_TYPE", "message": "unknown candidate type"})
        candidate = AIOutcomeCandidateType.ABSTAIN
    rationale = value.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip() or len(rationale) > 4_000:
        errors.append({"code": "INVALID_RATIONALE", "message": "rationale must be bounded text"})
    confidence = value.get("model_reported_confidence")
    if confidence is not None and (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        errors.append(
            {"code": "INVALID_CONFIDENCE", "message": "confidence must be from 0 through 1"}
        )
    abstention = value.get("abstention")
    if candidate is AIOutcomeCandidateType.ABSTAIN and (
        not isinstance(abstention, str) or not abstention.strip()
    ):
        errors.append(
            {"code": "ABSTENTION_REASON_REQUIRED", "message": "ABSTAIN requires a reason"}
        )
    if candidate is not AIOutcomeCandidateType.ABSTAIN and abstention is not None:
        errors.append(
            {"code": "NON_ABSTAINING_OUTPUT_HAS_ABSTENTION", "message": "abstention must be null"}
        )

    evidence = value.get("evidence")
    if not isinstance(evidence, list):
        errors.append({"code": "INVALID_EVIDENCE", "message": "evidence must be a list"})
    elif candidate is not AIOutcomeCandidateType.ABSTAIN:
        if not evidence:
            errors.append({"code": "MISSING_EVIDENCE", "message": "candidate requires evidence"})
        errors.extend(_evidence_errors(evidence, input_data))
    elif evidence:
        errors.extend(_evidence_errors(evidence, input_data))

    if candidate is AIOutcomeCandidateType.MAPPING:
        if value.get("effect") is not None:
            errors.append(
                {"code": "MAPPING_HAS_EFFECT", "message": "mapping cannot include effect"}
            )
        errors.extend(_mapping_errors(value.get("mapping"), input_data))
    elif candidate is AIOutcomeCandidateType.EFFECT_ESTIMATE:
        if value.get("mapping") is not None:
            errors.append(
                {"code": "EFFECT_HAS_MAPPING", "message": "effect cannot include mapping"}
            )
        errors.extend(_effect_errors(value.get("effect"), input_data))
    else:
        if value.get("mapping") is not None or value.get("effect") is not None:
            errors.append(
                {
                    "code": "ABSTAIN_HAS_CANDIDATE",
                    "message": "ABSTAIN cannot include candidate data",
                }
            )
    return errors


def outcome_evaluation_metrics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cases)
    valid = sum(bool(item.get("validation_valid")) for item in cases)
    abstained = sum(
        item.get("candidate_type") == AIOutcomeCandidateType.ABSTAIN.value for item in cases
    )
    reference = [item for item in cases if item.get("reference_type")]
    matched = sum(bool(item.get("reference_match")) for item in reference)
    unsupported = sum(
        any(
            str(category).startswith("UNSUPPORTED") for category in item.get("error_categories", [])
        )
        for item in cases
    )
    return {
        "case_count": total,
        "evidence_grounding_valid_count": valid,
        "evidence_grounding_rate": valid / total if total else None,
        "abstention_count": abstained,
        "abstention_rate": abstained / total if total else None,
        "reference_case_count": len(reference),
        "reference_agreement_count": matched,
        "reference_agreement_rate": matched / len(reference) if reference else None,
        "unsupported_conversion_count": unsupported,
        "high_risk_error_count": sum(
            bool(
                set(item.get("error_categories", []))
                & {
                    AIOutcomeErrorCategory.UNSUPPORTED_CONVERSION.value,
                    AIOutcomeErrorCategory.CALCULATION_ATTEMPT.value,
                    AIOutcomeErrorCategory.HALLUCINATED_COMPONENT.value,
                }
            )
            for item in cases
        ),
        "calibration": "descriptive_only; no threshold or automatic decision",
    }


def _mapping_errors(value: Any, input_data: dict[str, Any]) -> list[dict[str, str]]:
    if not isinstance(value, dict):
        return [{"code": "INVALID_MAPPING", "message": "mapping must be an object"}]
    allowed = {
        "reported_value",
        "reported_unit_id",
        "normalized_unit_id",
        "reported_time_value",
        "reported_time_unit",
        "reported_time_anchor",
        "timepoint_window_id",
        "measurement_scale_id",
        "direction_transformation",
        "transformation_reason",
    }
    errors = [
        {"code": "UNEXPECTED_MAPPING_PROPERTY", "message": key}
        for key in sorted(set(value) - allowed)
    ]
    extraction = input_data.get("extraction_value", {})
    reported_value = value.get("reported_value")
    expected_value = extraction.get("reported_value")
    if reported_value is not None and str(reported_value) != str(expected_value):
        errors.append(
            {
                "code": "REPORTED_VALUE_CHANGED",
                "message": "AI cannot change the reported extraction value",
            }
        )
    allowed_manifest = input_data.get("allowed_mappings", {})
    for field, key in (
        ("reported_unit_id", "allowed_unit_ids"),
        ("normalized_unit_id", "allowed_unit_ids"),
        ("timepoint_window_id", "allowed_timepoint_window_ids"),
        ("measurement_scale_id", "allowed_scale_ids"),
    ):
        candidate = value.get(field)
        if candidate is not None and str(candidate) not in {
            str(item) for item in allowed_manifest.get(key, [])
        }:
            errors.append({"code": "UNALLOWED_REFERENCE", "message": f"{field} is not permitted"})
    if value.get("reported_time_value") is not None:
        try:
            parsed = Decimal(str(value["reported_time_value"]))
            if not parsed.is_finite() or parsed < 0:
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            errors.append(
                {
                    "code": "INVALID_TIME_VALUE",
                    "message": "reported time must be finite and non-negative",
                }
            )
    if value.get("reported_time_unit") is not None and value.get(
        "reported_time_unit"
    ) not in allowed_manifest.get("allowed_time_units", []):
        errors.append(
            {"code": "INVALID_TIME_UNIT", "message": "reported time unit is not permitted"}
        )
    if value.get("reported_time_anchor") is not None and value.get(
        "reported_time_anchor"
    ) not in allowed_manifest.get("allowed_time_anchors", []):
        errors.append(
            {"code": "INVALID_TIME_ANCHOR", "message": "reported time anchor is not permitted"}
        )
    direction = value.get("direction_transformation", "NONE")
    if direction not in allowed_manifest.get("allowed_direction_transformations", []):
        errors.append(
            {
                "code": "INVALID_DIRECTION_TRANSFORMATION",
                "message": "direction transformation is not permitted",
            }
        )
    if direction == "SIGN_REVERSED" and not str(value.get("transformation_reason") or "").strip():
        errors.append(
            {"code": "TRANSFORMATION_REASON_REQUIRED", "message": "sign reversal requires a reason"}
        )
    return errors


def _effect_errors(value: Any, input_data: dict[str, Any]) -> list[dict[str, str]]:
    if not isinstance(value, dict):
        return [{"code": "INVALID_EFFECT", "message": "effect must be an object"}]
    allowed = {
        "effect_measure",
        "estimate",
        "standard_error",
        "variance",
        "variance_scale",
        "ci_lower",
        "ci_upper",
        "confidence_level",
        "adjustment",
        "analysis_population",
        "components",
    }
    errors = [
        {"code": "UNEXPECTED_EFFECT_PROPERTY", "message": key}
        for key in sorted(set(value) - allowed)
    ]
    measure = value.get("effect_measure")
    if measure not in input_data.get("outcome_definition", {}).get(
        "compatible_effect_measures", []
    ):
        errors.append(
            {
                "code": "INCOMPATIBLE_EFFECT_MEASURE",
                "message": "effect measure is not compatible with the outcome",
            }
        )
    if value.get("estimate") is None:
        errors.append(
            {"code": "ESTIMATE_REQUIRED", "message": "reported effect requires an estimate"}
        )
    for key in (
        "estimate",
        "standard_error",
        "variance",
        "ci_lower",
        "ci_upper",
        "confidence_level",
    ):
        if value.get(key) is not None:
            try:
                parsed = Decimal(str(value[key]))
                if not parsed.is_finite():
                    raise ValueError
                if key in {"standard_error", "variance"} and parsed < 0:
                    raise ValueError
            except (InvalidOperation, ValueError, TypeError):
                errors.append({"code": "INVALID_EFFECT_NUMBER", "message": key})
    if value.get("standard_error") is not None and value.get("variance") is not None:
        try:
            if abs(
                Decimal(str(value["standard_error"])) ** 2 - Decimal(str(value["variance"]))
            ) > Decimal("0.000000000001"):
                errors.append(
                    {
                        "code": "INCONSISTENT_VARIANCE",
                        "message": "standard error and variance disagree",
                    }
                )
        except (InvalidOperation, TypeError):
            pass
    if value.get("variance_scale") not in {"NATURAL", "LOG"}:
        errors.append(
            {
                "code": "INVALID_VARIANCE_SCALE",
                "message": "reported effect requires a variance scale",
            }
        )
    if (value.get("ci_lower") is None) != (value.get("ci_upper") is None):
        errors.append(
            {
                "code": "INCOMPLETE_CONFIDENCE_INTERVAL",
                "message": "both confidence interval bounds are required",
            }
        )
    if value.get("confidence_level") is not None:
        try:
            confidence_level = Decimal(str(value["confidence_level"]))
            if not confidence_level.is_finite() or not 0 < confidence_level <= 1:
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            errors.append(
                {
                    "code": "INVALID_CONFIDENCE_LEVEL",
                    "message": "confidence level must be between zero and one",
                }
            )
    if measure in {"RR", "OR", "HR"}:
        for key in ("estimate", "ci_lower", "ci_upper"):
            if value.get(key) is not None:
                try:
                    if Decimal(str(value[key])) <= 0:
                        raise ValueError
                except (InvalidOperation, ValueError, TypeError):
                    errors.append(
                        {"code": "INVALID_RATIO_VALUE", "message": f"{key} must be positive"}
                    )
    components = value.get("components")
    if components is not None and not isinstance(components, dict):
        errors.append(
            {"code": "INVALID_COMPONENTS", "message": "reported components must be an object"}
        )
    elif isinstance(components, dict):
        for key, component in components.items():
            try:
                parsed = Decimal(str(component))
                if not parsed.is_finite():
                    raise ValueError
            except (InvalidOperation, ValueError, TypeError):
                errors.append(
                    {"code": "INVALID_COMPONENT", "message": f"component {key} is not numeric"}
                )
    if value.get("adjustment") not in {None, "UNADJUSTED"}:
        errors.append({"code": "INVALID_ADJUSTMENT", "message": "adjustment is invalid"})
    if value.get("analysis_population") not in {
        None,
        "INTENTION_TO_TREAT",
        "PER_PROTOCOL",
        "MODIFIED_ITT",
        "SAFETY",
        "UNCLEAR",
        "OTHER",
    }:
        errors.append(
            {"code": "INVALID_ANALYSIS_POPULATION", "message": "analysis population is invalid"}
        )
    return errors


def _evidence_errors(evidence: list[Any], input_data: dict[str, Any]) -> list[dict[str, str]]:
    chunks = {
        str(item.get("chunk_id")): item
        for item in input_data.get("chunks", [])
        if isinstance(item, dict)
    }
    documents = {
        str(item.get("document_id")): item
        for item in input_data.get("source_documents", [])
        if isinstance(item, dict)
    }
    errors: list[dict[str, str]] = []
    for item in evidence:
        if not isinstance(item, dict):
            errors.append({"code": "INVALID_EVIDENCE", "message": "evidence must be an object"})
            continue
        document_id = str(item.get("document_id", ""))
        source = documents.get(document_id)
        chunk = chunks.get(str(item.get("chunk_id", "")))
        if source is None:
            errors.append({"code": "WRONG_DOCUMENT", "message": "evidence document is not pinned"})
        elif str(item.get("document_version_id", "")) != str(source.get("document_version_id", "")):
            errors.append(
                {
                    "code": "WRONG_DOCUMENT_VERSION",
                    "message": "evidence document version is not pinned",
                }
            )
        if chunk is None:
            errors.append(
                {
                    "code": "FABRICATED_CHUNK",
                    "message": "evidence chunk is not in the input snapshot",
                }
            )
            continue
        if str(chunk.get("document_id")) != document_id:
            errors.append({"code": "WRONG_DOCUMENT", "message": "chunk and document disagree"})
        if item.get("source_block_id") is not None and str(item.get("source_block_id")) != str(
            chunk.get("source_block_id")
        ):
            errors.append({"code": "WRONG_SOURCE_BLOCK", "message": "source block is not pinned"})
        if item.get("page") != chunk.get("page"):
            errors.append(
                {"code": "PAGE_MISMATCH", "message": "evidence page does not match chunk"}
            )
        if item.get("section") != chunk.get("section"):
            errors.append(
                {"code": "SECTION_MISMATCH", "message": "evidence section does not match chunk"}
            )
        quote = item.get("quote")
        text = str(chunk.get("text", ""))
        if not isinstance(quote, str) or not quote.strip() or len(quote) > 500:
            errors.append(
                {"code": "INVALID_QUOTE", "message": "evidence quote is missing or too long"}
            )
        elif normalize_evidence_text(quote) not in normalize_evidence_text(text):
            errors.append(
                {"code": "QUOTE_MISMATCH", "message": "evidence quote is not in the pinned chunk"}
            )
    return errors
