from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.app.deduplication.domain import (
    CandidateMatch,
    DedupDecisionKind,
    DeduplicationDecision,
    DeduplicationRun,
    DuplicateCandidate,
)


class DeduplicationRepository(Protocol):
    async def get_run_by_input(
        self,
        organization_id: UUID,
        review_id: UUID,
        algorithm_version: str,
        input_hash: str,
    ) -> DeduplicationRun | None: ...

    async def create_run(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        algorithm_version: str,
        input_hash: str,
        article_count: int,
        matches: list[CandidateMatch],
        created_by_user_id: UUID,
    ) -> tuple[DeduplicationRun, list[DuplicateCandidate]]: ...

    async def list_candidates(
        self, organization_id: UUID, review_id: UUID
    ) -> list[tuple[DuplicateCandidate, DeduplicationDecision | None]]: ...

    async def get_candidate(
        self, organization_id: UUID, candidate_id: UUID
    ) -> DuplicateCandidate | None: ...

    async def get_decision(
        self, organization_id: UUID, candidate_id: UUID
    ) -> DeduplicationDecision | None: ...

    async def append_decision(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        candidate_id: UUID,
        decision: DedupDecisionKind,
        retained_article_id: UUID | None,
        decided_by_user_id: UUID,
        reason: str | None,
    ) -> DeduplicationDecision: ...

    async def is_confirmed_duplicate(
        self, organization_id: UUID, review_id: UUID, article_id: UUID
    ) -> bool: ...
