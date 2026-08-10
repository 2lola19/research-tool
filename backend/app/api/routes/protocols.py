from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.protocols.domain import (
    ProtocolDecision,
    ProtocolDecisionKind,
    ProtocolVersion,
)
from backend.app.protocols.persistence import SqlAlchemyProtocolRepository
from backend.app.protocols.service import ProtocolService
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository

router = APIRouter(prefix="/protocols", tags=["protocols"])


class ResearchQuestion(BaseModel):
    population: str = Field(min_length=1, max_length=4000)
    intervention: str = Field(min_length=1, max_length=4000)
    comparator: str | None = Field(default=None, max_length=4000)
    outcomes: list[str] = Field(min_length=1, max_length=100)


class EligibilityCriteria(BaseModel):
    inclusion: list[str] = Field(min_length=1, max_length=200)
    exclusion: list[str] = Field(min_length=1, max_length=200)


class ProtocolContent(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    objective: str = Field(min_length=1, max_length=10_000)
    research_question: ResearchQuestion
    eligibility: EligibilityCriteria
    primary_outcomes: list[str] = Field(min_length=1, max_length=100)
    secondary_outcomes: list[str] = Field(default_factory=list, max_length=100)
    study_designs: list[str] = Field(min_length=1, max_length=100)
    analysis_plan: str = Field(min_length=1, max_length=20_000)


class ProtocolVersionRequest(BaseModel):
    review_id: UUID
    content: ProtocolContent


class ProtocolDecisionRequest(BaseModel):
    decision: ProtocolDecisionKind
    reason: str | None = Field(default=None, max_length=4000)


class ProtocolVersionResponse(BaseModel):
    id: UUID
    review_id: UUID
    version: int
    content: ProtocolContent
    content_hash: str
    decision: ProtocolDecisionKind | None
    decided_by_user_id: UUID | None

    @classmethod
    def from_domain(
        cls, version: ProtocolVersion, decision: ProtocolDecision | None = None
    ) -> ProtocolVersionResponse:
        return cls(
            id=version.id,
            review_id=version.review_id,
            version=version.version,
            content=ProtocolContent.model_validate(version.content),
            content_hash=version.content_hash,
            decision=decision.decision if decision is not None else None,
            decided_by_user_id=(decision.decided_by_user_id if decision is not None else None),
        )


class ProtocolDecisionResponse(BaseModel):
    id: UUID
    protocol_version_id: UUID
    decision: ProtocolDecisionKind
    decided_by_user_id: UUID
    reason: str | None

    @classmethod
    def from_domain(cls, decision: ProtocolDecision) -> ProtocolDecisionResponse:
        return cls(
            id=decision.id,
            protocol_version_id=decision.protocol_version_id,
            decision=decision.decision,
            decided_by_user_id=decision.decided_by_user_id,
            reason=decision.reason,
        )


def _service(session: DbSessionDependency) -> ProtocolService:
    return ProtocolService(
        SqlAlchemyProtocolRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyProvenanceRepository(session),
    )


@router.post(
    "/versions",
    response_model=ProtocolVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_protocol_version(
    payload: ProtocolVersionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> ProtocolVersionResponse:
    version = await _service(session).create_version(
        actor,
        review_id=payload.review_id,
        content=payload.content.model_dump(mode="json"),
    )
    await session.commit()
    return ProtocolVersionResponse.from_domain(version)


@router.get("/reviews/{review_id}/versions", response_model=list[ProtocolVersionResponse])
async def list_protocol_versions(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[ProtocolVersionResponse]:
    versions = await _service(session).list_versions(actor, review_id)
    return [
        ProtocolVersionResponse.from_domain(version, decision) for version, decision in versions
    ]


@router.post(
    "/versions/{protocol_version_id}/decision",
    response_model=ProtocolDecisionResponse,
)
async def decide_protocol_version(
    payload: ProtocolDecisionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    protocol_version_id: Annotated[UUID, Path()],
) -> ProtocolDecisionResponse:
    decision = await _service(session).decide(
        actor,
        protocol_version_id=protocol_version_id,
        decision=payload.decision,
        reason=payload.reason,
    )
    await session.commit()
    return ProtocolDecisionResponse.from_domain(decision)
