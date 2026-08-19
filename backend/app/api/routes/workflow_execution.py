from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.core.errors import AuthorizationError, ResourceNotFoundError
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.identity.service import AuthorizationService
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.reviews.service import ReviewService
from backend.app.workflow.domain import WorkflowJob
from backend.app.workflow.execution_domain import (
    JobAttemptState,
    WorkerClaim,
    WorkerHealth,
    WorkerStatus,
    WorkflowJobAttempt,
)
from backend.app.workflow.execution_persistence import SqlAlchemyWorkflowExecutionRepository
from backend.app.workflow.execution_service import WorkflowExecutionService

router = APIRouter(prefix="/workflow/execution", tags=["workflow-execution"])


class WorkerRegistrationRequest(BaseModel):
    capacity: int = Field(default=1, ge=1, le=100)


class WorkerHeartbeatRequest(BaseModel):
    active_jobs: int | None = Field(default=None, ge=0, le=100)
    status: WorkerStatus = WorkerStatus.HEALTHY


class WorkerClaimRequest(BaseModel):
    review_id: UUID
    lease_seconds: int = Field(default=60, ge=5, le=3_600)


class AttemptHeartbeatRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=160)
    lease_token: str = Field(min_length=20, max_length=160)
    lease_seconds: int = Field(default=60, ge=5, le=3_600)


class AttemptCompletionRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=160)
    lease_token: str = Field(min_length=20, max_length=160)
    result_snapshot: dict[str, object] = Field(default_factory=dict)


class AttemptFailureRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=160)
    lease_token: str = Field(min_length=20, max_length=160)
    failure_code: str = Field(min_length=1, max_length=80)
    failure_message: str = Field(min_length=1, max_length=2_000)
    requeue: bool = True


class JobRequeueRequest(BaseModel):
    review_id: UUID
    reason: str = Field(min_length=1, max_length=2_000)


class WorkerHealthResponse(BaseModel):
    worker_id: str
    status: WorkerStatus
    capacity: int
    active_jobs: int
    started_at: str
    last_heartbeat_at: str
    stopped_at: str | None
    last_error: str | None

    @classmethod
    def from_domain(cls, worker: WorkerHealth) -> WorkerHealthResponse:
        return cls(
            worker_id=worker.worker_id,
            status=worker.status,
            capacity=worker.capacity,
            active_jobs=worker.active_jobs,
            started_at=worker.started_at.isoformat(),
            last_heartbeat_at=worker.last_heartbeat_at.isoformat(),
            stopped_at=worker.stopped_at.isoformat() if worker.stopped_at else None,
            last_error=worker.last_error,
        )


class AttemptResponse(BaseModel):
    id: UUID
    job_id: UUID
    review_id: UUID
    attempt_number: int
    worker_id: str
    state: JobAttemptState
    claimed_at: str
    lease_expires_at: str
    heartbeat_at: str
    started_at: str
    finished_at: str | None
    result_snapshot: dict[str, object] | None
    failure_code: str | None
    failure_message: str | None

    @classmethod
    def from_domain(cls, attempt: WorkflowJobAttempt) -> AttemptResponse:
        return cls(
            id=attempt.id,
            job_id=attempt.job_id,
            review_id=attempt.review_id,
            attempt_number=attempt.attempt_number,
            worker_id=attempt.worker_id,
            state=attempt.state,
            claimed_at=attempt.claimed_at.isoformat(),
            lease_expires_at=attempt.lease_expires_at.isoformat(),
            heartbeat_at=attempt.heartbeat_at.isoformat(),
            started_at=attempt.started_at.isoformat(),
            finished_at=attempt.finished_at.isoformat() if attempt.finished_at else None,
            result_snapshot=attempt.result_snapshot,
            failure_code=attempt.failure_code,
            failure_message=attempt.failure_message,
        )


class WorkerClaimResponse(BaseModel):
    attempt: AttemptResponse
    job_id: UUID
    workflow_run_id: UUID
    review_id: UUID
    task_name: str
    task_version: str
    payload_schema: str
    payload_version: int
    payload: dict[str, object]
    lease_token: str

    @classmethod
    def from_domain(cls, claim: WorkerClaim) -> WorkerClaimResponse:
        return cls(
            attempt=AttemptResponse.from_domain(claim.attempt),
            job_id=claim.job.id,
            workflow_run_id=claim.job.workflow_run_id,
            review_id=claim.job.review_id,
            task_name=claim.job.task_name,
            task_version=claim.job.task_version,
            payload_schema=claim.job.payload_schema,
            payload_version=claim.job.payload_version,
            payload=claim.redacted_payload,
            lease_token=claim.attempt.lease_token,
        )


class JobExecutionResponse(BaseModel):
    job_id: UUID
    attempt: AttemptResponse
    state: str

    @classmethod
    def from_values(
        cls,
        job: WorkflowJob,
        attempt: WorkflowJobAttempt,
    ) -> JobExecutionResponse:
        return cls(
            job_id=job.id,
            attempt=AttemptResponse.from_domain(attempt),
            state=job.state.value,
        )


def _service(session: DbSessionDependency) -> WorkflowExecutionService:
    return WorkflowExecutionService(SqlAlchemyWorkflowExecutionRepository(session))


def _require_worker_controller(actor: ActorContext) -> None:
    AuthorizationService.require(actor, Permission.MANAGE_REVIEW_ACCESS)


async def _require_review_controller(
    actor: ActorContext,
    session: DbSessionDependency,
    review_id: UUID,
) -> None:
    _require_worker_controller(actor)
    review = await ReviewService(
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
    ).get(actor, review_id)
    if (
        not actor.has_permission(Permission.VIEW_ALL_REVIEWS)
        and review.owner_user_id != actor.user_id
    ):
        raise AuthorizationError("only the review owner may operate worker jobs")


@router.get("/workers", response_model=list[WorkerHealthResponse])
async def list_workers(
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> list[WorkerHealthResponse]:
    _require_worker_controller(actor)
    workers = await _service(session).list_workers()
    return [WorkerHealthResponse.from_domain(worker) for worker in workers]


@router.post(
    "/workers/{worker_id}/register",
    response_model=WorkerHealthResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_worker(
    payload: WorkerRegistrationRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    worker_id: Annotated[str, Path(min_length=1, max_length=160)],
) -> WorkerHealthResponse:
    _require_worker_controller(actor)
    worker = await _service(session).register_worker(worker_id, payload.capacity)
    await session.commit()
    return WorkerHealthResponse.from_domain(worker)


@router.post("/workers/{worker_id}/heartbeat", response_model=WorkerHealthResponse)
async def heartbeat_worker(
    payload: WorkerHeartbeatRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    worker_id: Annotated[str, Path(min_length=1, max_length=160)],
) -> WorkerHealthResponse:
    _require_worker_controller(actor)
    worker = await _service(session).heartbeat_worker(
        worker_id,
        active_jobs=payload.active_jobs,
        status=payload.status,
    )
    await session.commit()
    return WorkerHealthResponse.from_domain(worker)


@router.post("/workers/{worker_id}/stop", response_model=WorkerHealthResponse)
async def stop_worker(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    worker_id: Annotated[str, Path(min_length=1, max_length=160)],
) -> WorkerHealthResponse:
    _require_worker_controller(actor)
    worker = await _service(session).stop_worker(worker_id)
    await session.commit()
    return WorkerHealthResponse.from_domain(worker)


@router.post("/workers/{worker_id}/claim", response_model=WorkerClaimResponse | None)
async def claim_worker_job(
    payload: WorkerClaimRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    worker_id: Annotated[str, Path(min_length=1, max_length=160)],
) -> WorkerClaimResponse | None:
    await _require_review_controller(actor, session, payload.review_id)
    claim = await _service(session).claim_next(
        worker_id=worker_id,
        lease_seconds=payload.lease_seconds,
        organization_id=actor.organization_id,
        review_id=payload.review_id,
    )
    await session.commit()
    return WorkerClaimResponse.from_domain(claim) if claim else None


async def _attempt_review(
    actor: ActorContext,
    session: DbSessionDependency,
    attempt_id: UUID,
) -> tuple[WorkflowExecutionService, WorkflowJob, WorkflowJobAttempt]:
    execution = _service(session)
    loaded = await execution.get_attempt(actor.organization_id, attempt_id)
    if loaded is None:
        raise ResourceNotFoundError("workflow attempt was not found")
    job, attempt = loaded
    await _require_review_controller(actor, session, job.review_id)
    return execution, job, attempt


@router.post("/attempts/{attempt_id}/heartbeat", response_model=AttemptResponse)
async def heartbeat_attempt(
    payload: AttemptHeartbeatRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    attempt_id: Annotated[UUID, Path()],
) -> AttemptResponse:
    execution, _, _ = await _attempt_review(actor, session, attempt_id)
    attempt = await execution.heartbeat_attempt(
        worker_id=payload.worker_id,
        attempt_id=attempt_id,
        lease_token=payload.lease_token,
        lease_seconds=payload.lease_seconds,
    )
    await session.commit()
    return AttemptResponse.from_domain(attempt)


@router.post("/attempts/{attempt_id}/complete", response_model=JobExecutionResponse)
async def complete_attempt(
    payload: AttemptCompletionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    attempt_id: Annotated[UUID, Path()],
) -> JobExecutionResponse:
    execution, _, _ = await _attempt_review(actor, session, attempt_id)
    job, attempt = await execution.complete_attempt(
        worker_id=payload.worker_id,
        attempt_id=attempt_id,
        lease_token=payload.lease_token,
        result_snapshot=payload.result_snapshot,
    )
    await session.commit()
    return JobExecutionResponse.from_values(job, attempt)


@router.post("/attempts/{attempt_id}/fail", response_model=JobExecutionResponse)
async def fail_attempt(
    payload: AttemptFailureRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    attempt_id: Annotated[UUID, Path()],
) -> JobExecutionResponse:
    execution, _, _ = await _attempt_review(actor, session, attempt_id)
    job, attempt = await execution.fail_attempt(
        worker_id=payload.worker_id,
        attempt_id=attempt_id,
        lease_token=payload.lease_token,
        failure_code=payload.failure_code,
        failure_message=payload.failure_message,
        requeue=payload.requeue,
    )
    await session.commit()
    return JobExecutionResponse.from_values(job, attempt)


@router.get(
    "/reviews/{review_id}/attempts",
    response_model=list[AttemptResponse],
)
async def list_attempts(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[AttemptResponse]:
    review = await ReviewService(
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
    ).get(actor, review_id)
    _ = review
    attempts = await _service(session).list_attempts(actor.organization_id, review_id)
    return [AttemptResponse.from_domain(attempt) for attempt in attempts]


@router.post("/jobs/{job_id}/requeue", response_model=dict[str, object])
async def requeue_job(
    payload: JobRequeueRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    job_id: Annotated[UUID, Path()],
) -> dict[str, object]:
    await _require_review_controller(actor, session, payload.review_id)
    execution = _service(session)
    existing = await execution.get_job(actor.organization_id, job_id)
    if existing is None or existing.review_id != payload.review_id:
        raise ResourceNotFoundError("workflow job was not found")
    job = await execution.requeue_job(
        organization_id=actor.organization_id,
        job_id=job_id,
        reason=payload.reason,
        actor_user_id=actor.user_id,
    )
    await session.commit()
    return {"job_id": str(job.id), "state": job.state.value}
