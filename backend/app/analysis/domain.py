from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum
from statistics import NormalDist
from typing import Any
from uuid import UUID

from backend.app.outcomes.domain import AnalysisPopulation, EffectMeasure

ALGORITHM_NAME = "native-inverse-variance"
ALGORITHM_VERSION = "meta-analysis-1"
FOREST_RENDERER_VERSION = "forest-svg-1"
PERSISTED_QUANTUM = Decimal("0.000000000001")


class StatisticalModel(StrEnum):
    FIXED_EFFECT = "FIXED_EFFECT"
    RANDOM_EFFECTS = "RANDOM_EFFECTS"


class HeterogeneityEstimator(StrEnum):
    NONE = "NONE"
    DERSIMONIAN_LAIRD = "DERSIMONIAN_LAIRD"


class ConfidenceIntervalMethod(StrEnum):
    NORMAL = "NORMAL"


class EffectTransformation(StrEnum):
    IDENTITY = "IDENTITY"
    LOG = "LOG"


class ZeroEventPolicy(StrEnum):
    BLOCK = "BLOCK"
    EXCLUDE_DOUBLE_ZERO = "EXCLUDE_DOUBLE_ZERO"


class MissingVariancePolicy(StrEnum):
    BLOCK = "BLOCK"


class AdjustmentPolicy(StrEnum):
    UNADJUSTED_ONLY = "UNADJUSTED_ONLY"
    ADJUSTED_ONLY = "ADJUSTED_ONLY"
    EITHER_EXPLICIT_SELECTION = "EITHER_EXPLICIT_SELECTION"


class EstimateSelectionPolicy(StrEnum):
    EXPLICIT_ESTIMATE_IDS = "EXPLICIT_ESTIMATE_IDS"


class DependencyPolicy(StrEnum):
    BLOCK = "BLOCK"


class RunStatus(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DiagnosticLevel(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


class DiagnosticCode(StrEnum):
    TOO_FEW_STUDIES = "TOO_FEW_STUDIES"
    NON_POSITIVE_VARIANCE = "NON_POSITIVE_VARIANCE"
    EXTREME_WEIGHT_DOMINANCE = "EXTREME_WEIGHT_DOMINANCE"
    ZERO_EVENT_STUDY = "ZERO_EVENT_STUDY"
    DOUBLE_ZERO_STUDY = "DOUBLE_ZERO_STUDY"
    MULTI_ARM_DEPENDENCY = "MULTI_ARM_DEPENDENCY"
    CLUSTER_ADJUSTMENT_REQUIRED = "CLUSTER_ADJUSTMENT_REQUIRED"
    CROSSOVER_VARIANCE_REQUIRED = "CROSSOVER_VARIANCE_REQUIRED"
    ESTIMATOR_NONCONVERGENCE = "ESTIMATOR_NONCONVERGENCE"
    PREDICTION_INTERVAL_UNAVAILABLE = "PREDICTION_INTERVAL_UNAVAILABLE"
    UNSUPPORTED_EFFECT_MEASURE = "UNSUPPORTED_EFFECT_MEASURE"
    MISSING_VARIANCE = "MISSING_VARIANCE"
    MULTIPLE_ELIGIBLE_ESTIMATES_PER_STUDY = "MULTIPLE_ELIGIBLE_ESTIMATES_PER_STUDY"
    CANDIDATE_NOT_ANALYSIS_READY = "CANDIDATE_NOT_ANALYSIS_READY"
    UNVERIFIED_EXTRACTION = "UNVERIFIED_EXTRACTION"
    OUTCOME_VERSION_MISMATCH = "OUTCOME_VERSION_MISMATCH"
    TIMEPOINT_MISMATCH = "TIMEPOINT_MISMATCH"
    EFFECT_MEASURE_MISMATCH = "EFFECT_MEASURE_MISMATCH"
    UNIT_NOT_HARMONIZED = "UNIT_NOT_HARMONIZED"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    SCALE_DIRECTION_UNKNOWN = "SCALE_DIRECTION_UNKNOWN"
    SCALE_MISMATCH = "SCALE_MISMATCH"
    STUDY_DESIGN_INCOMPATIBLE = "STUDY_DESIGN_INCOMPATIBLE"
    ANALYSIS_POPULATION_MISMATCH = "ANALYSIS_POPULATION_MISMATCH"
    ADJUSTMENT_MISMATCH = "ADJUSTMENT_MISMATCH"
    ZERO_EVENT_POLICY_REQUIRED = "ZERO_EVENT_POLICY_REQUIRED"
    SUPERSEDED_ESTIMATE = "SUPERSEDED_ESTIMATE"
    STALE_ANALYSIS_SET = "STALE_ANALYSIS_SET"


@dataclass(frozen=True, slots=True)
class AnalysisSpecification:
    id: UUID
    organization_id: UUID
    review_id: UUID
    key: str
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AnalysisSpecificationVersion:
    id: UUID
    specification_id: UUID
    organization_id: UUID
    review_id: UUID
    version: int
    definition: dict[str, Any]
    content_hash: str
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AnalysisSet:
    id: UUID
    organization_id: UUID
    review_id: UUID
    specification_version_id: UUID
    candidate_set_id: UUID
    included_estimate_ids: tuple[UUID, ...]
    excluded_estimates: tuple[dict[str, Any], ...]
    input_hash: str
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StudyEffectInput:
    study_id: UUID
    estimate_id: UUID
    label: str
    presentation_estimate: Decimal
    analysis_estimate: Decimal
    variance: Decimal
    sample_size: int | None


@dataclass(frozen=True, slots=True)
class StudyWeight:
    study_id: UUID
    estimate_id: UUID
    analysis_estimate: Decimal
    presentation_estimate: Decimal
    ci_lower: Decimal
    ci_upper: Decimal
    raw_weight: Decimal
    normalized_weight_percent: Decimal


@dataclass(frozen=True, slots=True)
class HeterogeneityResult:
    q: Decimal
    degrees_of_freedom: int
    q_p_value: Decimal | None
    tau_squared: Decimal
    tau: Decimal
    i_squared_percent: Decimal


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    analysis_scale_estimate: Decimal
    analysis_scale_standard_error: Decimal
    analysis_scale_variance: Decimal
    analysis_scale_ci_lower: Decimal
    analysis_scale_ci_upper: Decimal
    presentation_estimate: Decimal
    presentation_ci_lower: Decimal
    presentation_ci_upper: Decimal
    confidence_level: Decimal
    number_of_studies: int
    total_participants: int | None
    model: StatisticalModel
    estimator: HeterogeneityEstimator
    ci_method: ConfidenceIntervalMethod
    transformation: EffectTransformation
    heterogeneity: HeterogeneityResult
    prediction_interval_lower: Decimal | None
    prediction_interval_upper: Decimal | None
    weights: tuple[StudyWeight, ...]
    diagnostics: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class SensitivityResult:
    omitted_study_id: UUID
    omitted_estimate_id: UUID
    result: SynthesisResult


@dataclass(frozen=True, slots=True)
class MetaAnalysisRun:
    id: UUID
    organization_id: UUID
    review_id: UUID
    specification_version_id: UUID
    analysis_set_id: UUID
    status: RunStatus
    algorithm_name: str
    algorithm_version: str
    provider: str
    provider_version: str
    input_hash: str
    result_hash: str | None
    result: dict[str, Any] | None
    diagnostics: tuple[dict[str, Any], ...]
    failure_reason: str | None
    created_by_user_id: UUID
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AnalysisArtifact:
    id: UUID
    organization_id: UUID
    review_id: UUID
    run_id: UUID
    artifact_type: str
    renderer_version: str
    media_type: str
    filename: str
    content: bytes
    sha256: str
    byte_size: int
    created_by_user_id: UUID
    created_at: datetime


def normalize_specification(definition: dict[str, Any]) -> dict[str, Any]:
    effect_measure = EffectMeasure(_key(definition, "effect_measure"))
    model = StatisticalModel(_key(definition, "model"))
    estimator = HeterogeneityEstimator(_key(definition, "heterogeneity_estimator"))
    transformation = EffectTransformation(_key(definition, "transformation"))
    confidence_level = Decimal(str(definition.get("confidence_level")))
    if confidence_level <= 0 or confidence_level >= 1:
        raise ValueError("confidence level must be between zero and one")
    if model == StatisticalModel.FIXED_EFFECT and estimator != HeterogeneityEstimator.NONE:
        raise ValueError("fixed-effect analysis requires the NONE heterogeneity estimator")
    if (
        model == StatisticalModel.RANDOM_EFFECTS
        and estimator != HeterogeneityEstimator.DERSIMONIAN_LAIRD
    ):
        raise ValueError("random-effects analysis requires an explicit supported estimator")
    ratio_measures = {EffectMeasure.RR, EffectMeasure.OR, EffectMeasure.HR}
    expected_transformation = (
        EffectTransformation.LOG
        if effect_measure in ratio_measures
        else EffectTransformation.IDENTITY
    )
    if transformation != expected_transformation:
        raise ValueError(
            f"{effect_measure.value} requires {expected_transformation.value} transformation"
        )
    standardized_definition = _optional(definition.get("standardized_effect_definition"))
    if effect_measure == EffectMeasure.SMD and standardized_definition not in {
        "COHEN_D",
        "HEDGES_G",
    }:
        raise ValueError("SMD requires an explicit COHEN_D or HEDGES_G definition")
    minimum_value = definition.get("minimum_studies")
    if minimum_value is None:
        raise ValueError("minimum studies is required")
    minimum_studies = int(str(minimum_value))
    if minimum_studies < 1:
        raise ValueError("minimum studies must be positive")
    study_designs = sorted(
        {
            str(value).strip().upper()
            for value in definition.get("eligible_study_designs", [])
            if str(value).strip()
        }
    )
    return {
        "outcome_version_id": str(UUID(str(definition.get("outcome_version_id")))),
        "timepoint_window_id": _uuid_or_none(definition.get("timepoint_window_id")),
        "synthesis_population": _required(definition.get("synthesis_population"), "population"),
        "intervention": _required(definition.get("intervention"), "intervention"),
        "comparator": _required(definition.get("comparator"), "comparator"),
        "eligible_study_designs": study_designs,
        "effect_measure": effect_measure.value,
        "model": model.value,
        "heterogeneity_estimator": estimator.value,
        "confidence_level": canonical_decimal(confidence_level),
        "transformation": transformation.value,
        "ci_method": ConfidenceIntervalMethod(_key(definition, "ci_method")).value,
        "zero_event_policy": ZeroEventPolicy(_key(definition, "zero_event_policy")).value,
        "missing_variance_policy": MissingVariancePolicy(
            _key(definition, "missing_variance_policy")
        ).value,
        "adjustment_policy": AdjustmentPolicy(_key(definition, "adjustment_policy")).value,
        "analysis_population": AnalysisPopulation(_key(definition, "analysis_population")).value,
        "selection_policy": EstimateSelectionPolicy(_key(definition, "selection_policy")).value,
        "multi_arm_policy": DependencyPolicy(_key(definition, "multi_arm_policy")).value,
        "cluster_policy": DependencyPolicy(_key(definition, "cluster_policy")).value,
        "crossover_policy": DependencyPolicy(_key(definition, "crossover_policy")).value,
        "minimum_studies": minimum_studies,
        "prediction_interval": bool(definition.get("prediction_interval")),
        "standardized_effect_definition": standardized_definition,
    }


def canonical_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("numeric values must be finite")
    normalized = value.quantize(PERSISTED_QUANTUM, rounding=ROUND_HALF_EVEN)
    return format(normalized, "f")


def transform_effect(estimate: Decimal, transformation: EffectTransformation) -> Decimal:
    if not estimate.is_finite():
        raise ValueError("effect estimate must be finite")
    if transformation == EffectTransformation.LOG:
        if estimate <= 0:
            raise ValueError("ratio effect estimates must be positive")
        return estimate.ln()
    return estimate


def presentation_effect(value: Decimal, transformation: EffectTransformation) -> Decimal:
    return value.exp() if transformation == EffectTransformation.LOG else value


def synthesis_result_payload(result: SynthesisResult) -> dict[str, Any]:
    return {
        "analysis_scale_estimate": canonical_decimal(result.analysis_scale_estimate),
        "analysis_scale_standard_error": canonical_decimal(result.analysis_scale_standard_error),
        "analysis_scale_variance": canonical_decimal(result.analysis_scale_variance),
        "analysis_scale_ci_lower": canonical_decimal(result.analysis_scale_ci_lower),
        "analysis_scale_ci_upper": canonical_decimal(result.analysis_scale_ci_upper),
        "presentation_estimate": canonical_decimal(result.presentation_estimate),
        "presentation_ci_lower": canonical_decimal(result.presentation_ci_lower),
        "presentation_ci_upper": canonical_decimal(result.presentation_ci_upper),
        "confidence_level": canonical_decimal(result.confidence_level),
        "number_of_studies": result.number_of_studies,
        "total_participants": result.total_participants,
        "model": result.model.value,
        "estimator": result.estimator.value,
        "ci_method": result.ci_method.value,
        "transformation": result.transformation.value,
        "heterogeneity": {
            "q": canonical_decimal(result.heterogeneity.q),
            "degrees_of_freedom": result.heterogeneity.degrees_of_freedom,
            "q_p_value": (
                canonical_decimal(result.heterogeneity.q_p_value)
                if result.heterogeneity.q_p_value is not None
                else None
            ),
            "tau_squared": canonical_decimal(result.heterogeneity.tau_squared),
            "tau": canonical_decimal(result.heterogeneity.tau),
            "i_squared_percent": canonical_decimal(result.heterogeneity.i_squared_percent),
        },
        "prediction_interval_lower": (
            canonical_decimal(result.prediction_interval_lower)
            if result.prediction_interval_lower is not None
            else None
        ),
        "prediction_interval_upper": (
            canonical_decimal(result.prediction_interval_upper)
            if result.prediction_interval_upper is not None
            else None
        ),
        "weights": [
            {
                "study_id": str(item.study_id),
                "estimate_id": str(item.estimate_id),
                "analysis_estimate": canonical_decimal(item.analysis_estimate),
                "presentation_estimate": canonical_decimal(item.presentation_estimate),
                "ci_lower": canonical_decimal(item.ci_lower),
                "ci_upper": canonical_decimal(item.ci_upper),
                "raw_weight": canonical_decimal(item.raw_weight),
                "normalized_weight_percent": canonical_decimal(item.normalized_weight_percent),
            }
            for item in result.weights
        ],
        "diagnostics": list(result.diagnostics),
    }


def z_value(confidence_level: Decimal) -> Decimal:
    probability = (Decimal("1") + confidence_level) / Decimal("2")
    return Decimal(str(NormalDist().inv_cdf(float(probability))))


def chi_square_survival(q: Decimal, degrees_of_freedom: int) -> Decimal | None:
    if degrees_of_freedom <= 0:
        return None
    value = _regularized_gamma_q(degrees_of_freedom / 2.0, float(q) / 2.0)
    return Decimal(str(min(1.0, max(0.0, value))))


def _regularized_gamma_q(shape: float, value: float) -> float:
    if value < 0 or shape <= 0:
        raise ValueError("invalid chi-square parameters")
    if value == 0:
        return 1.0
    if value < shape + 1.0:
        term = 1.0 / shape
        total = term
        ap = shape
        for _ in range(1, 1001):
            ap += 1.0
            term *= value / ap
            total += term
            if abs(term) <= abs(total) * 1e-15:
                lower = total * math.exp(-value + shape * math.log(value) - math.lgamma(shape))
                return 1.0 - lower
        raise ArithmeticError("chi-square series did not converge")
    b = value + 1.0 - shape
    c = 1.0 / 1e-300
    d = 1.0 / b
    h = d
    for index in range(1, 1001):
        an = -index * (index - shape)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-300:
            d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) <= 1e-15:
            return math.exp(-value + shape * math.log(value) - math.lgamma(shape)) * h
    raise ArithmeticError("chi-square continued fraction did not converge")


def _key(definition: dict[str, Any], name: str) -> str:
    value = str(definition.get(name, "")).strip().upper()
    if not value:
        raise ValueError(f"{name.replace('_', ' ')} is required")
    return value


def _required(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{label} is required")
    return result


def _optional(value: Any) -> str | None:
    result = str(value or "").strip().upper()
    return result or None


def _uuid_or_none(value: Any) -> str | None:
    return str(UUID(str(value))) if value else None
