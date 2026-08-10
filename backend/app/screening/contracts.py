from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.app.screening.domain import (
    ScreeningAdjudication,
    ScreeningAssignment,
    ScreeningDecision,
    ScreeningDecisionKind,
    ScreeningOutcome,
    ScreeningOutcomeKind,
    ScreeningProgression,
    ScreeningRound,
    ScreeningStage,
)


class ScreeningRepository(Protocol):
    async def create_round(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        name: str,
        stage: ScreeningStage,
        required_decisions: int,
        blinded: bool,
        created_by_user_id: UUID,
    ) -> ScreeningRound: ...

    async def get_round(self, organization_id: UUID, round_id: UUID) -> ScreeningRound | None: ...

    async def close_round(
        self, organization_id: UUID, round_id: UUID, closed_by_user_id: UUID
    ) -> ScreeningRound: ...

    async def get_assignment_for(
        self, organization_id: UUID, round_id: UUID, article_id: UUID, reviewer_id: UUID
    ) -> ScreeningAssignment | None: ...

    async def create_assignment(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        round_id: UUID,
        article_id: UUID,
        reviewer_user_id: UUID,
        assigned_by_user_id: UUID,
    ) -> ScreeningAssignment: ...

    async def count_article_assignments(
        self, organization_id: UUID, round_id: UUID, article_id: UUID
    ) -> int: ...

    async def list_reviewer_assignments(
        self, organization_id: UUID, round_id: UUID, reviewer_user_id: UUID
    ) -> list[ScreeningAssignment]: ...

    async def get_assignment(
        self, organization_id: UUID, assignment_id: UUID
    ) -> ScreeningAssignment | None: ...

    async def get_decision_for_assignment(
        self, organization_id: UUID, assignment_id: UUID
    ) -> ScreeningDecision | None: ...

    async def append_decision(
        self,
        *,
        assignment: ScreeningAssignment,
        decision: ScreeningDecisionKind,
        exclusion_reason: str | None,
    ) -> ScreeningDecision: ...

    async def list_article_decisions(
        self, organization_id: UUID, round_id: UUID, article_id: UUID
    ) -> list[ScreeningDecision]: ...

    async def get_outcome(
        self, organization_id: UUID, round_id: UUID, article_id: UUID
    ) -> ScreeningOutcome | None: ...

    async def get_outcome_by_id(
        self, organization_id: UUID, outcome_id: UUID
    ) -> ScreeningOutcome | None: ...

    async def append_outcome(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        round_id: UUID,
        article_id: UUID,
        outcome: ScreeningOutcomeKind,
    ) -> ScreeningOutcome: ...

    async def list_outcomes(
        self, organization_id: UUID, round_id: UUID
    ) -> list[ScreeningOutcome]: ...

    async def get_adjudication(
        self, organization_id: UUID, outcome_id: UUID
    ) -> ScreeningAdjudication | None: ...

    async def append_adjudication(
        self,
        *,
        outcome: ScreeningOutcome,
        decision: ScreeningDecisionKind,
        decided_by_user_id: UUID,
        reason: str | None,
    ) -> ScreeningAdjudication: ...

    async def round_is_complete(self, organization_id: UUID, round_id: UUID) -> bool: ...

    async def create_progression(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        article_id: UUID,
        source_round_id: UUID,
        target_round_id: UUID,
        created_by_user_id: UUID,
    ) -> ScreeningProgression: ...

    async def get_progression(
        self,
        organization_id: UUID,
        source_round_id: UUID,
        target_round_id: UUID,
        article_id: UUID,
    ) -> ScreeningProgression | None: ...
