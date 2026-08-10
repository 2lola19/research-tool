from backend.app.screening.domain import (
    ScreeningDecisionKind,
    ScreeningOutcomeKind,
    compute_outcome,
)


def test_screening_outcome_waits_for_required_decisions() -> None:
    assert compute_outcome([ScreeningDecisionKind.INCLUDE], 2) is None


def test_screening_consensus_outcomes_are_deterministic() -> None:
    assert compute_outcome([ScreeningDecisionKind.INCLUDE] * 2, 2) == ScreeningOutcomeKind.INCLUDE
    assert compute_outcome([ScreeningDecisionKind.EXCLUDE] * 2, 2) == ScreeningOutcomeKind.EXCLUDE


def test_screening_disagreement_creates_conflict() -> None:
    decisions = [ScreeningDecisionKind.INCLUDE, ScreeningDecisionKind.EXCLUDE]
    assert compute_outcome(decisions, 2) == ScreeningOutcomeKind.CONFLICT
