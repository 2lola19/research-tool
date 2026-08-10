from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.orchestration.contracts import JobState
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.workflow.domain import (
    CheckpointState,
    HumanCheckpoint,
    JobEvent,
    WorkflowJob,
    WorkflowRun,
)
from backend.app.workflow.persistence import SqlAlchemyWorkflowRepository
from backend.app.workflow.service import WorkflowService

router = APIRouter(prefix="/workflow", tags=["workflow"])


class WorkflowRunRequest(BaseModel):
    review_id: UUID
    workflow_name: str = Field(min_length=1, max_length=120)
    workflow_version: str = Field(min_length=1, max_length=50)
    idempotency_key: str = Field(min_length=1, max_length=200)


class WorkflowRunResponse(BaseModel):
    id: UUID
    review_id: UUID
    workflow_name: str
    workflow_version: str
    idempotency_key: str
    state: str

    @classmethod
    def from_domain(cls, run: WorkflowRun) -> WorkflowRunResponse:
        return cls(
            id=run.id,
            review_id=run.review_id,
            workflow_name=run.workflow_name,
            workflow_version=run.workflow_version,
            idempotency_key=run.idempotency_key,
            state=run.state.value,
        )


class JobSubmissionRequest(BaseModel):
    review_id: UUID
    task_name: str = Field(min_length=1, max_length=120)
    task_version: str = Field(min_length=1, max_length=50)
    idempotency_key: str = Field(min_length=1, max_length=200)
    payload: dict[str, object] = Field(default_factory=dict)


class JobTransitionRequest(BaseModel):
    target_state: JobState
    reason: str | None = Field(default=None, max_length=2000)


class WorkflowJobResponse(BaseModel):
    id: UUID
    workflow_run_id: UUID
    review_id: UUID
    task_name: str
    task_version: str
    idempotency_key: str
    state: JobState
    paused_from_state: JobState | None
    attempt: int

    @classmethod
    def from_domain(cls, job: WorkflowJob) -> WorkflowJobResponse:
        return cls(
            id=job.id,
            workflow_run_id=job.workflow_run_id,
            review_id=job.review_id,
            task_name=job.task_name,
            task_version=job.task_version,
            idempotency_key=job.idempotency_key,
            state=job.state,
            paused_from_state=job.paused_from_state,
            attempt=job.attempt,
        )


class JobEventResponse(BaseModel):
    id: UUID
    sequence: int
    event_type: str
    from_state: JobState | None
    to_state: JobState
    actor_user_id: UUID | None
    reason: str | None

    @classmethod
    def from_domain(cls, event: JobEvent) -> JobEventResponse:
        return cls(
            id=event.id,
            sequence=event.sequence,
            event_type=event.event_type.value,
            from_state=event.from_state,
            to_state=event.to_state,
            actor_user_id=event.actor_user_id,
            reason=event.reason,
        )


class CheckpointRequest(BaseModel):
    request_message: str = Field(min_length=1, max_length=4000)


class CheckpointDecisionRequest(BaseModel):
    decision: CheckpointState
    decision_note: str | None = Field(default=None, max_length=4000)


class CheckpointResponse(BaseModel):
    id: UUID
    job_id: UUID
    review_id: UUID
    state: CheckpointState
    request_message: str
    requested_by_user_id: UUID
    decision_note: str | None
    resolved_by_user_id: UUID | None

    @classmethod
    def from_domain(cls, checkpoint: HumanCheckpoint) -> CheckpointResponse:
        return cls(
            id=checkpoint.id,
            job_id=checkpoint.job_id,
            review_id=checkpoint.review_id,
            state=checkpoint.state,
            request_message=checkpoint.request_message,
            requested_by_user_id=checkpoint.requested_by_user_id,
            decision_note=checkpoint.decision_note,
            resolved_by_user_id=checkpoint.resolved_by_user_id,
        )


def _service(session: DbSessionDependency) -> WorkflowService:
    return WorkflowService(
        SqlAlchemyWorkflowRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
    )


@router.post("/runs", response_model=WorkflowRunResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow_run(
    payload: WorkflowRunRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> WorkflowRunResponse:
    run = await _service(session).create_run(
        actor,
        review_id=payload.review_id,
        workflow_name=payload.workflow_name,
        workflow_version=payload.workflow_version,
        idempotency_key=payload.idempotency_key,
    )
    await session.commit()
    return WorkflowRunResponse.from_domain(run)


@router.post(
    "/runs/{workflow_run_id}/jobs",
    response_model=WorkflowJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_workflow_job(
    payload: JobSubmissionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    workflow_run_id: Annotated[UUID, Path()],
) -> WorkflowJobResponse:
    job = await _service(session).submit_job(
        actor,
        review_id=payload.review_id,
        workflow_run_id=workflow_run_id,
        task_name=payload.task_name,
        task_version=payload.task_version,
        idempotency_key=payload.idempotency_key,
        payload=payload.payload,
    )
    await session.commit()
    return WorkflowJobResponse.from_domain(job)


@router.post("/jobs/{job_id}/transitions", response_model=WorkflowJobResponse)
async def transition_workflow_job(
    payload: JobTransitionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    job_id: Annotated[UUID, Path()],
) -> WorkflowJobResponse:
    job = await _service(session).transition_job(
        actor,
        job_id,
        payload.target_state,
        payload.reason,
    )
    await session.commit()
    return WorkflowJobResponse.from_domain(job)


@router.get("/jobs/{job_id}/events", response_model=list[JobEventResponse])
async def list_workflow_job_events(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    job_id: Annotated[UUID, Path()],
) -> list[JobEventResponse]:
    events = await _service(session).list_events(actor, job_id)
    return [JobEventResponse.from_domain(event) for event in events]


@router.post(
    "/jobs/{job_id}/checkpoints",
    response_model=CheckpointResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_human_checkpoint(
    payload: CheckpointRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    job_id: Annotated[UUID, Path()],
) -> CheckpointResponse:
    checkpoint = await _service(session).request_checkpoint(actor, job_id, payload.request_message)
    await session.commit()
    return CheckpointResponse.from_domain(checkpoint)


@router.post(
    "/checkpoints/{checkpoint_id}/decision",
    response_model=CheckpointResponse,
)
async def resolve_human_checkpoint(
    payload: CheckpointDecisionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    checkpoint_id: Annotated[UUID, Path()],
) -> CheckpointResponse:
    checkpoint = await _service(session).resolve_checkpoint(
        actor,
        checkpoint_id,
        payload.decision,
        payload.decision_note,
    )
    await session.commit()
    return CheckpointResponse.from_domain(checkpoint)
