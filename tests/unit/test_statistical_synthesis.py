from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from backend.app.analysis.domain import (
    EffectTransformation,
    StudyEffectInput,
    chi_square_survival,
    normalize_specification,
    presentation_effect,
    transform_effect,
)
from backend.app.analysis.engine import NativeDeterministicSynthesisEngine
from backend.app.analysis.renderers import forest_plot_model, render_forest_svg

FIXTURE = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "meta_analysis_golden.json").read_text()
)


def _definition(*, model: str = "FIXED_EFFECT", prediction: bool = False) -> dict[str, object]:
    return {
        "outcome_version_id": "00000000-0000-0000-0000-000000000001",
        "timepoint_window_id": "00000000-0000-0000-0000-000000000002",
        "synthesis_population": "Adults",
        "intervention": "Intervention A",
        "comparator": "Placebo",
        "eligible_study_designs": ["RANDOMIZED_CONTROLLED_TRIAL"],
        "effect_measure": "MD",
        "model": model,
        "heterogeneity_estimator": ("DERSIMONIAN_LAIRD" if model == "RANDOM_EFFECTS" else "NONE"),
        "confidence_level": "0.95",
        "transformation": "IDENTITY",
        "ci_method": "NORMAL",
        "zero_event_policy": "BLOCK",
        "missing_variance_policy": "BLOCK",
        "adjustment_policy": "UNADJUSTED_ONLY",
        "analysis_population": "INTENTION_TO_TREAT",
        "selection_policy": "EXPLICIT_ESTIMATE_IDS",
        "multi_arm_policy": "BLOCK",
        "cluster_policy": "BLOCK",
        "crossover_policy": "BLOCK",
        "minimum_studies": 1,
        "prediction_interval": prediction,
        "standardized_effect_definition": None,
    }


def _studies() -> tuple[StudyEffectInput, ...]:
    return tuple(
        StudyEffectInput(
            UUID(int=index),
            UUID(int=index + 10),
            f"Study {index}",
            estimate,
            estimate,
            variance,
            sample_size,
        )
        for index, estimate, variance, sample_size in (
            (1, Decimal("0.2"), Decimal("0.04"), 100),
            (2, Decimal("0.5"), Decimal("0.09"), 120),
            (3, Decimal("1.2"), Decimal("0.16"), 80),
        )
    )


def _close(actual: Decimal, expected: str, tolerance: str = "0.000000001") -> None:
    assert abs(actual - Decimal(expected)) <= Decimal(tolerance)


def test_fixed_effect_matches_independent_golden_fixture() -> None:
    result = NativeDeterministicSynthesisEngine().synthesize(_definition(), _studies())
    expected = FIXTURE["fixed_effect"]
    _close(result.analysis_scale_estimate, expected["estimate"])
    _close(result.analysis_scale_variance, expected["variance"])
    _close(result.analysis_scale_standard_error, expected["standard_error"])
    _close(result.analysis_scale_ci_lower, expected["ci_lower"])
    _close(result.analysis_scale_ci_upper, expected["ci_upper"])
    _close(result.heterogeneity.q, expected["q"])
    assert result.heterogeneity.q_p_value is not None
    _close(result.heterogeneity.q_p_value, expected["q_p_value"])
    _close(result.heterogeneity.i_squared_percent, expected["i_squared_percent"])
    assert result.heterogeneity.tau_squared == 0
    for actual, value in zip(result.weights, expected["weights_percent"], strict=True):
        _close(actual.normalized_weight_percent, value)
    assert result.total_participants == 300


def test_random_effects_dl_and_prediction_interval_match_golden_fixture() -> None:
    definition = _definition(model="RANDOM_EFFECTS", prediction=True)
    result = NativeDeterministicSynthesisEngine().synthesize(definition, _studies())
    expected = FIXTURE["random_effects_dl"]
    _close(result.analysis_scale_estimate, expected["estimate"])
    _close(result.analysis_scale_variance, expected["variance"])
    _close(result.analysis_scale_standard_error, expected["standard_error"])
    _close(result.analysis_scale_ci_lower, expected["ci_lower"])
    _close(result.analysis_scale_ci_upper, expected["ci_upper"])
    _close(result.heterogeneity.tau_squared, expected["tau_squared"])
    _close(result.heterogeneity.tau, expected["tau"])
    assert result.prediction_interval_lower is not None
    assert result.prediction_interval_upper is not None
    _close(result.prediction_interval_lower, expected["prediction_lower"])
    _close(result.prediction_interval_upper, expected["prediction_upper"])
    for actual, value in zip(result.weights, expected["weights_percent"], strict=True):
        _close(actual.normalized_weight_percent, value)


def test_leave_one_out_uses_same_engine_without_mutating_parent() -> None:
    engine = NativeDeterministicSynthesisEngine()
    results = engine.leave_one_out(_definition(model="RANDOM_EFFECTS"), _studies())
    assert len(results) == 3
    expected = FIXTURE["random_effects_dl"]["leave_one_out_estimates"]
    for result, value in zip(results, expected, strict=True):
        _close(result.result.presentation_estimate, value)
        assert result.result.number_of_studies == 2


def test_log_scale_round_trip_and_ratio_configuration() -> None:
    value = Decimal("0.76")
    transformed = transform_effect(value, EffectTransformation.LOG)
    _close(presentation_effect(transformed, EffectTransformation.LOG), "0.76")
    ratio = _definition()
    ratio.update({"effect_measure": "RR", "transformation": "LOG"})
    assert normalize_specification(ratio)["transformation"] == "LOG"
    ratio["transformation"] = "IDENTITY"
    with pytest.raises(ValueError, match="requires LOG"):
        normalize_specification(ratio)
    with pytest.raises(ValueError, match="positive"):
        transform_effect(Decimal("0"), EffectTransformation.LOG)


def test_ratio_pooling_uses_log_scale_and_back_transforms() -> None:
    ratio = _definition()
    ratio.update({"effect_measure": "RR", "transformation": "LOG"})
    studies = (
        StudyEffectInput(
            UUID(int=1),
            UUID(int=11),
            "RR low",
            Decimal("0.5"),
            Decimal("0.5").ln(),
            Decimal("0.1"),
            100,
        ),
        StudyEffectInput(
            UUID(int=2),
            UUID(int=12),
            "RR high",
            Decimal("2"),
            Decimal("2").ln(),
            Decimal("0.1"),
            100,
        ),
    )
    result = NativeDeterministicSynthesisEngine().synthesize(ratio, studies)
    _close(result.analysis_scale_estimate, "0", "0.000000000000001")
    _close(result.presentation_estimate, "1", "0.000000000000001")
    expected_lower = (Decimal("0") - Decimal("1.959963984540054") * Decimal("0.05").sqrt()).exp()
    _close(result.presentation_ci_lower, str(expected_lower), "0.000000000000001")
    _close(result.presentation_ci_upper, str(Decimal("1") / expected_lower), "0.000000000000001")


def test_specification_has_no_hidden_scientific_defaults() -> None:
    definition = _definition()
    del definition["zero_event_policy"]
    with pytest.raises(ValueError, match="zero event policy is required"):
        normalize_specification(definition)
    smd = _definition()
    smd.update({"effect_measure": "SMD", "standardized_effect_definition": None})
    with pytest.raises(ValueError, match="SMD requires"):
        normalize_specification(smd)
    random = _definition(model="RANDOM_EFFECTS")
    random["heterogeneity_estimator"] = "NONE"
    with pytest.raises(ValueError, match="explicit supported estimator"):
        normalize_specification(random)


@pytest.mark.parametrize("variance", ["0", "-0.1", "NaN"])
def test_non_positive_or_non_finite_variance_fails_safely(variance: str) -> None:
    study = _studies()[0]
    invalid = StudyEffectInput(
        study.study_id,
        study.estimate_id,
        study.label,
        study.presentation_estimate,
        study.analysis_estimate,
        Decimal(variance),
        study.sample_size,
    )
    with pytest.raises(ValueError, match="variances"):
        NativeDeterministicSynthesisEngine().synthesize(_definition(), (invalid,))


def test_duplicate_study_and_single_study_random_effects_fail_safely() -> None:
    first = _studies()[0]
    duplicate = StudyEffectInput(
        first.study_id,
        UUID(int=99),
        "Duplicate",
        Decimal("0.4"),
        Decimal("0.4"),
        Decimal("0.1"),
        50,
    )
    engine = NativeDeterministicSynthesisEngine()
    with pytest.raises(ValueError, match="more than one estimate"):
        engine.synthesize(_definition(), (first, duplicate))
    with pytest.raises(ValueError, match="at least two"):
        engine.synthesize(_definition(model="RANDOM_EFFECTS"), (first,))


def test_single_study_fixed_effect_is_explicitly_diagnostic() -> None:
    result = NativeDeterministicSynthesisEngine().synthesize(_definition(), (_studies()[0],))
    assert result.presentation_estimate == Decimal("0.2")
    assert result.heterogeneity.degrees_of_freedom == 0
    assert result.heterogeneity.q_p_value is None
    assert {item["code"] for item in result.diagnostics} == {"TOO_FEW_STUDIES"}


def test_two_study_prediction_interval_is_not_misleading() -> None:
    result = NativeDeterministicSynthesisEngine().synthesize(
        _definition(model="RANDOM_EFFECTS", prediction=True), _studies()[:2]
    )
    assert result.prediction_interval_lower is None
    assert result.prediction_interval_upper is None
    assert "PREDICTION_INTERVAL_UNAVAILABLE" in {item["code"] for item in result.diagnostics}


def test_extreme_weight_and_variance_ranges_remain_finite_and_diagnostic() -> None:
    studies = (
        StudyEffectInput(
            UUID(int=1),
            UUID(int=11),
            "Precise",
            Decimal("1000000"),
            Decimal("1000000"),
            Decimal("0.000000000001"),
            10,
        ),
        StudyEffectInput(
            UUID(int=2),
            UUID(int=12),
            "Imprecise",
            Decimal("-1000000"),
            Decimal("-1000000"),
            Decimal("1000000000000"),
            20,
        ),
    )
    result = NativeDeterministicSynthesisEngine().synthesize(_definition(), studies)
    assert result.analysis_scale_estimate.is_finite()
    assert result.analysis_scale_variance.is_finite()
    assert "EXTREME_WEIGHT_DOMINANCE" in {item["code"] for item in result.diagnostics}


@pytest.mark.parametrize("confidence", ["0", "1", "-0.5", "1.5"])
def test_invalid_confidence_levels_are_rejected(confidence: str) -> None:
    definition = _definition()
    definition["confidence_level"] = confidence
    with pytest.raises(ValueError, match="between zero and one"):
        normalize_specification(definition)


def test_chi_square_survival_known_df_two_identity() -> None:
    # For df=2, survival is exactly exp(-Q/2); Q=2*ln(2) therefore gives 0.5.
    probability = chi_square_survival(Decimal("2") * Decimal("2").ln(), 2)
    assert probability is not None
    _close(probability, "0.5", "0.000000000001")
    assert chi_square_survival(Decimal("0"), 0) is None


def test_forest_plot_renderer_is_deterministic_and_statistics_free() -> None:
    result = NativeDeterministicSynthesisEngine().synthesize(_definition(), _studies())
    from backend.app.analysis.domain import synthesis_result_payload

    payload = synthesis_result_payload(result)
    labels = {str(item.study_id): item.label for item in _studies()}
    model = forest_plot_model(effect_measure="MD", result=payload, study_labels=labels)
    first = render_forest_svg(model)
    assert first == render_forest_svg(model)
    assert b"Study 1" in first
    assert b"Pooled" in first
    assert b"I\xc2\xb2" in first
