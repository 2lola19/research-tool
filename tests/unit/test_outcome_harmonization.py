from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from backend.app.outcomes.domain import (
    AdjustmentStatus,
    AnalysisPopulation,
    Directionality,
    DirectionTransformation,
    EffectEstimate,
    EffectMeasure,
    EstimateOrigin,
    MappingMethod,
    MeasurementScale,
    OutcomeDefinitionVersion,
    OutcomeMapping,
    ReadinessStatus,
    SynthesisCandidateSet,
    TimeAnchor,
    TimeUnit,
    UnitDefinition,
    VarianceScale,
    ZeroEventPattern,
    apply_direction,
    convert_unit,
    derive_effect,
    normalize_outcome_definition,
    normalize_time_to_days,
    readiness_blockers,
    readiness_status,
)


def _unit(
    key: str, multiplier: str, *, context: str = "GENERAL", precision: int = 6
) -> UnitDefinition:
    return UnitDefinition(
        uuid4(),
        uuid4(),
        uuid4(),
        key,
        key,
        "MASS",
        context,
        "G",
        multiplier,
        "0",
        precision,
        "1",
        uuid4(),
        datetime.now(UTC),
    )


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        (TimeUnit.DAY, "28.000000000000"),
        (TimeUnit.WEEK, "196.000000000000"),
    ],
)
def test_time_normalization_is_explicit_and_deterministic(unit: TimeUnit, expected: str) -> None:
    assert str(normalize_time_to_days(Decimal("28"), unit)) == expected


@pytest.mark.parametrize("unit", [TimeUnit.MONTH, TimeUnit.YEAR])
def test_calendar_time_requires_a_review_specific_rule(unit: TimeUnit) -> None:
    with pytest.raises(ValueError, match="review-specific"):
        normalize_time_to_days(Decimal("1"), unit)


def test_unit_conversion_preserves_context_and_rounding() -> None:
    grams = _unit("G", "1", precision=3)
    kilograms = UnitDefinition(
        grams.id,
        grams.organization_id,
        grams.review_id,
        "KG",
        "kg",
        "MASS",
        "GENERAL",
        "G",
        "1000",
        "0",
        6,
        "1",
        grams.created_by_user_id,
        grams.created_at,
    )
    assert convert_unit(Decimal("1000"), grams, kilograms) == Decimal("1.000000")
    analyte_specific = _unit("MMOL_L", "1", context="GLUCOSE")
    with pytest.raises(ValueError, match="conversion context"):
        convert_unit(Decimal("1"), grams, analyte_specific)
    assert apply_direction(Decimal("7.25"), DirectionTransformation.SIGN_REVERSED) == Decimal(
        "-7.25"
    )


def test_outcome_definition_is_declarative_and_rejects_duplicates() -> None:
    normalized = normalize_outcome_definition(
        {
            "name": "All-cause mortality",
            "outcome_type": "DICHOTOMOUS",
            "directionality": "HIGHER_WORSE",
            "role": "PRIMARY",
            "compatible_effect_measures": ["RR", "OR", "RD"],
        }
    )
    assert normalized["compatible_effect_measures"] == ["RR", "OR", "RD"]
    with pytest.raises(ValueError, match="unique"):
        normalize_outcome_definition(
            {
                "name": "Mortality",
                "outcome_type": "DICHOTOMOUS",
                "directionality": "HIGHER_WORSE",
                "compatible_effect_measures": ["RR", "RR"],
            }
        )


def test_binary_effect_derivations_use_hand_verifiable_values() -> None:
    cells = {
        "events_intervention": Decimal("10"),
        "sample_intervention": Decimal("100"),
        "events_comparator": Decimal("20"),
        "sample_comparator": Decimal("100"),
    }
    rr, rr_se, rr_var, rr_zero = derive_effect(EffectMeasure.RR, cells)
    odds, odds_se, odds_var, _ = derive_effect(EffectMeasure.OR, cells)
    rd, rd_se, rd_var, _ = derive_effect(EffectMeasure.RD, cells)
    assert rr == Decimal("0.500000000000")
    assert rr_var == Decimal("0.130000000000")
    assert rr_se == Decimal("0.360555127546")
    assert odds == Decimal("0.444444444444")
    assert odds_var == Decimal("0.173611111111")
    assert odds_se == Decimal("0.416666666667")
    assert rd == Decimal("-0.100000000000")
    assert rd_var == Decimal("0.002500000000")
    assert rd_se == Decimal("0.050000000000")
    assert rr_zero == ZeroEventPattern.NONE


def test_mean_difference_and_zero_event_policy_are_not_silently_imputed() -> None:
    estimate, se, variance, pattern = derive_effect(
        EffectMeasure.MD,
        {
            "mean_intervention": Decimal("12.5"),
            "mean_comparator": Decimal("10"),
            "sd_intervention": Decimal("4"),
            "sample_intervention": Decimal("64"),
            "sd_comparator": Decimal("3"),
            "sample_comparator": Decimal("36"),
        },
    )
    assert (estimate, variance, se, pattern) == (
        Decimal("2.500000000000"),
        Decimal("0.500000000000"),
        Decimal("0.707106781187"),
        ZeroEventPattern.NONE,
    )
    zero = {
        "events_intervention": Decimal("0"),
        "sample_intervention": Decimal("50"),
        "events_comparator": Decimal("0"),
        "sample_comparator": Decimal("60"),
    }
    assert derive_effect(EffectMeasure.RR, zero) == (None, None, None, ZeroEventPattern.DOUBLE_ZERO)
    rd, _, _, rd_pattern = derive_effect(EffectMeasure.RD, zero)
    assert rd == Decimal("0E-12")
    assert rd_pattern == ZeroEventPattern.DOUBLE_ZERO
    with pytest.raises(ValueError, match="standard deviations"):
        derive_effect(
            EffectMeasure.MD,
            {
                "mean_intervention": Decimal("2"),
                "mean_comparator": Decimal("1"),
                "sd_intervention": Decimal("-1"),
                "sample_intervention": Decimal("10"),
                "sd_comparator": Decimal("1"),
                "sample_comparator": Decimal("10"),
            },
        )


@pytest.mark.parametrize(
    "components",
    [
        {
            "events_intervention": Decimal("1"),
            "sample_intervention": Decimal("0"),
            "events_comparator": Decimal("1"),
            "sample_comparator": Decimal("2"),
        },
        {
            "events_intervention": Decimal("3"),
            "sample_intervention": Decimal("2"),
            "events_comparator": Decimal("1"),
            "sample_comparator": Decimal("2"),
        },
        {
            "events_intervention": Decimal("0.5"),
            "sample_intervention": Decimal("2"),
            "events_comparator": Decimal("1"),
            "sample_comparator": Decimal("2"),
        },
    ],
)
def test_effect_derivation_rejects_invalid_denominators_and_counts(
    components: dict[str, Decimal],
) -> None:
    with pytest.raises(ValueError):
        derive_effect(EffectMeasure.RR, components)


def test_readiness_detects_duplicate_studies_and_unverified_sources() -> None:
    organization_id, review_id, study_id = uuid4(), uuid4(), uuid4()
    outcome_id, outcome_version_id, actor_id = uuid4(), uuid4(), uuid4()
    window_id, mapping_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    outcome = OutcomeDefinitionVersion(
        outcome_version_id,
        outcome_id,
        organization_id,
        review_id,
        1,
        {"compatible_effect_measures": ["RR"]},
        "a" * 64,
        None,
        actor_id,
        now,
    )
    mapping = OutcomeMapping(
        mapping_id,
        organization_id,
        review_id,
        study_id,
        uuid4(),
        outcome_version_id,
        MappingMethod.MANUAL,
        "Mapped",
        None,
        "10",
        None,
        None,
        "10",
        None,
        None,
        "28",
        TimeUnit.DAY,
        TimeAnchor.RANDOMIZATION,
        "28",
        window_id,
        "1",
        None,
        DirectionTransformation.NONE,
        None,
        False,
        None,
        actor_id,
        now,
    )

    def estimate() -> EffectEstimate:
        return EffectEstimate(
            uuid4(),
            organization_id,
            review_id,
            study_id,
            outcome_version_id,
            EffectMeasure.RR,
            EstimateOrigin.DERIVED,
            "0.5",
            "0.2",
            "0.04",
            VarianceScale.LOG,
            None,
            None,
            None,
            AdjustmentStatus.UNADJUSTED,
            AnalysisPopulation.INTENTION_TO_TREAT,
            None,
            None,
            window_id,
            None,
            None,
            {},
            (mapping_id,),
            None,
            "effect-foundation-1",
            ZeroEventPattern.NONE,
            actor_id,
            now,
        )

    estimates = [estimate(), estimate()]
    candidate = SynthesisCandidateSet(
        uuid4(),
        organization_id,
        review_id,
        outcome_version_id,
        EffectMeasure.RR,
        window_id,
        "Adults",
        tuple(item.id for item in estimates),
        actor_id,
        now,
    )
    blockers = readiness_blockers(candidate, outcome, estimates, {mapping.id: mapping}, {})
    codes = {item["code"] for item in blockers}
    assert {"DUPLICATE_STUDY_ESTIMATE", "UNVERIFIED_EXTRACTION"} <= codes
    assert readiness_status(blockers) == ReadinessStatus.NOT_READY


def test_readiness_distinguishes_harmonization_from_review() -> None:
    assert (
        readiness_status(({"code": "TIMEPOINT_MISMATCH"},)) == ReadinessStatus.NEEDS_HARMONIZATION
    )
    assert readiness_status(({"code": "ADJUSTMENT_MISMATCH"},)) == ReadinessStatus.NEEDS_REVIEW
    assert readiness_status(()) == ReadinessStatus.READY


def test_unknown_scale_direction_blocks_continuous_readiness() -> None:
    organization_id, review_id, study_id, actor_id = uuid4(), uuid4(), uuid4(), uuid4()
    outcome_version_id, mapping_id, scale_id, window_id = uuid4(), uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    outcome = OutcomeDefinitionVersion(
        outcome_version_id,
        uuid4(),
        organization_id,
        review_id,
        1,
        {"compatible_effect_measures": ["MD"]},
        "b" * 64,
        None,
        actor_id,
        now,
    )
    mapping = OutcomeMapping(
        mapping_id,
        organization_id,
        review_id,
        study_id,
        uuid4(),
        outcome_version_id,
        MappingMethod.MANUAL,
        "Mapped",
        None,
        "2",
        "score",
        None,
        "2",
        uuid4(),
        None,
        "28",
        TimeUnit.DAY,
        TimeAnchor.RANDOMIZATION,
        "28",
        window_id,
        "1",
        scale_id,
        DirectionTransformation.NONE,
        None,
        True,
        None,
        actor_id,
        now,
    )
    effect = EffectEstimate(
        uuid4(),
        organization_id,
        review_id,
        study_id,
        outcome_version_id,
        EffectMeasure.MD,
        EstimateOrigin.REPORTED,
        "2",
        "0.5",
        "0.25",
        VarianceScale.NATURAL,
        None,
        None,
        None,
        AdjustmentStatus.UNADJUSTED,
        AnalysisPopulation.INTENTION_TO_TREAT,
        None,
        None,
        window_id,
        mapping.normalized_unit_id,
        scale_id,
        {},
        (mapping_id,),
        None,
        None,
        ZeroEventPattern.NONE,
        actor_id,
        now,
    )
    candidate = SynthesisCandidateSet(
        uuid4(),
        organization_id,
        review_id,
        outcome_version_id,
        EffectMeasure.MD,
        window_id,
        None,
        (effect.id,),
        actor_id,
        now,
    )
    scale = MeasurementScale(
        scale_id,
        organization_id,
        review_id,
        "SCORE",
        "Score",
        "0",
        "20",
        Directionality.UNKNOWN,
        actor_id,
        now,
    )
    codes = {
        item["code"]
        for item in readiness_blockers(
            candidate, outcome, [effect], {mapping_id: mapping}, {scale_id: scale}
        )
    }
    assert "SCALE_DIRECTION_UNKNOWN" in codes
