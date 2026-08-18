from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.app.ai.extraction_domain import (
    AIExtractionFieldStatus,
    AIExtractionMatchClass,
)
from backend.app.ai.full_text_domain import normalize_evidence_text
from backend.app.extraction.domain import ExtractionFieldType, MissingnessState


def evaluate_field(
    *,
    prediction: dict[str, Any] | None,
    validation: dict[str, Any] | None,
    reference_missingness: str,
    reference_value: Any,
    field_type: str,
    absolute_tolerance: float | None,
) -> dict[str, Any]:
    evidence_valid = bool(validation and validation.get("valid"))
    if prediction is None:
        return _result(AIExtractionMatchClass.INVALID_PROPOSAL, False)
    try:
        status = AIExtractionFieldStatus(str(prediction.get("status")))
    except ValueError:
        return _result(AIExtractionMatchClass.INVALID_PROPOSAL, False)
    if status is AIExtractionFieldStatus.ABSTAIN:
        return _result(AIExtractionMatchClass.AI_ABSTAIN, evidence_valid)
    predicts_value = status is AIExtractionFieldStatus.PROPOSED_VALUE
    reference_has_value = reference_missingness == MissingnessState.VALUE_REPORTED.value
    if predicts_value and not evidence_valid:
        return _result(AIExtractionMatchClass.EVIDENCE_INVALID, False)
    if predicts_value and not reference_has_value:
        return _result(AIExtractionMatchClass.AI_VALUE_REFERENCE_MISSING, evidence_valid)
    if not predicts_value and reference_has_value:
        return _result(AIExtractionMatchClass.AI_MISSING_REFERENCE_VALUE, evidence_valid)
    if not predicts_value:
        expected = _status_for_missingness(reference_missingness)
        classification = (
            AIExtractionMatchClass.EXACT_MATCH
            if status.value == expected
            else AIExtractionMatchClass.MISMATCH
        )
        return _result(classification, evidence_valid)

    ai_value = prediction.get("value")
    exact = ai_value == reference_value and type(ai_value) is type(reference_value)
    if exact:
        return _result(AIExtractionMatchClass.EXACT_MATCH, evidence_valid)
    field_kind = ExtractionFieldType(field_type)
    if field_kind is ExtractionFieldType.DECIMAL:
        try:
            ai_number = Decimal(str(ai_value))
            reference_number = Decimal(str(reference_value))
            error = abs(ai_number - reference_number)
            relative = error / abs(reference_number) if reference_number != Decimal("0") else None
            if error == Decimal("0"):
                return _result(
                    AIExtractionMatchClass.NORMALIZED_MATCH,
                    evidence_valid,
                    absolute_error=0.0,
                    relative_error=0.0,
                )
            if absolute_tolerance is not None and error <= Decimal(str(absolute_tolerance)):
                return _result(
                    AIExtractionMatchClass.ACCEPTABLE_WITH_TOLERANCE,
                    evidence_valid,
                    absolute_error=float(error),
                    relative_error=float(relative) if relative is not None else None,
                )
            return _result(
                AIExtractionMatchClass.MISMATCH,
                evidence_valid,
                absolute_error=float(error),
                relative_error=float(relative) if relative is not None else None,
            )
        except (InvalidOperation, TypeError, ValueError):
            pass
    if (
        field_kind in {ExtractionFieldType.TEXT, ExtractionFieldType.CITATION}
        and isinstance(ai_value, str)
        and normalize_evidence_text(ai_value).casefold()
        == normalize_evidence_text(str(reference_value)).casefold()
    ):
        return _result(AIExtractionMatchClass.NORMALIZED_MATCH, evidence_valid)
    return _result(AIExtractionMatchClass.MISMATCH, evidence_valid)


def aggregate_metrics(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    classes = Counter(str(item["classification"]) for item in case_results)
    field_types: dict[str, Counter[str]] = defaultdict(Counter)
    options: dict[str, Counter[str]] = defaultdict(Counter)
    for item in case_results:
        field_types[str(item["field_type"])][str(item["classification"])] += 1
        if item.get("field_type") in {"CATEGORICAL", "ENUM"}:
            key = f"{item.get('reference_value')}->{item.get('ai_value')}"
            options[str(item["field_key"])][key] += 1
    non_missing = sum(item.get("ai_status") == "PROPOSED_VALUE" for item in case_results)
    evidence_valid = sum(
        item.get("ai_status") == "PROPOSED_VALUE" and bool(item.get("evidence_valid"))
        for item in case_results
    )
    grounding_errors = Counter(
        error
        for item in case_results
        for error in item.get("validation_errors", [])
        if error
        in {
            "INVALID_CHUNK_REFERENCE",
            "QUOTE_MISMATCH",
            "WRONG_DOCUMENT",
            "WRONG_DOCUMENT_VERSION",
            "PAGE_MISMATCH",
            "SECTION_MISMATCH",
            "TABLE_MISMATCH",
            "VALUE_NOT_SUPPORTED_BY_QUOTE",
            "REPORTED_VALUE_NOT_SUPPORTED_BY_QUOTE",
        }
    )
    missingness = _missingness_metrics(case_results)
    source_locations = Counter(
        _source_location(item.get("source_location")) for item in case_results
    )
    return {
        "metric_version": "ai-extraction-evaluation-1",
        "requested_fields": len(case_results),
        "classifications": dict(sorted(classes.items())),
        "non_missing_proposed_fields": non_missing,
        "fields_with_valid_evidence": evidence_valid,
        "grounding_valid_rate": evidence_valid / non_missing if non_missing else None,
        "hallucination_count": classes[AIExtractionMatchClass.AI_VALUE_REFERENCE_MISSING.value],
        "evidence_invalid_count": classes[AIExtractionMatchClass.EVIDENCE_INVALID.value],
        "abstention_count": classes[AIExtractionMatchClass.AI_ABSTAIN.value],
        "missingness": missingness,
        "grounding_error_counts": dict(sorted(grounding_errors.items())),
        "document_location_breakdown": dict(sorted(source_locations.items())),
        "fields_with_missingness_result": sum(
            item.get("ai_status") not in {None, AIExtractionFieldStatus.PROPOSED_VALUE.value}
            for item in case_results
        ),
        "human_review_workload_remaining": len(case_results),
        "valid_proposal_coverage": sum(
            item["classification"]
            not in {
                AIExtractionMatchClass.INVALID_PROPOSAL.value,
                AIExtractionMatchClass.EVIDENCE_INVALID.value,
            }
            for item in case_results
        )
        / len(case_results)
        if case_results
        else None,
        "field_type_breakdown": {
            key: dict(sorted(value.items())) for key, value in sorted(field_types.items())
        },
        "categorical_confusion": {
            key: dict(sorted(value.items())) for key, value in sorted(options.items())
        },
        "categorical_exact_accuracy": _categorical_accuracy(case_results),
        "numeric_error_summary": _numeric_error_summary(case_results),
        "calibration_bins": _calibration(case_results),
        "threshold_simulations": _thresholds(case_results),
        "threshold_label": "HYPOTHETICAL EVALUATION ONLY",
    }


def _missingness_metrics(case_results: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "correct_not_reported": sum(
            item.get("reference_missingness") == MissingnessState.NOT_REPORTED.value
            and item.get("ai_status") == AIExtractionFieldStatus.NOT_REPORTED.value
            for item in case_results
        ),
        "false_reported_value": sum(
            item.get("classification") == AIExtractionMatchClass.AI_VALUE_REFERENCE_MISSING.value
            for item in case_results
        ),
        "falsely_missing": sum(
            item.get("classification") == AIExtractionMatchClass.AI_MISSING_REFERENCE_VALUE.value
            for item in case_results
        ),
        "unclear": sum(
            item.get("ai_status") == AIExtractionFieldStatus.UNCLEAR.value for item in case_results
        ),
        "requires_supplement": sum(
            item.get("ai_status") == AIExtractionFieldStatus.REQUIRES_SUPPLEMENT.value
            for item in case_results
        ),
        "requires_table_or_figure": sum(
            item.get("ai_status") == AIExtractionFieldStatus.REQUIRES_TABLE_OR_FIGURE.value
            for item in case_results
        ),
        "conflicting_source_values": sum(
            item.get("ai_status") == AIExtractionFieldStatus.CONFLICTING_SOURCE_VALUES.value
            for item in case_results
        ),
    }


def _source_location(value: Any) -> str:
    if not isinstance(value, dict):
        return "unknown"
    role = str(value.get("document_role") or "")
    if role == "SUPPLEMENT":
        return "supplement"
    if role == "APPENDIX":
        return "appendix"
    if value.get("table_id"):
        return "table"
    section = str(value.get("section") or "").casefold()
    for label in ("abstract", "methods", "participants", "results", "appendix", "supplement"):
        if label in section:
            return label
    return "other" if section else "unknown"


def _categorical_accuracy(case_results: list[dict[str, Any]]) -> float | None:
    items = [item for item in case_results if item.get("field_type") in {"CATEGORICAL", "ENUM"}]
    if not items:
        return None
    correct = sum(
        1
        for item in items
        if item.get("classification") == AIExtractionMatchClass.EXACT_MATCH.value
    )
    return correct / len(items)


def _numeric_error_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    errors = [
        float(item["absolute_error"])
        for item in case_results
        if item.get("absolute_error") is not None
    ]
    relatives = [
        float(item["relative_error"])
        for item in case_results
        if item.get("relative_error") is not None
    ]
    return {
        "count": len(errors),
        "maximum_absolute_error": max(errors) if errors else None,
        "mean_absolute_error": sum(errors) / len(errors) if errors else None,
        "maximum_relative_error": max(relatives) if relatives else None,
    }


def _result(
    classification: AIExtractionMatchClass,
    evidence_valid: bool,
    *,
    absolute_error: float | None = None,
    relative_error: float | None = None,
) -> dict[str, Any]:
    return {
        "classification": classification.value,
        "evidence_valid": evidence_valid,
        "absolute_error": absolute_error,
        "relative_error": relative_error,
    }


def _status_for_missingness(missingness: str) -> str:
    return {
        MissingnessState.NOT_REPORTED.value: AIExtractionFieldStatus.NOT_REPORTED.value,
        MissingnessState.NOT_APPLICABLE.value: AIExtractionFieldStatus.NOT_APPLICABLE.value,
        MissingnessState.UNCLEAR.value: AIExtractionFieldStatus.UNCLEAR.value,
        MissingnessState.NEEDS_REVIEW.value: AIExtractionFieldStatus.UNCLEAR.value,
    }.get(missingness, AIExtractionFieldStatus.ABSTAIN.value)


def _calibration(case_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bins: list[dict[str, Any]] = []
    for lower in (0.0, 0.2, 0.4, 0.6, 0.8):
        items = [
            item
            for item in case_results
            if item.get("confidence") is not None
            and lower <= float(item["confidence"]) <= lower + 0.2
        ]
        correct = sum(
            item["classification"]
            in {
                AIExtractionMatchClass.EXACT_MATCH.value,
                AIExtractionMatchClass.NORMALIZED_MATCH.value,
                AIExtractionMatchClass.ACCEPTABLE_WITH_TOLERANCE.value,
            }
            for item in items
        )
        bins.append(
            {
                "lower": lower,
                "upper": lower + 0.2,
                "count": len(items),
                "correct": correct,
                "hallucinated": sum(
                    item["classification"]
                    == AIExtractionMatchClass.AI_VALUE_REFERENCE_MISSING.value
                    for item in items
                ),
                "evidence_invalid": sum(
                    item["classification"] == AIExtractionMatchClass.EVIDENCE_INVALID.value
                    for item in items
                ),
            }
        )
    return bins


def _thresholds(case_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    simulations: list[dict[str, Any]] = []
    correct_classes = {
        AIExtractionMatchClass.EXACT_MATCH.value,
        AIExtractionMatchClass.NORMALIZED_MATCH.value,
        AIExtractionMatchClass.ACCEPTABLE_WITH_TOLERANCE.value,
    }
    for threshold in (0.5, 0.7, 0.8, 0.9, 0.95):
        accepted = [
            item
            for item in case_results
            if item.get("confidence") is not None
            and float(item["confidence"]) >= threshold
            and item.get("ai_status") == AIExtractionFieldStatus.PROPOSED_VALUE.value
        ]
        errors = sum(item["classification"] not in correct_classes for item in accepted)
        simulations.append(
            {
                "threshold": threshold,
                "hypothetically_accepted": len(accepted),
                "correct": len(accepted) - errors,
                "incorrect": errors,
                "hallucinated": sum(
                    item["classification"]
                    == AIExtractionMatchClass.AI_VALUE_REFERENCE_MISSING.value
                    for item in accepted
                ),
                "evidence_invalid": sum(
                    item["classification"] == AIExtractionMatchClass.EVIDENCE_INVALID.value
                    for item in accepted
                ),
                "human_review_avoided": len(accepted),
                "human_review_retained": len(case_results) - len(accepted),
                "observation_label": (
                    "ZERO OBSERVED ERRORS ON THIS EVALUATION DATASET" if errors == 0 else None
                ),
            }
        )
    return simulations
