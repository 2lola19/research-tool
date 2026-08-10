from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.citations.persistence import SqlAlchemyCitationRepository
from backend.app.deduplication.domain import (
    DedupDecisionKind,
    DeduplicationDecision,
    DeduplicationRun,
    DuplicateCandidate,
    MatchReason,
)
from backend.app.deduplication.persistence import SqlAlchemyDeduplicationRepository
from backend.app.deduplication.service import DeduplicationService
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository

router = APIRouter(prefix="/deduplication", tags=["deduplication"])


class DeduplicationRunResponse(BaseModel):
    id: UUID
    review_id: UUID
    algorithm_version: str
    input_hash: str
    article_count: int
    candidate_count: int

    @classmethod
    def from_domain(cls, run: DeduplicationRun) -> DeduplicationRunResponse:
        return cls(
            id=run.id,
            review_id=run.review_id,
            algorithm_version=run.algorithm_version,
            input_hash=run.input_hash,
            article_count=run.article_count,
            candidate_count=run.candidate_count,
        )


class DeduplicationDecisionRequest(BaseModel):
    decision: DedupDecisionKind
    retained_article_id: UUID | None = None
    reason: str | None = Field(default=None, max_length=4000)


class DuplicateCandidateResponse(BaseModel):
    id: UUID
    left_article_id: UUID
    right_article_id: UUID
    reason: MatchReason
    score: float
    decision: DedupDecisionKind | None
    decided_by_user_id: UUID | None
    retained_article_id: UUID | None

    @classmethod
    def from_domain(
        cls,
        candidate: DuplicateCandidate,
        decision: DeduplicationDecision | None,
    ) -> DuplicateCandidateResponse:
        return cls(
            id=candidate.id,
            left_article_id=candidate.left_article_id,
            right_article_id=candidate.right_article_id,
            reason=candidate.reason,
            score=candidate.score,
            decision=decision.decision if decision is not None else None,
            decided_by_user_id=(decision.decided_by_user_id if decision is not None else None),
            retained_article_id=(decision.retained_article_id if decision is not None else None),
        )


class DeduplicationDecisionResponse(BaseModel):
    id: UUID
    candidate_id: UUID
    decision: DedupDecisionKind
    decided_by_user_id: UUID
    retained_article_id: UUID | None
    reason: str | None

    @classmethod
    def from_domain(cls, decision: DeduplicationDecision) -> DeduplicationDecisionResponse:
        return cls(
            id=decision.id,
            candidate_id=decision.candidate_id,
            decision=decision.decision,
            decided_by_user_id=decision.decided_by_user_id,
            retained_article_id=decision.retained_article_id,
            reason=decision.reason,
        )


def _service(session: DbSessionDependency) -> DeduplicationService:
    return DeduplicationService(
        SqlAlchemyDeduplicationRepository(session),
        SqlAlchemyCitationRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyProvenanceRepository(session),
    )


@router.post(
    "/reviews/{review_id}/runs",
    response_model=DeduplicationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def run_deduplication(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> DeduplicationRunResponse:
    run = await _service(session).scan(actor, review_id)
    await session.commit()
    return DeduplicationRunResponse.from_domain(run)


@router.get("/reviews/{review_id}/candidates", response_model=list[DuplicateCandidateResponse])
async def list_duplicate_candidates(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[DuplicateCandidateResponse]:
    candidates = await _service(session).list_candidates(actor, review_id)
    return [
        DuplicateCandidateResponse.from_domain(candidate, decision)
        for candidate, decision in candidates
    ]


@router.post(
    "/candidates/{candidate_id}/decision",
    response_model=DeduplicationDecisionResponse,
)
async def decide_duplicate_candidate(
    payload: DeduplicationDecisionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    candidate_id: Annotated[UUID, Path()],
) -> DeduplicationDecisionResponse:
    decision = await _service(session).decide(
        actor,
        candidate_id=candidate_id,
        decision=payload.decision,
        retained_article_id=payload.retained_article_id,
        reason=payload.reason,
    )
    await session.commit()
    return DeduplicationDecisionResponse.from_domain(decision)
