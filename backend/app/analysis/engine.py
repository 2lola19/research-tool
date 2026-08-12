from __future__ import annotations

from decimal import Decimal, localcontext
from typing import Any

from backend.app.analysis.domain import (
    ALGORITHM_NAME,
    ALGORITHM_VERSION,
    ConfidenceIntervalMethod,
    DiagnosticCode,
    DiagnosticLevel,
    EffectTransformation,
    HeterogeneityEstimator,
    HeterogeneityResult,
    SensitivityResult,
    StatisticalModel,
    StudyEffectInput,
    StudyWeight,
    SynthesisResult,
    chi_square_survival,
    presentation_effect,
    z_value,
)


class NativeDeterministicSynthesisEngine:
    name = ALGORITHM_NAME
    version = ALGORITHM_VERSION
    provider = "NATIVE_PYTHON"
    provider_version = "decimal-v1"

    def synthesize(
        self, definition: dict[str, Any], studies: tuple[StudyEffectInput, ...]
    ) -> SynthesisResult:
        model = StatisticalModel(definition["model"])
        estimator = HeterogeneityEstimator(definition["heterogeneity_estimator"])
        transformation = EffectTransformation(definition["transformation"])
        confidence_level = Decimal(definition["confidence_level"])
        minimum_studies = int(definition["minimum_studies"])
        if len(studies) < minimum_studies:
            raise ValueError("analysis has fewer Studies than its explicit minimum")
        if model == StatisticalModel.RANDOM_EFFECTS and len(studies) < 2:
            raise ValueError("random-effects analysis requires at least two Studies")
        if not studies:
            raise ValueError("analysis requires at least one Study")
        if len({item.study_id for item in studies}) != len(studies):
            raise ValueError("analysis contains more than one estimate for a Study")
        if any(not item.variance.is_finite() or item.variance <= 0 for item in studies):
            raise ValueError("all sampling variances must be finite and positive")
        ordered = tuple(
            sorted(studies, key=lambda item: (str(item.study_id), str(item.estimate_id)))
        )
        with localcontext() as context:
            context.prec = 50
            fixed_weights = tuple(Decimal("1") / item.variance for item in ordered)
            fixed_total = sum(fixed_weights, Decimal("0"))
            fixed_mean = (
                sum(
                    weight * item.analysis_estimate
                    for weight, item in zip(fixed_weights, ordered, strict=True)
                )
                / fixed_total
            )
            q = sum(
                (
                    weight * (item.analysis_estimate - fixed_mean) ** 2
                    for weight, item in zip(fixed_weights, ordered, strict=True)
                ),
                Decimal("0"),
            )
            df = len(ordered) - 1
            tau_squared = Decimal("0")
            if model == StatisticalModel.RANDOM_EFFECTS:
                denominator = fixed_total - sum(weight**2 for weight in fixed_weights) / fixed_total
                if denominator <= 0:
                    raise ValueError("between-Study variance denominator is non-positive")
                tau_squared = max(Decimal("0"), (q - Decimal(df)) / denominator)
            weights = tuple(Decimal("1") / (item.variance + tau_squared) for item in ordered)
            total_weight = sum(weights, Decimal("0"))
            pooled = (
                sum(
                    weight * item.analysis_estimate
                    for weight, item in zip(weights, ordered, strict=True)
                )
                / total_weight
            )
            variance = Decimal("1") / total_weight
            standard_error = variance.sqrt()
            z = z_value(confidence_level)
            lower = pooled - z * standard_error
            upper = pooled + z * standard_error
            i_squared = (
                max(Decimal("0"), (q - Decimal(df)) / q) * Decimal("100")
                if q > 0 and df > 0
                else Decimal("0")
            )
            diagnostics: list[dict[str, Any]] = []
            if len(ordered) < 2:
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.TOO_FEW_STUDIES,
                        DiagnosticLevel.WARNING,
                        "Heterogeneity cannot be estimated from one Study.",
                    )
                )
            normalized = tuple(weight / total_weight * Decimal("100") for weight in weights)
            if max(normalized) > Decimal("80") and len(ordered) > 1:
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.EXTREME_WEIGHT_DOMINANCE,
                        DiagnosticLevel.WARNING,
                        "One Study contributes more than 80% of model weight.",
                    )
                )
            study_weights = tuple(
                StudyWeight(
                    study_id=item.study_id,
                    estimate_id=item.estimate_id,
                    analysis_estimate=item.analysis_estimate,
                    presentation_estimate=item.presentation_estimate,
                    ci_lower=presentation_effect(
                        item.analysis_estimate - z * item.variance.sqrt(), transformation
                    ),
                    ci_upper=presentation_effect(
                        item.analysis_estimate + z * item.variance.sqrt(), transformation
                    ),
                    raw_weight=weight,
                    normalized_weight_percent=percent,
                )
                for item, weight, percent in zip(ordered, weights, normalized, strict=True)
            )
            prediction_lower: Decimal | None = None
            prediction_upper: Decimal | None = None
            if bool(definition["prediction_interval"]):
                if model == StatisticalModel.RANDOM_EFFECTS and len(ordered) >= 3:
                    prediction_se = (variance + tau_squared).sqrt()
                    prediction_lower = presentation_effect(
                        pooled - z * prediction_se, transformation
                    )
                    prediction_upper = presentation_effect(
                        pooled + z * prediction_se, transformation
                    )
                else:
                    diagnostics.append(
                        _diagnostic(
                            DiagnosticCode.PREDICTION_INTERVAL_UNAVAILABLE,
                            DiagnosticLevel.WARNING,
                            "Prediction interval requires random effects and at least "
                            "three Studies.",
                        )
                    )
            total_participants = (
                sum(item.sample_size for item in ordered if item.sample_size is not None)
                if all(item.sample_size is not None for item in ordered)
                else None
            )
            return SynthesisResult(
                analysis_scale_estimate=pooled,
                analysis_scale_standard_error=standard_error,
                analysis_scale_variance=variance,
                analysis_scale_ci_lower=lower,
                analysis_scale_ci_upper=upper,
                presentation_estimate=presentation_effect(pooled, transformation),
                presentation_ci_lower=presentation_effect(lower, transformation),
                presentation_ci_upper=presentation_effect(upper, transformation),
                confidence_level=confidence_level,
                number_of_studies=len(ordered),
                total_participants=total_participants,
                model=model,
                estimator=estimator,
                ci_method=ConfidenceIntervalMethod(definition["ci_method"]),
                transformation=transformation,
                heterogeneity=HeterogeneityResult(
                    q=q,
                    degrees_of_freedom=df,
                    q_p_value=chi_square_survival(q, df),
                    tau_squared=tau_squared,
                    tau=tau_squared.sqrt(),
                    i_squared_percent=i_squared,
                ),
                prediction_interval_lower=prediction_lower,
                prediction_interval_upper=prediction_upper,
                weights=study_weights,
                diagnostics=tuple(diagnostics),
            )

    def leave_one_out(
        self, definition: dict[str, Any], studies: tuple[StudyEffectInput, ...]
    ) -> tuple[SensitivityResult, ...]:
        if len(studies) < 3:
            return ()
        sensitivity_definition = dict(definition)
        sensitivity_definition["minimum_studies"] = 1
        return tuple(
            SensitivityResult(
                omitted_study_id=omitted.study_id,
                omitted_estimate_id=omitted.estimate_id,
                result=self.synthesize(
                    sensitivity_definition,
                    tuple(item for item in studies if item.study_id != omitted.study_id),
                ),
            )
            for omitted in sorted(studies, key=lambda item: str(item.study_id))
        )


def _diagnostic(code: DiagnosticCode, level: DiagnosticLevel, message: str) -> dict[str, Any]:
    return {"code": code.value, "level": level.value, "message": message}
