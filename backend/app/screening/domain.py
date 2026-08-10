from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from backend.app.citations.domain import Article


class ScreeningStage(StrEnum):
    TITLE_ABSTRACT = "TITLE_ABSTRACT"
    FULL_TEXT = "FULL_TEXT"


class ScreeningRoundState(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class ScreeningDecisionKind(StrEnum):
    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"


class ScreeningOutcomeKind(StrEnum):
    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True)
class ScreeningRound:
    id: UUID
    organization_id: UUID
    review_id: UUID
    name: str
    stage: ScreeningStage
    sequence: int
    required_decisions: int
    blinded: bool
    state: ScreeningRoundState
    created_by_user_id: UUID
    created_at: datetime
    closed_at: datetime | None
    closed_by_user_id: UUID | None


@dataclass(frozen=True, slots=True)
class ScreeningAssignment:
    id: UUID
    round_id: UUID
    organization_id: UUID
    review_id: UUID
    article_id: UUID
    reviewer_user_id: UUID
    assigned_by_user_id: UUID
    assigned_at: datetime


@dataclass(frozen=True, slots=True)
class ScreeningDecision:
    id: UUID
    assignment_id: UUID
    organization_id: UUID
    review_id: UUID
    round_id: UUID
    article_id: UUID
    reviewer_user_id: UUID
    decision: ScreeningDecisionKind
    exclusion_reason: str | None
    decided_at: datetime


@dataclass(frozen=True, slots=True)
class ScreeningOutcome:
    id: UUID
    organization_id: UUID
    review_id: UUID
    round_id: UUID
    article_id: UUID
    outcome: ScreeningOutcomeKind
    computed_at: datetime


@dataclass(frozen=True, slots=True)
class ScreeningAdjudication:
    id: UUID
    outcome_id: UUID
    organization_id: UUID
    review_id: UUID
    decision: ScreeningDecisionKind
    decided_by_user_id: UUID
    reason: str | None
    decided_at: datetime


@dataclass(frozen=True, slots=True)
class ScreeningProgression:
    id: UUID
    organization_id: UUID
    review_id: UUID
    article_id: UUID
    source_round_id: UUID
    target_round_id: UUID
    created_by_user_id: UUID
    created_at: datetime


def compute_outcome(
    decisions: list[ScreeningDecisionKind], required_decisions: int
) -> ScreeningOutcomeKind | None:
    if len(decisions) < required_decisions:
        return None
    considered = decisions[:required_decisions]
    if all(item == ScreeningDecisionKind.INCLUDE for item in considered):
        return ScreeningOutcomeKind.INCLUDE
    if all(item == ScreeningDecisionKind.EXCLUDE for item in considered):
        return ScreeningOutcomeKind.EXCLUDE
    return ScreeningOutcomeKind.CONFLICT


@dataclass(frozen=True, slots=True)
class ScreeningQueueItem:
    assignment: ScreeningAssignment
    article: Article
    own_decision: ScreeningDecision | None
    outcome: ScreeningOutcome | None
