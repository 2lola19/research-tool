from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from enum import StrEnum
from typing import Any
from uuid import UUID

CALCULATION_VERSION = "effect-foundation-1"
HARMONIZATION_VERSION = "outcome-harmonization-1"
READINESS_VERSION = "analysis-readiness-1"
PERSISTED_QUANTUM = Decimal("0.000000000001")


class OutcomeType(StrEnum):
    DICHOTOMOUS = "DICHOTOMOUS"
    CONTINUOUS = "CONTINUOUS"
    TIME_TO_EVENT = "TIME_TO_EVENT"
    COUNT = "COUNT"
    PROPORTION = "PROPORTION"
    RATE = "RATE"
    DIAGNOSTIC = "DIAGNOSTIC"
    ORDINAL = "ORDINAL"


class Directionality(StrEnum):
    HIGHER_BETTER = "HIGHER_BETTER"
    HIGHER_WORSE = "HIGHER_WORSE"
    NEUTRAL = "NEUTRAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class OutcomeRole(StrEnum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    OTHER = "OTHER"


class MappingMethod(StrEnum):
    MANUAL = "MANUAL"
    DETERMINISTIC_RULE = "DETERMINISTIC_RULE"
    IMPORTED = "IMPORTED"


class TimeUnit(StrEnum):
    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"
    YEAR = "YEAR"


class TimeAnchor(StrEnum):
    BASELINE = "BASELINE"
    RANDOMIZATION = "RANDOMIZATION"
    INTERVENTION_START = "INTERVENTION_START"
    DIAGNOSIS = "DIAGNOSIS"
    OTHER = "OTHER"


class DirectionTransformation(StrEnum):
    NONE = "NONE"
    SIGN_REVERSED = "SIGN_REVERSED"


class EffectMeasure(StrEnum):
    RR = "RR"
    OR = "OR"
    RD = "RD"
    MD = "MD"
    SMD = "SMD"
    HR = "HR"
    PROPORTION = "PROPORTION"
    MEAN = "MEAN"
    RATE = "RATE"


class EstimateOrigin(StrEnum):
    REPORTED = "REPORTED"
    DERIVED = "DERIVED"


class AdjustmentStatus(StrEnum):
    UNADJUSTED = "UNADJUSTED"
    ADJUSTED = "ADJUSTED"


class AnalysisPopulation(StrEnum):
    INTENTION_TO_TREAT = "INTENTION_TO_TREAT"
    PER_PROTOCOL = "PER_PROTOCOL"
    MODIFIED_ITT = "MODIFIED_ITT"
    SAFETY = "SAFETY"
    UNCLEAR = "UNCLEAR"
    OTHER = "OTHER"


class ZeroEventPattern(StrEnum):
    NONE = "NONE"
    INTERVENTION_ONLY = "INTERVENTION_ONLY"
    COMPARATOR_ONLY = "COMPARATOR_ONLY"
    DOUBLE_ZERO = "DOUBLE_ZERO"
    BOUNDARY_CELL = "BOUNDARY_CELL"


class VarianceScale(StrEnum):
    NATURAL = "NATURAL"
    LOG = "LOG"


class ReadinessStatus(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    NEEDS_HARMONIZATION = "NEEDS_HARMONIZATION"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ReadinessBlocker(StrEnum):
    OUTCOME_NOT_MAPPED = "OUTCOME_NOT_MAPPED"
    OUTCOME_VERSION_MISMATCH = "OUTCOME_VERSION_MISMATCH"
    TIMEPOINT_NOT_MAPPED = "TIMEPOINT_NOT_MAPPED"
    TIMEPOINT_MISMATCH = "TIMEPOINT_MISMATCH"
    UNIT_NOT_HARMONIZED = "UNIT_NOT_HARMONIZED"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    EFFECT_MEASURE_INCOMPATIBLE = "EFFECT_MEASURE_INCOMPATIBLE"
    SCALE_DIRECTION_UNKNOWN = "SCALE_DIRECTION_UNKNOWN"
    SCALE_MISMATCH = "SCALE_MISMATCH"
    SAMPLE_SIZE_MISSING = "SAMPLE_SIZE_MISSING"
    VARIANCE_MISSING = "VARIANCE_MISSING"
    ADJUSTMENT_MISMATCH = "ADJUSTMENT_MISMATCH"
    DUPLICATE_STUDY_ESTIMATE = "DUPLICATE_STUDY_ESTIMATE"
    ZERO_EVENT_POLICY_REQUIRED = "ZERO_EVENT_POLICY_REQUIRED"
    ANALYSIS_POPULATION_MISMATCH = "ANALYSIS_POPULATION_MISMATCH"
    UNVERIFIED_EXTRACTION = "UNVERIFIED_EXTRACTION"


@dataclass(frozen=True, slots=True)
class OutcomeDefinition:
    id: UUID
    organization_id: UUID
    review_id: UUID
    key: str
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OutcomeDefinitionVersion:
    id: UUID
    outcome_id: UUID
    organization_id: UUID
    review_id: UUID
    version: int
    definition: dict[str, Any]
    content_hash: str
    protocol_version_id: UUID | None
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TimepointWindow:
    id: UUID
    organization_id: UUID
    review_id: UUID
    key: str
    label: str
    anchor: TimeAnchor
    minimum_days: str | None
    maximum_days: str | None
    rule_version: str
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class UnitDefinition:
    id: UUID
    organization_id: UUID
    review_id: UUID
    key: str
    label: str
    dimension: str
    context_key: str
    base_unit_key: str
    multiplier_to_base: str
    offset_to_base: str
    precision: int
    rule_version: str
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MeasurementScale:
    id: UUID
    organization_id: UUID
    review_id: UUID
    key: str
    name: str
    minimum: str | None
    maximum: str | None
    directionality: Directionality
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class OutcomeMapping:
    id: UUID
    organization_id: UUID
    review_id: UUID
    study_id: UUID
    extraction_value_id: UUID
    outcome_version_id: UUID
    method: MappingMethod
    rationale: str
    confidence: str | None
    reported_value: str | None
    reported_unit: str | None
    reported_unit_id: UUID | None
    normalized_value: str | None
    normalized_unit_id: UUID | None
    conversion_rule_version: str | None
    reported_time_value: str | None
    reported_time_unit: TimeUnit | None
    reported_time_anchor: TimeAnchor | None
    normalized_time_days: str | None
    timepoint_window_id: UUID | None
    timepoint_rule_version: str | None
    measurement_scale_id: UUID | None
    direction_transformation: DirectionTransformation
    transformation_reason: str | None
    extraction_verified: bool
    supersedes_mapping_id: UUID | None
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class EffectEstimate:
    id: UUID
    organization_id: UUID
    review_id: UUID
    study_id: UUID
    outcome_version_id: UUID
    effect_measure: EffectMeasure
    origin: EstimateOrigin
    estimate: str | None
    standard_error: str | None
    variance: str | None
    variance_scale: VarianceScale
    ci_lower: str | None
    ci_upper: str | None
    confidence_level: str | None
    adjustment: AdjustmentStatus
    analysis_population: AnalysisPopulation
    covariates: str | None
    model_description: str | None
    timepoint_window_id: UUID | None
    unit_id: UUID | None
    measurement_scale_id: UUID | None
    components: dict[str, str]
    source_mapping_ids: tuple[UUID, ...]
    source_evidence_location_id: UUID | None
    calculation_version: str | None
    zero_event_pattern: ZeroEventPattern
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SynthesisCandidateSet:
    id: UUID
    organization_id: UUID
    review_id: UUID
    outcome_version_id: UUID
    effect_measure: EffectMeasure
    timepoint_window_id: UUID | None
    population_label: str | None
    estimate_ids: tuple[UUID, ...]
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AnalysisReadinessSnapshot:
    id: UUID
    organization_id: UUID
    review_id: UUID
    candidate_set_id: UUID
    algorithm_version: str
    status: ReadinessStatus
    blockers: tuple[dict[str, Any], ...]
    evaluated_by_user_id: UUID
    created_at: datetime


def normalize_outcome_definition(definition: dict[str, Any]) -> dict[str, Any]:
    name = _required(definition.get("name"), "outcome name")
    outcome_type = OutcomeType(_key(definition.get("outcome_type"), "outcome type"))
    direction = Directionality(_key(definition.get("directionality"), "directionality"))
    role = OutcomeRole(_key(definition.get("role", OutcomeRole.OTHER), "outcome role"))
    measures = _unique_enum_values(
        definition.get("compatible_effect_measures"), EffectMeasure, "effect measures"
    )
    if not measures:
        raise ValueError("outcome requires compatible effect measures")
    return {
        "name": name,
        "description": _optional(definition.get("description")),
        "category": _optional(definition.get("category")),
        "outcome_type": outcome_type.value,
        "directionality": direction.value,
        "role": role.value,
        "measurement_concept": _optional(definition.get("measurement_concept")),
        "compatible_effect_measures": measures,
        "allowed_unit_ids": _unique_uuid_strings(definition.get("allowed_unit_ids", [])),
        "allowed_scale_ids": _unique_uuid_strings(definition.get("allowed_scale_ids", [])),
        "expected_timepoint_window_ids": _unique_uuid_strings(
            definition.get("expected_timepoint_window_ids", [])
        ),
    }


def normalize_time_to_days(value: Decimal, unit: TimeUnit) -> Decimal:
    if value < 0:
        raise ValueError("timepoint cannot be negative")
    factors = {
        TimeUnit.DAY: Decimal("1"),
        TimeUnit.WEEK: Decimal("7"),
    }
    if unit not in factors:
        raise ValueError(
            "calendar time units require an explicit review-specific normalization rule"
        )
    return _persist(value * factors[unit])


def convert_unit(value: Decimal, source: UnitDefinition, target: UnitDefinition) -> Decimal:
    if (source.dimension, source.context_key, source.base_unit_key) != (
        target.dimension,
        target.context_key,
        target.base_unit_key,
    ):
        raise ValueError("units do not share a scientifically valid conversion context")
    with localcontext() as context:
        context.prec = 50
        base = value * Decimal(source.multiplier_to_base) + Decimal(source.offset_to_base)
        converted = (base - Decimal(target.offset_to_base)) / Decimal(target.multiplier_to_base)
    quantum = Decimal(1).scaleb(-target.precision)
    return converted.quantize(quantum, rounding=ROUND_HALF_EVEN)


def apply_direction(value: Decimal, transformation: DirectionTransformation) -> Decimal:
    return -value if transformation == DirectionTransformation.SIGN_REVERSED else value


def derive_effect(
    measure: EffectMeasure, components: dict[str, Decimal]
) -> tuple[Decimal | None, Decimal | None, Decimal | None, ZeroEventPattern]:
    required = {
        EffectMeasure.RR: {
            "events_intervention",
            "sample_intervention",
            "events_comparator",
            "sample_comparator",
        },
        EffectMeasure.OR: {
            "events_intervention",
            "sample_intervention",
            "events_comparator",
            "sample_comparator",
        },
        EffectMeasure.RD: {
            "events_intervention",
            "sample_intervention",
            "events_comparator",
            "sample_comparator",
        },
        EffectMeasure.MD: {"mean_intervention", "mean_comparator"},
    }
    if measure not in required:
        raise ValueError("deterministic derivation is not implemented for this effect measure")
    missing = required[measure] - components.keys()
    if missing:
        raise ValueError(f"missing effect components: {', '.join(sorted(missing))}")
    with localcontext() as context:
        context.prec = 50
        if measure == EffectMeasure.MD:
            estimate = components["mean_intervention"] - components["mean_comparator"]
            variance = _mean_difference_variance(components)
            return (
                _persist(estimate),
                _sqrt_or_none(variance),
                _persist_or_none(variance),
                ZeroEventPattern.NONE,
            )
        a = components["events_intervention"]
        n1 = components["sample_intervention"]
        c = components["events_comparator"]
        n0 = components["sample_comparator"]
        _validate_binary_counts(a, n1, c, n0)
        zero_pattern = _zero_pattern(a, c)
        p1, p0 = a / n1, c / n0
        if measure == EffectMeasure.RD:
            variance = p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0
            return _persist(p1 - p0), _sqrt_or_none(variance), _persist(variance), zero_pattern
        if zero_pattern != ZeroEventPattern.NONE:
            return None, None, None, zero_pattern
        if measure == EffectMeasure.RR:
            variance = 1 / a - 1 / n1 + 1 / c - 1 / n0
            return _persist(p1 / p0), _sqrt_or_none(variance), _persist(variance), zero_pattern
        if a == n1 or c == n0:
            return None, None, None, ZeroEventPattern.BOUNDARY_CELL
        odds1, odds0 = a / (n1 - a), c / (n0 - c)
        variance = 1 / a + 1 / (n1 - a) + 1 / c + 1 / (n0 - c)
        return _persist(odds1 / odds0), _sqrt_or_none(variance), _persist(variance), zero_pattern


def readiness_blockers(
    candidate: SynthesisCandidateSet,
    outcome: OutcomeDefinitionVersion,
    estimates: list[EffectEstimate],
    mappings: dict[UUID, OutcomeMapping],
    scales: dict[UUID, MeasurementScale],
) -> tuple[dict[str, Any], ...]:
    blockers: list[dict[str, Any]] = []

    def add(code: ReadinessBlocker, **details: Any) -> None:
        blockers.append({"code": code.value, **details})

    compatible = set(outcome.definition["compatible_effect_measures"])
    if candidate.effect_measure.value not in compatible:
        add(ReadinessBlocker.EFFECT_MEASURE_INCOMPATIBLE)
    if not estimates:
        add(ReadinessBlocker.OUTCOME_NOT_MAPPED)
    studies: dict[UUID, int] = {}
    adjustments: set[AdjustmentStatus] = set()
    populations: set[AnalysisPopulation] = set()
    units: set[UUID | None] = set()
    scale_ids: set[UUID | None] = set()
    for estimate in sorted(estimates, key=lambda item: str(item.id)):
        details = {"estimate_id": str(estimate.id), "study_id": str(estimate.study_id)}
        studies[estimate.study_id] = studies.get(estimate.study_id, 0) + 1
        adjustments.add(estimate.adjustment)
        populations.add(estimate.analysis_population)
        units.add(estimate.unit_id)
        scale_ids.add(estimate.measurement_scale_id)
        if estimate.outcome_version_id != candidate.outcome_version_id:
            add(ReadinessBlocker.OUTCOME_VERSION_MISMATCH, **details)
        if estimate.effect_measure != candidate.effect_measure:
            add(ReadinessBlocker.EFFECT_MEASURE_INCOMPATIBLE, **details)
        if estimate.timepoint_window_id is None:
            add(ReadinessBlocker.TIMEPOINT_NOT_MAPPED, **details)
        elif estimate.timepoint_window_id != candidate.timepoint_window_id:
            add(ReadinessBlocker.TIMEPOINT_MISMATCH, **details)
        if estimate.variance is None and estimate.standard_error is None:
            add(ReadinessBlocker.VARIANCE_MISSING, **details)
        sample_keys = {"sample_intervention", "sample_comparator"}
        if (
            estimate.origin == EstimateOrigin.DERIVED
            and estimate.effect_measure
            in (
                EffectMeasure.RR,
                EffectMeasure.OR,
                EffectMeasure.RD,
                EffectMeasure.MD,
            )
            and not sample_keys <= estimate.components.keys()
        ):
            add(ReadinessBlocker.SAMPLE_SIZE_MISSING, **details)
        if estimate.zero_event_pattern != ZeroEventPattern.NONE and estimate.effect_measure in (
            EffectMeasure.RR,
            EffectMeasure.OR,
        ):
            add(ReadinessBlocker.ZERO_EVENT_POLICY_REQUIRED, **details)
        source_mappings = [mappings.get(item) for item in estimate.source_mapping_ids]
        if not source_mappings or any(
            item is None or not item.extraction_verified for item in source_mappings
        ):
            add(ReadinessBlocker.UNVERIFIED_EXTRACTION, **details)
        if (
            estimate.effect_measure in (EffectMeasure.MD, EffectMeasure.MEAN)
            and estimate.unit_id is None
        ):
            add(ReadinessBlocker.UNIT_NOT_HARMONIZED, **details)
        if estimate.effect_measure in (EffectMeasure.MD, EffectMeasure.SMD, EffectMeasure.MEAN):
            scale = (
                scales.get(estimate.measurement_scale_id) if estimate.measurement_scale_id else None
            )
            if scale is not None and scale.directionality == Directionality.UNKNOWN:
                add(ReadinessBlocker.SCALE_DIRECTION_UNKNOWN, **details)
    for study_id, count in sorted(studies.items(), key=lambda item: str(item[0])):
        if count > 1:
            add(ReadinessBlocker.DUPLICATE_STUDY_ESTIMATE, study_id=str(study_id), count=count)
    if len(adjustments) > 1:
        add(ReadinessBlocker.ADJUSTMENT_MISMATCH)
    if len(populations) > 1:
        add(ReadinessBlocker.ANALYSIS_POPULATION_MISMATCH)
    if len({item for item in units if item is not None}) > 1:
        add(ReadinessBlocker.UNIT_MISMATCH)
    if len({item for item in scale_ids if item is not None}) > 1:
        add(ReadinessBlocker.SCALE_MISMATCH)
    if (
        candidate.effect_measure in (EffectMeasure.MD, EffectMeasure.SMD, EffectMeasure.MEAN)
        and outcome.definition.get("directionality") == Directionality.UNKNOWN.value
    ):
        add(ReadinessBlocker.SCALE_DIRECTION_UNKNOWN)
    return tuple(
        sorted(
            blockers,
            key=lambda item: (item["code"], item.get("study_id", ""), item.get("estimate_id", "")),
        )
    )


def readiness_status(blockers: tuple[dict[str, Any], ...]) -> ReadinessStatus:
    if not blockers:
        return ReadinessStatus.READY
    codes = {item["code"] for item in blockers}
    harmonization = {
        ReadinessBlocker.OUTCOME_VERSION_MISMATCH.value,
        ReadinessBlocker.TIMEPOINT_NOT_MAPPED.value,
        ReadinessBlocker.TIMEPOINT_MISMATCH.value,
        ReadinessBlocker.UNIT_NOT_HARMONIZED.value,
        ReadinessBlocker.UNIT_MISMATCH.value,
        ReadinessBlocker.SCALE_DIRECTION_UNKNOWN.value,
        ReadinessBlocker.SCALE_MISMATCH.value,
    }
    review = {
        ReadinessBlocker.ADJUSTMENT_MISMATCH.value,
        ReadinessBlocker.ANALYSIS_POPULATION_MISMATCH.value,
    }
    hard = codes - harmonization - review
    if hard:
        return ReadinessStatus.NOT_READY
    if codes & harmonization:
        return ReadinessStatus.NEEDS_HARMONIZATION
    return ReadinessStatus.NEEDS_REVIEW


def _mean_difference_variance(components: dict[str, Decimal]) -> Decimal | None:
    optional = {"sd_intervention", "sample_intervention", "sd_comparator", "sample_comparator"}
    if not optional <= components.keys():
        return None
    n1, n0 = components["sample_intervention"], components["sample_comparator"]
    if n1 <= 0 or n0 <= 0:
        raise ValueError("sample sizes must be positive")
    if components["sd_intervention"] < 0 or components["sd_comparator"] < 0:
        raise ValueError("standard deviations cannot be negative")
    return components["sd_intervention"] ** 2 / n1 + components["sd_comparator"] ** 2 / n0


def _validate_binary_counts(a: Decimal, n1: Decimal, c: Decimal, n0: Decimal) -> None:
    if n1 <= 0 or n0 <= 0:
        raise ValueError("sample sizes must be positive")
    if any(value != value.to_integral_value() for value in (a, n1, c, n0)):
        raise ValueError("events and sample sizes must be whole numbers")
    if a < 0 or c < 0 or a > n1 or c > n0:
        raise ValueError("event counts must be between zero and sample size")


def _zero_pattern(a: Decimal, c: Decimal) -> ZeroEventPattern:
    if a == 0 and c == 0:
        return ZeroEventPattern.DOUBLE_ZERO
    if a == 0:
        return ZeroEventPattern.INTERVENTION_ONLY
    if c == 0:
        return ZeroEventPattern.COMPARATOR_ONLY
    return ZeroEventPattern.NONE


def _sqrt_or_none(value: Decimal | None) -> Decimal | None:
    return _persist(value.sqrt()) if value is not None else None


def _persist_or_none(value: Decimal | None) -> Decimal | None:
    return _persist(value) if value is not None else None


def _persist(value: Decimal) -> Decimal:
    return value.quantize(PERSISTED_QUANTUM, rounding=ROUND_HALF_EVEN)


def _unique_enum_values(value: Any, enum: type[StrEnum], label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    result = [enum(_key(item, label)).value for item in value]
    if len(result) != len(set(result)):
        raise ValueError(f"{label} must be unique")
    return result


def _unique_uuid_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("scientific configuration identifiers must be a list")
    result = [str(UUID(str(item))) for item in value]
    if len(result) != len(set(result)):
        raise ValueError("scientific configuration identifiers must be unique")
    return result


def _key(value: Any, label: str) -> str:
    result = str(value or "").strip().upper()
    if (
        not result
        or len(result) > 120
        or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in result)
    ):
        raise ValueError(f"{label} is invalid")
    return result


def _required(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{label} is required")
    return result


def _optional(value: Any) -> str | None:
    result = str(value or "").strip()
    return result or None
