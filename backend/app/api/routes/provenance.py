from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.provenance.domain import (
    AIRun,
    AIRunStatus,
    AuditEvent,
    PromptVersion,
    ProvenanceActorKind,
    ScientificProvenance,
    VerificationState,
)
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.persistence import SqlAlchemyReviewRepository

router = APIRouter(prefix="/provenance", tags=["provenance"])


class PromptVersionRequest(BaseModel):
    prompt_key: str = Field(min_length=1, max_length=120)
    template: str = Field(min_length=1, max_length=100_000)
    output_schema: dict[str, Any] = Field(default_factory=dict)


class PromptVersionResponse(BaseModel):
    id: UUID
    prompt_key: str
    version: int

    @classmethod
    def from_domain(cls, prompt: PromptVersion) -> PromptVersionResponse:
        return cls(id=prompt.id, prompt_key=prompt.prompt_key, version=prompt.version)


class AIRunRequest(BaseModel):
    review_id: UUID
    prompt_version_id: UUID
    provider: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=160)
    model_version: str = Field(min_length=1, max_length=100)
    parameters: dict[str, Any] = Field(default_factory=dict)
    input_snapshot: dict[str, Any]
    output_snapshot: dict[str, Any] | None = None
    status: AIRunStatus
    usage: dict[str, Any] = Field(default_factory=dict)


class AIRunResponse(BaseModel):
    id: UUID
    review_id: UUID
    prompt_version_id: UUID
    provider: str
    model_name: str
    model_version: str
    status: AIRunStatus

    @classmethod
    def from_domain(cls, run: AIRun) -> AIRunResponse:
        return cls(
            id=run.id,
            review_id=run.review_id,
            prompt_version_id=run.prompt_version_id,
            provider=run.provider,
            model_name=run.model_name,
            model_version=run.model_version,
            status=run.status,
        )


class ProvenanceRequest(BaseModel):
    subject_type: str = Field(min_length=1, max_length=120)
    subject_id: UUID
    source_type: str | None = Field(default=None, min_length=1, max_length=120)
    source_id: UUID | None = None
    source_locator: dict[str, Any] = Field(default_factory=dict)
    method_name: str = Field(min_length=1, max_length=160)
    method_version: str = Field(min_length=1, max_length=100)
    actor_kind: ProvenanceActorKind
    ai_run_id: UUID | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    verification_state: VerificationState = VerificationState.UNVERIFIED


class ProvenanceResponse(BaseModel):
    id: UUID
    review_id: UUID
    subject_type: str
    subject_id: UUID
    source_type: str | None
    source_id: UUID | None
    source_locator: dict[str, Any]
    method_name: str
    method_version: str
    actor_kind: ProvenanceActorKind
    actor_user_id: UUID | None
    ai_run_id: UUID | None
    confidence: float | None
    verification_state: VerificationState

    @classmethod
    def from_domain(cls, record: ScientificProvenance) -> ProvenanceResponse:
        return cls(
            id=record.id,
            review_id=record.review_id,
            subject_type=record.subject_type,
            subject_id=record.subject_id,
            source_type=record.source_type,
            source_id=record.source_id,
            source_locator=record.source_locator,
            method_name=record.method_name,
            method_version=record.method_version,
            actor_kind=record.actor_kind,
            actor_user_id=record.actor_user_id,
            ai_run_id=record.ai_run_id,
            confidence=record.confidence,
            verification_state=record.verification_state,
        )


class AuditEventResponse(BaseModel):
    id: UUID
    review_id: UUID | None
    entity_type: str
    entity_id: UUID
    action: str
    actor_user_id: UUID
    before_snapshot: dict[str, Any] | None
    after_snapshot: dict[str, Any] | None
    reason: str | None

    @classmethod
    def from_domain(cls, event: AuditEvent) -> AuditEventResponse:
        return cls(
            id=event.id,
            review_id=event.review_id,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            action=event.action,
            actor_user_id=event.actor_user_id,
            before_snapshot=event.before_snapshot,
            after_snapshot=event.after_snapshot,
            reason=event.reason,
        )


def _service(session: DbSessionDependency) -> ProvenanceService:
    return ProvenanceService(
        SqlAlchemyProvenanceRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
    )


@router.post("/prompts", response_model=PromptVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt_version(
    payload: PromptVersionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> PromptVersionResponse:
    prompt = await _service(session).create_prompt_version(
        actor,
        prompt_key=payload.prompt_key,
        template=payload.template,
        output_schema=payload.output_schema,
    )
    await session.commit()
    return PromptVersionResponse.from_domain(prompt)


@router.post("/ai-runs", response_model=AIRunResponse, status_code=status.HTTP_201_CREATED)
async def record_ai_run(
    payload: AIRunRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> AIRunResponse:
    run = await _service(session).record_ai_run(
        actor,
        review_id=payload.review_id,
        prompt_version_id=payload.prompt_version_id,
        provider=payload.provider,
        model_name=payload.model_name,
        model_version=payload.model_version,
        parameters=payload.parameters,
        input_snapshot=payload.input_snapshot,
        output_snapshot=payload.output_snapshot,
        status=payload.status,
        usage=payload.usage,
    )
    await session.commit()
    return AIRunResponse.from_domain(run)


@router.post(
    "/reviews/{review_id}/records",
    response_model=ProvenanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_scientific_provenance(
    payload: ProvenanceRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> ProvenanceResponse:
    record = await _service(session).record_provenance(
        actor,
        review_id=review_id,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        source_type=payload.source_type,
        source_id=payload.source_id,
        source_locator=payload.source_locator,
        method_name=payload.method_name,
        method_version=payload.method_version,
        actor_kind=payload.actor_kind,
        ai_run_id=payload.ai_run_id,
        confidence=payload.confidence,
        verification_state=payload.verification_state,
    )
    await session.commit()
    return ProvenanceResponse.from_domain(record)


@router.get("/reviews/{review_id}/records", response_model=list[ProvenanceResponse])
async def list_scientific_provenance(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[ProvenanceResponse]:
    records = await _service(session).list_provenance(actor, review_id)
    return [ProvenanceResponse.from_domain(record) for record in records]


@router.get("/reviews/{review_id}/audit", response_model=list[AuditEventResponse])
async def list_review_audit_events(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[AuditEventResponse]:
    events = await _service(session).list_audit_events(actor, review_id)
    return [AuditEventResponse.from_domain(event) for event in events]
