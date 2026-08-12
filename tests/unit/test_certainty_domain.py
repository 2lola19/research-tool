from datetime import UTC, datetime
from uuid import UUID

import pytest

from backend.app.certainty.domain import (
    AdjustmentDirection,
    CertaintyDomainJudgment,
    CertaintyLevel,
    calculate_candidate_certainty,
    normalize_framework_definition,
)
from backend.app.certainty.fixtures import GRADE_COMPATIBLE_FOUNDATION


def _judgment(key: str, direction: AdjustmentDirection, magnitude: int) -> CertaintyDomainJudgment:
    return CertaintyDomainJudgment(
        UUID(int=magnitude + len(key)),
        UUID(int=1),
        key,
        direction,
        magnitude,
        "TEST",
        "Explicit human rationale",
        None,
        {},
        datetime.now(UTC),
    )


def test_grade_compatible_framework_has_ordered_structured_domains() -> None:
    normalized = normalize_framework_definition(GRADE_COMPATIBLE_FOUNDATION)
    assert [item["key"] for item in normalized["domains"][:5]] == [
        "RISK_OF_BIAS",
        "INCONSISTENCY",
        "INDIRECTNESS",
        "IMPRECISION",
        "PUBLICATION_BIAS",
    ]
    assert normalized["starting_rules"]["RANDOMIZED"] == "HIGH"
    assert normalized["starting_rules"]["OBSERVATIONAL"] == "LOW"


def test_golden_rct_downgrades_to_low() -> None:
    judgments = (
        _judgment("RISK_OF_BIAS", AdjustmentDirection.DOWNGRADE, 1),
        _judgment("INCONSISTENCY", AdjustmentDirection.DOWNGRADE, 0),
        _judgment("INDIRECTNESS", AdjustmentDirection.DOWNGRADE, 0),
        _judgment("IMPRECISION", AdjustmentDirection.DOWNGRADE, 1),
        _judgment("PUBLICATION_BIAS", AdjustmentDirection.DOWNGRADE, 0),
    )
    assert calculate_candidate_certainty(CertaintyLevel.HIGH, judgments) == CertaintyLevel.LOW


def test_certainty_floor_and_ceiling_are_deterministic() -> None:
    down = (_judgment("ROB", AdjustmentDirection.DOWNGRADE, 2),) * 3
    up = (_judgment("LARGE", AdjustmentDirection.UPGRADE, 2),) * 3
    assert calculate_candidate_certainty(CertaintyLevel.LOW, down) == CertaintyLevel.VERY_LOW
    assert calculate_candidate_certainty(CertaintyLevel.LOW, up) == CertaintyLevel.HIGH


def test_observational_upgrade_and_mixed_adjustments() -> None:
    judgments = (
        _judgment("ROB", AdjustmentDirection.DOWNGRADE, 1),
        _judgment("LARGE", AdjustmentDirection.UPGRADE, 2),
    )
    assert calculate_candidate_certainty(CertaintyLevel.LOW, judgments) == CertaintyLevel.MODERATE


def test_invalid_framework_adjustment_is_rejected() -> None:
    invalid = dict(GRADE_COMPATIBLE_FOUNDATION)
    invalid["domains"] = [
        {
            "key": "ROB",
            "label": "Risk of bias",
            "direction": "DOWNGRADE",
            "choices": [{"value": "BAD", "label": "Bad", "magnitude": 3}],
        }
    ]
    with pytest.raises(ValueError, match="between 0 and 2"):
        normalize_framework_definition(invalid)
