from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.ai.full_text_persistence import SqlAlchemyAIFullTextRepository
from backend.app.ai.full_text_service import AIFullTextScreeningService
from backend.app.ai.mock_provider import DeterministicMockAIProvider
from backend.app.ai.persistence import SqlAlchemyAIRepository
from backend.app.ai.screening_persistence import SqlAlchemyAIScreeningRepository
from backend.app.ai.screening_service import AIScreeningService
from backend.app.ai.service import AIExecutionService
from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.citations.persistence import SqlAlchemyCitationRepository
from backend.app.deduplication.persistence import SqlAlchemyDeduplicationRepository
from backend.app.documents.persistence import SqlAlchemyDocumentRepository
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.protocols.persistence import SqlAlchemyProtocolRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.reviews.service import ReviewService
from backend.app.screening.domain import (
    ScreeningAdjudication,
    ScreeningAssignment,
    ScreeningDecision,
    ScreeningDecisionKind,
    ScreeningOutcome,
    ScreeningOutcomeKind,
    ScreeningProgression,
    ScreeningQueueItem,
    ScreeningRound,
    ScreeningRoundState,
    ScreeningStage,
)
from backend.app.screening.persistence import SqlAlchemyScreeningRepository
from backend.app.screening.service import ScreeningService

router = APIRouter(prefix="/screening", tags=["screening"])


class RoundRequest(BaseModel):
    review_id: UUID
    name: str = Field(min_length=1, max_length=300)
    stage: ScreeningStage
    required_decisions: int = Field(default=2, ge=1, le=10)
    blinded: bool = True


class RoundResponse(BaseModel):
    id: UUID
    review_id: UUID
    name: str
    stage: ScreeningStage
    sequence: int
    required_decisions: int
    blinded: bool
    state: ScreeningRoundState

    @classmethod
    def from_domain(cls, item: ScreeningRound) -> RoundResponse:
        return cls(
            id=item.id,
            review_id=item.review_id,
            name=item.name,
            stage=item.stage,
            sequence=item.sequence,
            required_decisions=item.required_decisions,
            blinded=item.blinded,
            state=item.state,
        )


class AssignmentRequest(BaseModel):
    article_id: UUID
    reviewer_user_id: UUID


class AssignmentResponse(BaseModel):
    id: UUID
    round_id: UUID
    article_id: UUID
    reviewer_user_id: UUID

    @classmethod
    def from_domain(cls, item: ScreeningAssignment) -> AssignmentResponse:
        return cls(
            id=item.id,
            round_id=item.round_id,
            article_id=item.article_id,
            reviewer_user_id=item.reviewer_user_id,
        )


class DecisionRequest(BaseModel):
    decision: ScreeningDecisionKind
    exclusion_reason: str | None = Field(default=None, max_length=4000)


class DecisionResponse(BaseModel):
    id: UUID
    assignment_id: UUID
    decision: ScreeningDecisionKind
    exclusion_reason: str | None

    @classmethod
    def from_domain(cls, item: ScreeningDecision) -> DecisionResponse:
        return cls(
            id=item.id,
            assignment_id=item.assignment_id,
            decision=item.decision,
            exclusion_reason=item.exclusion_reason,
        )


class QueueItemResponse(BaseModel):
    assignment_id: UUID
    article_id: UUID
    title: str
    abstract: str | None
    own_decision: ScreeningDecisionKind | None
    outcome: ScreeningOutcomeKind | None

    @classmethod
    def from_domain(cls, item: ScreeningQueueItem) -> QueueItemResponse:
        return cls(
            assignment_id=item.assignment.id,
            article_id=item.article.id,
            title=item.article.title,
            abstract=item.article.abstract,
            own_decision=(item.own_decision.decision if item.own_decision is not None else None),
            outcome=item.outcome.outcome if item.outcome is not None else None,
        )


class OutcomeResponse(BaseModel):
    id: UUID
    article_id: UUID
    outcome: ScreeningOutcomeKind
    adjudication: ScreeningDecisionKind | None

    @classmethod
    def from_domain(
        cls, outcome: ScreeningOutcome, adjudication: ScreeningAdjudication | None
    ) -> OutcomeResponse:
        return cls(
            id=outcome.id,
            article_id=outcome.article_id,
            outcome=outcome.outcome,
            adjudication=adjudication.decision if adjudication is not None else None,
        )


class AdjudicationRequest(BaseModel):
    decision: ScreeningDecisionKind
    reason: str = Field(min_length=1, max_length=4000)


class AdjudicationResponse(BaseModel):
    id: UUID
    outcome_id: UUID
    decision: ScreeningDecisionKind
    decided_by_user_id: UUID
    reason: str | None

    @classmethod
    def from_domain(cls, item: ScreeningAdjudication) -> AdjudicationResponse:
        return cls(
            id=item.id,
            outcome_id=item.outcome_id,
            decision=item.decision,
            decided_by_user_id=item.decided_by_user_id,
            reason=item.reason,
        )


class ProgressionRequest(BaseModel):
    target_round_id: UUID


class ProgressionResponse(BaseModel):
    id: UUID
    article_id: UUID
    source_round_id: UUID
    target_round_id: UUID

    @classmethod
    def from_domain(cls, item: ScreeningProgression) -> ProgressionResponse:
        return cls(
            id=item.id,
            article_id=item.article_id,
            source_round_id=item.source_round_id,
            target_round_id=item.target_round_id,
        )


def _service(session: DbSessionDependency) -> ScreeningService:
    return ScreeningService(
        SqlAlchemyScreeningRepository(session),
        SqlAlchemyCitationRepository(session),
        SqlAlchemyDeduplicationRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyProvenanceRepository(session),
    )


def _ai_screening_service(session: DbSessionDependency) -> AIScreeningService:
    identity = SqlAlchemyIdentityRepository(session)
    reviews = ReviewService(SqlAlchemyReviewRepository(session), identity)
    provenance = SqlAlchemyProvenanceRepository(session)
    return AIScreeningService(
        SqlAlchemyAIScreeningRepository(session),
        SqlAlchemyAIRepository(session),
        SqlAlchemyScreeningRepository(session),
        SqlAlchemyCitationRepository(session),
        SqlAlchemyProtocolRepository(session),
        reviews,
        provenance,
        AIExecutionService(
            SqlAlchemyAIRepository(session),
            reviews,
            provenance,
            {"mock": DeterministicMockAIProvider()},
        ),
    )


def _ai_full_text_service(session: DbSessionDependency) -> AIFullTextScreeningService:
    identity = SqlAlchemyIdentityRepository(session)
    reviews_repository = SqlAlchemyReviewRepository(session)
    reviews = ReviewService(reviews_repository, identity)
    provenance = SqlAlchemyProvenanceRepository(session)
    ai_repository = SqlAlchemyAIRepository(session)
    screening_repository = SqlAlchemyScreeningRepository(session)
    citation_repository = SqlAlchemyCitationRepository(session)
    canonical = ScreeningService(
        screening_repository,
        citation_repository,
        SqlAlchemyDeduplicationRepository(session),
        reviews_repository,
        identity,
        provenance,
    )
    return AIFullTextScreeningService(
        SqlAlchemyAIFullTextRepository(session),
        ai_repository,
        SqlAlchemyAIScreeningRepository(session),
        screening_repository,
        SqlAlchemyDocumentRepository(session),
        citation_repository,
        SqlAlchemyProtocolRepository(session),
        reviews,
        provenance,
        AIExecutionService(
            ai_repository,
            reviews,
            provenance,
            {"mock": DeterministicMockAIProvider()},
        ),
        canonical,
    )


@router.post("/rounds", response_model=RoundResponse, status_code=status.HTTP_201_CREATED)
async def create_screening_round(
    payload: RoundRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> RoundResponse:
    item = await _service(session).create_round(
        actor,
        review_id=payload.review_id,
        name=payload.name,
        stage=payload.stage,
        required_decisions=payload.required_decisions,
        blinded=payload.blinded,
    )
    await session.commit()
    return RoundResponse.from_domain(item)


@router.post(
    "/rounds/{round_id}/assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_screening_article(
    payload: AssignmentRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    round_id: Annotated[UUID, Path()],
) -> AssignmentResponse:
    item = await _service(session).assign(
        actor,
        round_id=round_id,
        article_id=payload.article_id,
        reviewer_user_id=payload.reviewer_user_id,
    )
    await session.commit()
    return AssignmentResponse.from_domain(item)


@router.get("/rounds/{round_id}/queue", response_model=list[QueueItemResponse])
async def get_screening_queue(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    round_id: Annotated[UUID, Path()],
) -> list[QueueItemResponse]:
    items = await _service(session).queue(actor, round_id)
    return [QueueItemResponse.from_domain(item) for item in items]


@router.post("/assignments/{assignment_id}/decision", response_model=DecisionResponse)
async def record_screening_decision(
    payload: DecisionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    assignment_id: Annotated[UUID, Path()],
) -> DecisionResponse:
    item = await _service(session).decide(
        actor,
        assignment_id=assignment_id,
        decision=payload.decision,
        exclusion_reason=payload.exclusion_reason,
    )
    await _ai_screening_service(session).record_decision_interaction(actor, item)
    await _ai_full_text_service(session).record_decision_interaction(actor, item)
    await session.commit()
    return DecisionResponse.from_domain(item)


@router.get("/rounds/{round_id}/outcomes", response_model=list[OutcomeResponse])
async def list_screening_outcomes(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    round_id: Annotated[UUID, Path()],
) -> list[OutcomeResponse]:
    outcomes = await _service(session).list_outcomes(actor, round_id)
    return [
        OutcomeResponse.from_domain(outcome, adjudication) for outcome, adjudication in outcomes
    ]


@router.post("/outcomes/{outcome_id}/adjudication", response_model=AdjudicationResponse)
async def adjudicate_screening_conflict(
    payload: AdjudicationRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    outcome_id: Annotated[UUID, Path()],
) -> AdjudicationResponse:
    item = await _service(session).adjudicate(
        actor, outcome_id=outcome_id, decision=payload.decision, reason=payload.reason
    )
    await session.commit()
    return AdjudicationResponse.from_domain(item)


@router.post("/rounds/{round_id}/close", response_model=RoundResponse)
async def close_screening_round(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    round_id: Annotated[UUID, Path()],
) -> RoundResponse:
    item = await _service(session).close(actor, round_id)
    await session.commit()
    return RoundResponse.from_domain(item)


@router.post(
    "/rounds/{source_round_id}/progressions",
    response_model=list[ProgressionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def progress_to_full_text(
    payload: ProgressionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    source_round_id: Annotated[UUID, Path()],
) -> list[ProgressionResponse]:
    items = await _service(session).progress(
        actor,
        source_round_id=source_round_id,
        target_round_id=payload.target_round_id,
    )
    await session.commit()
    return [ProgressionResponse.from_domain(item) for item in items]
