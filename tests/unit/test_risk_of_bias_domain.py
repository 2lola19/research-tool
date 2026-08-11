from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.app.risk_of_bias.domain import (
    AssessmentStatus,
    RiskOfBiasAnswer,
    RiskOfBiasAssessment,
    RiskOfBiasDomainJudgment,
    compare_assessment_snapshots,
    normalize_instrument_definition,
    suggest_domain_judgment,
    suggest_overall_judgment,
)
from backend.app.risk_of_bias.fixtures import DEMONSTRATION_RCT_INSTRUMENT


def test_instrument_definition_is_ordered_validated_and_deterministic() -> None:
    normalized = normalize_instrument_definition(DEMONSTRATION_RCT_INSTRUMENT)
    assert [item["order"] for item in normalized["domains"]] == [0, 1]
    assert [item["order"] for item in normalized["domains"][0]["questions"]] == [0, 1]
    assert (
        suggest_domain_judgment(
            normalized,
            "RANDOMIZATION",
            {"RANDOM_SEQUENCE": "YES", "ALLOCATION_CONCEALED": "NO_INFORMATION"},
        )
        == "SOME_CONCERNS"
    )
    assert (
        suggest_overall_judgment(
            normalized, {"RANDOMIZATION": "LOW", "MISSING_OUTCOME_DATA": "HIGH"}
        )
        == "HIGH"
    )

    invalid = deepcopy(DEMONSTRATION_RCT_INSTRUMENT)
    invalid["domains"][0]["questions"][0]["allowed_answers"] = ["INVENTED"]
    with pytest.raises(ValueError, match="invalid answer choices"):
        normalize_instrument_definition(invalid)


def _assessment(answer: str, domain: str, overall: str) -> RiskOfBiasAssessment:
    assessment_id = uuid4()
    now = datetime.now(UTC)
    return RiskOfBiasAssessment(
        id=assessment_id,
        organization_id=uuid4(),
        review_id=uuid4(),
        study_id=uuid4(),
        instrument_version_id=uuid4(),
        assessor_user_id=uuid4(),
        round_number=1,
        revision=1,
        supersedes_assessment_id=None,
        status=AssessmentStatus.SUBMITTED,
        overall_suggested_judgment=overall,
        overall_final_judgment=overall,
        overall_rationale="Independent rationale",
        overall_override_reason=None,
        overall_evidence_location_id=None,
        created_at=now,
        submitted_at=now,
        answers=(
            RiskOfBiasAnswer(uuid4(), assessment_id, "Q1", answer, "Evidence rationale", None, now),
        ),
        domain_judgments=(
            RiskOfBiasDomainJudgment(
                uuid4(), assessment_id, "D1", domain, domain, "Domain rationale", None, None, now
            ),
        ),
    )


def test_comparison_reports_scientific_disagreement_not_rationale_wording() -> None:
    first = _assessment("YES", "LOW", "LOW")
    agreeing = _assessment("YES", "LOW", "LOW")
    assert compare_assessment_snapshots(first, agreeing) == ()

    differing = _assessment("NO", "HIGH", "HIGH")
    assert compare_assessment_snapshots(first, differing) == (
        {"scope": "answer", "key": "Q1", "value_a": "YES", "value_b": "NO"},
        {"scope": "domain", "key": "D1", "value_a": "LOW", "value_b": "HIGH"},
        {"scope": "overall", "key": "overall", "value_a": "LOW", "value_b": "HIGH"},
    )
