from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    and_,
    func,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.db.base import Base
from backend.app.db.sequence import insert_next_unique_integer
from backend.app.orchestration.contracts import JobState
from backend.app.workflow.domain import JobEventType, WorkflowJob, validate_job_transition
from backend.app.workflow.execution_domain import (
    JobAttemptState,
    JobSignature,
    WorkerHealth,
    WorkerStatus,
    WorkflowJobAttempt,
)
from backend.app.workflow.persistence import (
    JobEventRecord,
    WorkflowJobRecord,
    _job_to_domain,
)
from backend.app.workflow.recovery_domain import (
    FailureClass,
    ReconciliationIssue,
    ReconciliationReport,
    ReconciliationSeverity,
    RecoveryOperationType,
    RetryPolicy,
    WorkflowStepState,
)
from backend.app.workflow.recovery_persistence import (
    WorkflowRecoveryOperationRecord,
    WorkflowStepCheckpointRecord,
    recovery_operation_to_domain,
    step_checkpoint_to_domain,
)


class WorkflowJobAttemptRecord(Base):
    __tablename__ = "workflow_job_attempts"
    __table_args__ = (
        UniqueConstraint("job_id", "attempt_number", name="uq_workflow_attempt_job_number"),
        UniqueConstraint(
            "id",
            "organization_id",
            "review_id",
            name="uq_workflow_attempt_id_tenant_review",
        ),
        UniqueConstraint("lease_token", name="uq_workflow_attempt_lease_token"),
        CheckConstraint("attempt_number > 0", name="ck_workflow_attempt_number"),
        CheckConstraint(
            "state IN ('CLAIMED', 'RUNNING', 'COMPLETED', 'FAILED', 'EXPIRED')",
            name="ck_workflow_attempt_state",
        ),
        ForeignKeyConstraint(
            ["job_id", "organization_id", "review_id"],
            ["workflow_jobs.id", "workflow_jobs.organization_id", "workflow_jobs.review_id"],
            name="fk_workflow_attempt_job_tenant_review",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    attempt_number: Mapped[int] = mapped_column(Integer)
    worker_id: Mapped[str] = mapped_column(String(160))
    lease_token: Mapped[str] = mapped_column(String(160))
    state: Mapped[str] = mapped_column(String(20))
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lease_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    failure_code: Mapped[str | None] = mapped_column(String(80))
    failure_message: Mapped[str | None] = mapped_column(Text)


class WorkflowWorkerRecord(Base):
    __tablename__ = "workflow_workers"
    __table_args__ = (
        CheckConstraint(
            "status IN ('STARTING', 'HEALTHY', 'DRAINING', 'STOPPED', 'FAILED')",
            name="ck_workflow_worker_status",
        ),
        CheckConstraint("capacity > 0 AND capacity <= 100", name="ck_workflow_worker_capacity"),
        CheckConstraint(
            "active_jobs >= 0 AND active_jobs <= capacity",
            name="ck_workflow_worker_active",
        ),
        Index("ix_workflow_workers_heartbeat", "last_heartbeat_at"),
    )

    worker_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    capacity: Mapped[int] = mapped_column(Integer)
    active_jobs: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


Index(
    "ix_workflow_attempts_claimable",
    WorkflowJobAttemptRecord.organization_id,
    WorkflowJobAttemptRecord.state,
    WorkflowJobAttemptRecord.lease_expires_at,
)
Index(
    "ix_workflow_attempts_worker_state",
    WorkflowJobAttemptRecord.worker_id,
    WorkflowJobAttemptRecord.state,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return _now()
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _attempt_to_domain(record: WorkflowJobAttemptRecord) -> WorkflowJobAttempt:
    return WorkflowJobAttempt(
        id=record.id,
        job_id=record.job_id,
        organization_id=record.organization_id,
        review_id=record.review_id,
        attempt_number=record.attempt_number,
        worker_id=record.worker_id,
        lease_token=record.lease_token,
        state=JobAttemptState(record.state),
        claimed_at=_as_utc(record.claimed_at),
        lease_expires_at=_as_utc(record.lease_expires_at),
        deadline_at=_as_utc(record.deadline_at or record.lease_expires_at),
        heartbeat_at=_as_utc(record.heartbeat_at),
        started_at=_as_utc(record.started_at),
        finished_at=_as_utc(record.finished_at) if record.finished_at else None,
        result_snapshot=record.result_snapshot,
        failure_code=record.failure_code,
        failure_message=record.failure_message,
    )


def _worker_to_domain(record: WorkflowWorkerRecord) -> WorkerHealth:
    return WorkerHealth(
        worker_id=record.worker_id,
        status=WorkerStatus(record.status),
        capacity=record.capacity,
        active_jobs=record.active_jobs,
        started_at=_as_utc(record.started_at),
        last_heartbeat_at=_as_utc(record.last_heartbeat_at),
        stopped_at=_as_utc(record.stopped_at) if record.stopped_at else None,
        last_error=record.last_error,
    )


class SqlAlchemyWorkflowExecutionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def register_worker(self, worker_id: str, capacity: int) -> WorkerHealth:
        now = _now()
        statement = (
            select(WorkflowWorkerRecord)
            .where(WorkflowWorkerRecord.worker_id == worker_id)
            .with_for_update()
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        if record is None:
            active_jobs = await self._count_active_jobs(worker_id)
            if active_jobs > capacity:
                raise ConflictError("worker capacity is below its active leased jobs")
            record = WorkflowWorkerRecord(
                worker_id=worker_id,
                status=WorkerStatus.STARTING.value,
                capacity=capacity,
                active_jobs=active_jobs,
                started_at=now,
                last_heartbeat_at=now,
            )
            self._session.add(record)
        else:
            active_jobs = await self._count_active_jobs(worker_id)
            if active_jobs > capacity:
                raise ConflictError("worker capacity is below its active leased jobs")
            record.status = WorkerStatus.STARTING.value
            record.capacity = capacity
            record.active_jobs = active_jobs
            record.stopped_at = None
            record.last_error = None
            record.last_heartbeat_at = now
            record.updated_at = now
        await self._session.flush()
        await self._session.refresh(record)
        return _worker_to_domain(record)

    async def heartbeat_worker(
        self,
        worker_id: str,
        *,
        active_jobs: int | None = None,
        status: WorkerStatus = WorkerStatus.HEALTHY,
    ) -> WorkerHealth:
        record = await self._get_worker_for_update(worker_id)
        if record.status == WorkerStatus.STOPPED.value:
            raise ConflictError("stopped worker cannot heartbeat")
        record.status = status.value
        record.last_heartbeat_at = _now()
        if active_jobs is None:
            active_jobs = await self._count_active_jobs(worker_id)
        if active_jobs > record.capacity:
            raise ConflictError("worker active jobs exceed its bounded capacity")
        record.active_jobs = active_jobs
        record.updated_at = _now()
        await self._session.flush()
        await self._session.refresh(record)
        return _worker_to_domain(record)

    async def stop_worker(self, worker_id: str, last_error: str | None = None) -> WorkerHealth:
        record = await self._get_worker_for_update(worker_id)
        record.status = WorkerStatus.STOPPED.value
        record.stopped_at = _now()
        record.last_heartbeat_at = record.stopped_at
        record.last_error = last_error[:2_000] if last_error else None
        record.active_jobs = await self._count_active_jobs(worker_id)
        record.updated_at = _now()
        await self._session.flush()
        await self._session.refresh(record)
        return _worker_to_domain(record)

    async def get_worker(self, worker_id: str) -> WorkerHealth | None:
        statement = select(WorkflowWorkerRecord).where(WorkflowWorkerRecord.worker_id == worker_id)
        record = (await self._session.execute(statement)).scalar_one_or_none()
        return _worker_to_domain(record) if record is not None else None

    async def list_workers(self) -> list[WorkerHealth]:
        statement = select(WorkflowWorkerRecord).order_by(WorkflowWorkerRecord.worker_id)
        return [_worker_to_domain(record) for record in await self._session.scalars(statement)]

    async def claim_next_job(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
        organization_id: UUID | None,
        review_id: UUID | None,
        task_signatures: tuple[JobSignature, ...],
    ) -> tuple[WorkflowJob, WorkflowJobAttempt] | None:
        worker = await self._get_worker_for_update(worker_id)
        if worker.status in {WorkerStatus.STOPPED.value, WorkerStatus.DRAINING.value}:
            return None
        worker.active_jobs = await self._count_active_jobs(worker_id)
        if worker.active_jobs >= worker.capacity:
            return None

        now = _now()
        conditions = [
            WorkflowJobRecord.state == JobState.QUEUED.value,
            WorkflowJobRecord.attempt < WorkflowJobRecord.max_attempts,
            or_(
                WorkflowJobRecord.next_retry_at.is_(None),
                WorkflowJobRecord.next_retry_at <= now,
            ),
        ]
        if organization_id is not None:
            conditions.append(WorkflowJobRecord.organization_id == organization_id)
        if review_id is not None:
            conditions.append(WorkflowJobRecord.review_id == review_id)
        if task_signatures:
            conditions.append(
                or_(
                    *(
                        and_(
                            WorkflowJobRecord.task_name == task_name,
                            WorkflowJobRecord.task_version == task_version,
                            WorkflowJobRecord.payload_schema == payload_schema,
                            WorkflowJobRecord.payload_version == payload_version,
                        )
                        for (
                            task_name,
                            task_version,
                            payload_schema,
                            payload_version,
                        ) in task_signatures
                    )
                )
            )
        statement = (
            select(WorkflowJobRecord)
            .where(*conditions)
            .order_by(WorkflowJobRecord.created_at, WorkflowJobRecord.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        if record is None:
            worker.last_heartbeat_at = _now()
            worker.updated_at = _now()
            await self._session.flush()
            return None

        previous_state = JobState(record.state)
        record.attempt += 1
        record.state = JobState.RUNNING.value
        record.next_retry_at = None
        record.updated_at = now
        deadline_at = now + timedelta(seconds=record.timeout_seconds)
        attempt = WorkflowJobAttemptRecord(
            job_id=record.id,
            organization_id=record.organization_id,
            review_id=record.review_id,
            attempt_number=record.attempt,
            worker_id=worker_id,
            lease_token=secrets.token_urlsafe(32),
            state=JobAttemptState.CLAIMED.value,
            claimed_at=now,
            lease_expires_at=min(now + timedelta(seconds=lease_seconds), deadline_at),
            deadline_at=deadline_at,
            heartbeat_at=now,
            started_at=now,
        )
        self._session.add(attempt)
        await self._session.flush()
        await self._append_job_event(
            organization_id=record.organization_id,
            job_id=record.id,
            from_state=previous_state,
            to_state=JobState.RUNNING,
            event_type=JobEventType.ATTEMPT_CLAIMED,
            reason=f"worker {worker_id} claimed attempt {record.attempt}",
        )
        await self._sync_step_checkpoint(record, WorkflowStepState.RUNNING)
        worker.status = WorkerStatus.HEALTHY.value
        worker.last_heartbeat_at = now
        worker.active_jobs = await self._count_active_jobs(worker_id)
        worker.updated_at = now
        await self._session.flush()
        await self._session.refresh(record)
        await self._session.refresh(attempt)
        return _job_to_domain(record), _attempt_to_domain(attempt)

    async def get_attempt(
        self,
        organization_id: UUID,
        attempt_id: UUID,
    ) -> tuple[WorkflowJob, WorkflowJobAttempt] | None:
        statement = (
            select(WorkflowJobAttemptRecord, WorkflowJobRecord)
            .join(
                WorkflowJobRecord,
                and_(
                    WorkflowJobRecord.id == WorkflowJobAttemptRecord.job_id,
                    WorkflowJobRecord.organization_id == WorkflowJobAttemptRecord.organization_id,
                    WorkflowJobRecord.review_id == WorkflowJobAttemptRecord.review_id,
                ),
            )
            .where(
                WorkflowJobAttemptRecord.organization_id == organization_id,
                WorkflowJobAttemptRecord.id == attempt_id,
            )
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        attempt, job = row
        return _job_to_domain(job), _attempt_to_domain(attempt)

    async def get_job(self, organization_id: UUID, job_id: UUID) -> WorkflowJob | None:
        statement = select(WorkflowJobRecord).where(
            WorkflowJobRecord.organization_id == organization_id,
            WorkflowJobRecord.id == job_id,
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        return _job_to_domain(record) if record is not None else None

    async def list_attempts(
        self,
        organization_id: UUID,
        review_id: UUID,
    ) -> list[WorkflowJobAttempt]:
        statement = (
            select(WorkflowJobAttemptRecord)
            .where(
                WorkflowJobAttemptRecord.organization_id == organization_id,
                WorkflowJobAttemptRecord.review_id == review_id,
            )
            .order_by(
                WorkflowJobAttemptRecord.claimed_at,
                WorkflowJobAttemptRecord.id,
            )
        )
        return [_attempt_to_domain(record) for record in await self._session.scalars(statement)]

    async def heartbeat_attempt(
        self,
        *,
        worker_id: str,
        attempt_id: UUID,
        lease_token: str,
        lease_seconds: int,
    ) -> WorkflowJobAttempt:
        attempt, job = await self._get_active_attempt_for_update(
            worker_id=worker_id,
            attempt_id=attempt_id,
            lease_token=lease_token,
        )
        now = _now()
        attempt.state = JobAttemptState.RUNNING.value
        attempt.heartbeat_at = now
        deadline_at = _as_utc(attempt.deadline_at or attempt.lease_expires_at)
        attempt.lease_expires_at = min(now + timedelta(seconds=lease_seconds), deadline_at)
        await self._append_job_event(
            organization_id=job.organization_id,
            job_id=job.id,
            from_state=JobState(job.state),
            to_state=JobState(job.state),
            event_type=JobEventType.ATTEMPT_HEARTBEAT,
            reason=f"worker {worker_id} heartbeat attempt {attempt.attempt_number}",
        )
        await self._refresh_worker(worker_id, now)
        await self._sync_step_checkpoint(job, WorkflowStepState.RUNNING)
        await self._session.flush()
        await self._session.refresh(attempt)
        return _attempt_to_domain(attempt)

    async def complete_attempt(
        self,
        *,
        worker_id: str,
        attempt_id: UUID,
        lease_token: str,
        result_snapshot: dict[str, Any],
    ) -> tuple[WorkflowJob, WorkflowJobAttempt]:
        attempt, job = await self._get_active_attempt_for_update(
            worker_id=worker_id,
            attempt_id=attempt_id,
            lease_token=lease_token,
        )
        current_state = JobState(job.state)
        validate_job_transition(current_state, JobState.COMPLETED)
        now = _now()
        attempt.state = JobAttemptState.COMPLETED.value
        attempt.finished_at = now
        attempt.heartbeat_at = now
        attempt.result_snapshot = result_snapshot
        job.state = JobState.COMPLETED.value
        job.updated_at = now
        await self._append_job_event(
            organization_id=job.organization_id,
            job_id=job.id,
            from_state=current_state,
            to_state=JobState.COMPLETED,
            event_type=JobEventType.ATTEMPT_COMPLETED,
            reason=f"worker {worker_id} completed attempt {attempt.attempt_number}",
        )
        await self._sync_step_checkpoint(
            job,
            WorkflowStepState.COMPLETED,
            output_digest=self._digest_json(result_snapshot),
        )
        await self._refresh_worker(worker_id, now)
        await self._session.flush()
        await self._session.refresh(job)
        await self._session.refresh(attempt)
        return _job_to_domain(job), _attempt_to_domain(attempt)

    async def fail_attempt(
        self,
        *,
        worker_id: str,
        attempt_id: UUID,
        lease_token: str,
        failure_code: str,
        failure_message: str,
        failure_class: FailureClass = FailureClass.UNKNOWN,
        requeue: bool | None = None,
    ) -> tuple[WorkflowJob, WorkflowJobAttempt]:
        attempt, job = await self._get_active_attempt_for_update(
            worker_id=worker_id,
            attempt_id=attempt_id,
            lease_token=lease_token,
        )
        current_state = JobState(job.state)
        validate_job_transition(current_state, JobState.FAILED)
        now = _now()
        attempt.state = JobAttemptState.FAILED.value
        attempt.finished_at = now
        attempt.heartbeat_at = now
        attempt.failure_code = failure_code[:80]
        attempt.failure_message = failure_message[:2_000]
        job.failure_class = failure_class.value
        job.state = JobState.FAILED.value
        job.updated_at = now
        await self._append_job_event(
            organization_id=job.organization_id,
            job_id=job.id,
            from_state=current_state,
            to_state=JobState.FAILED,
            event_type=JobEventType.ATTEMPT_FAILED,
            reason=(
                f"worker {worker_id} failed attempt {attempt.attempt_number}: {failure_code[:80]}"
            ),
        )
        policy = RetryPolicy.from_json(
            job.retry_policy,
            fallback_max_attempts=job.max_attempts,
            fallback_timeout_seconds=job.timeout_seconds,
        )
        should_retry = requeue is True or (
            requeue is None and policy.should_retry(failure_class, attempt.attempt_number)
        )
        if should_retry and attempt.attempt_number < job.max_attempts:
            validate_job_transition(JobState.FAILED, JobState.QUEUED)
            job.state = JobState.QUEUED.value
            job.next_retry_at = now + timedelta(
                seconds=policy.delay_for_attempt(attempt.attempt_number)
            )
            job.dead_lettered_at = None
            job.updated_at = now
            await self._append_job_event(
                organization_id=job.organization_id,
                job_id=job.id,
                from_state=JobState.FAILED,
                to_state=JobState.QUEUED,
                event_type=JobEventType.ATTEMPT_REQUEUED,
                reason=(
                    f"attempt {attempt.attempt_number} requeued after failure; retry at "
                    f"{job.next_retry_at.isoformat()}"
                ),
            )
            await self._sync_step_checkpoint(
                job,
                WorkflowStepState.QUEUED,
                failure_class=failure_class,
            )
        elif requeue is None:
            validate_job_transition(JobState.FAILED, JobState.DEAD_LETTERED)
            job.state = JobState.DEAD_LETTERED.value
            job.dead_lettered_at = now
            job.next_retry_at = None
            job.updated_at = now
            await self._append_job_event(
                organization_id=job.organization_id,
                job_id=job.id,
                from_state=JobState.FAILED,
                to_state=JobState.DEAD_LETTERED,
                event_type=JobEventType.ATTEMPT_DEAD_LETTERED,
                reason=(
                    f"attempt {attempt.attempt_number} dead-lettered after "
                    f"{failure_class.value} failure"
                ),
            )
            await self._sync_step_checkpoint(
                job,
                WorkflowStepState.DEAD_LETTERED,
                failure_class=failure_class,
            )
        else:
            job.next_retry_at = None
            await self._sync_step_checkpoint(
                job,
                WorkflowStepState.FAILED,
                failure_class=failure_class,
            )
        await self._refresh_worker(worker_id, now)
        await self._session.flush()
        await self._session.refresh(job)
        await self._session.refresh(attempt)
        return _job_to_domain(job), _attempt_to_domain(attempt)

    async def requeue_job(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        reason: str,
        actor_user_id: UUID | None,
        idempotency_key: str | None = None,
        additional_attempts: int = 0,
    ) -> WorkflowJob:
        operation_key = idempotency_key or (
            f"legacy-requeue:{hashlib.sha256(reason.strip().encode('utf-8')).hexdigest()}"
        )
        existing_operation = await self._get_recovery_operation(
            organization_id=organization_id,
            job_id=job_id,
            operation=RecoveryOperationType.MANUAL_RETRY,
            idempotency_key=operation_key,
        )
        if existing_operation is not None:
            existing_job = await self.get_job(organization_id, job_id)
            if existing_job is None:
                raise ResourceNotFoundError("workflow job was not found")
            return existing_job
        if not 0 <= additional_attempts <= 100:
            raise ValueError("additional attempts must be from 0 through 100")
        statement = (
            select(WorkflowJobRecord)
            .where(
                WorkflowJobRecord.organization_id == organization_id,
                WorkflowJobRecord.id == job_id,
            )
            .with_for_update()
        )
        job = (await self._session.execute(statement)).scalar_one_or_none()
        if job is None:
            raise ResourceNotFoundError("workflow job was not found")
        validate_job_transition(JobState(job.state), JobState.QUEUED)
        if job.attempt >= job.max_attempts and additional_attempts == 0:
            raise ConflictError("workflow job has exhausted its configured attempts")
        current_state = JobState(job.state)
        if additional_attempts:
            job.max_attempts += additional_attempts
            policy = RetryPolicy.from_json(
                job.retry_policy,
                fallback_max_attempts=job.max_attempts - additional_attempts,
                fallback_timeout_seconds=job.timeout_seconds,
            )
            job.retry_policy = RetryPolicy(
                max_attempts=job.max_attempts,
                backoff_seconds=policy.backoff_seconds,
                max_backoff_seconds=policy.max_backoff_seconds,
                timeout_seconds=policy.timeout_seconds,
                retryable_failure_classes=policy.retryable_failure_classes,
            ).to_json()
        job.state = JobState.QUEUED.value
        job.updated_at = _now()
        job.next_retry_at = _now()
        job.dead_lettered_at = None
        job.recovery_count += 1
        await self._append_job_event(
            organization_id=organization_id,
            job_id=job.id,
            from_state=current_state,
            to_state=JobState.QUEUED,
            event_type=JobEventType.MANUAL_RECOVERY,
            actor_user_id=actor_user_id,
            reason=(
                f"{reason[:1_800]} (additional_attempts={additional_attempts}, "
                f"idempotency_key={operation_key})"
            ),
        )
        await self._sync_step_checkpoint(job, WorkflowStepState.QUEUED)
        self._session.add(
            WorkflowRecoveryOperationRecord(
                job_id=job.id,
                organization_id=organization_id,
                review_id=job.review_id,
                operation=RecoveryOperationType.MANUAL_RETRY.value,
                idempotency_key=operation_key,
                actor_user_id=actor_user_id,
                reason=reason[:2_000],
                additional_attempts=additional_attempts,
                resulting_state=job.state,
            )
        )
        await self._session.flush()
        await self._session.refresh(job)
        return _job_to_domain(job)

    async def requeue_expired(self, limit: int = 100) -> int:
        now = _now()
        statement = (
            select(WorkflowJobAttemptRecord)
            .where(
                WorkflowJobAttemptRecord.state.in_(
                    [JobAttemptState.CLAIMED.value, JobAttemptState.RUNNING.value]
                ),
                WorkflowJobAttemptRecord.lease_expires_at <= now,
            )
            .order_by(WorkflowJobAttemptRecord.lease_expires_at, WorkflowJobAttemptRecord.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        records = list(await self._session.scalars(statement))
        for attempt in records:
            await self._expire_attempt(attempt, now)
        if records:
            await self._session.flush()
        return len(records)

    async def resume_job(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        idempotency_key: str,
        actor_user_id: UUID | None,
        reason: str,
    ) -> WorkflowJob:
        existing_operation = await self._get_recovery_operation(
            organization_id=organization_id,
            job_id=job_id,
            operation=RecoveryOperationType.RESUME,
            idempotency_key=idempotency_key,
        )
        if existing_operation is not None:
            existing_job = await self.get_job(organization_id, job_id)
            if existing_job is None:
                raise ResourceNotFoundError("workflow job was not found")
            return existing_job
        statement = (
            select(WorkflowJobRecord)
            .where(
                WorkflowJobRecord.organization_id == organization_id,
                WorkflowJobRecord.id == job_id,
            )
            .with_for_update()
        )
        job = (await self._session.execute(statement)).scalar_one_or_none()
        if job is None:
            raise ResourceNotFoundError("workflow job was not found")
        current_state = JobState(job.state)
        if current_state != JobState.PAUSED:
            raise ConflictError("only paused workflow jobs can be resumed")
        if job.paused_from_state is None:
            raise ConflictError("paused workflow job has no resumable state")
        target_state = JobState(job.paused_from_state)
        validate_job_transition(current_state, target_state)
        job.state = target_state.value
        job.paused_from_state = None
        if target_state == JobState.RUNNING:
            job.attempt += 1
        job.updated_at = _now()
        await self._append_job_event(
            organization_id=organization_id,
            job_id=job.id,
            from_state=current_state,
            to_state=target_state,
            event_type=JobEventType.MANUAL_RECOVERY,
            actor_user_id=actor_user_id,
            reason=f"{reason[:1_800]} (idempotency_key={idempotency_key})",
        )
        await self._sync_step_checkpoint(
            job,
            WorkflowStepState.RUNNING
            if target_state == JobState.RUNNING
            else WorkflowStepState.QUEUED,
        )
        self._session.add(
            WorkflowRecoveryOperationRecord(
                job_id=job.id,
                organization_id=organization_id,
                review_id=job.review_id,
                operation=RecoveryOperationType.RESUME.value,
                idempotency_key=idempotency_key,
                actor_user_id=actor_user_id,
                reason=reason[:2_000],
                additional_attempts=0,
                resulting_state=job.state,
            )
        )
        await self._session.flush()
        await self._session.refresh(job)
        return _job_to_domain(job)

    async def list_step_checkpoints(
        self,
        organization_id: UUID,
        review_id: UUID,
    ) -> list[Any]:
        statement = (
            select(WorkflowStepCheckpointRecord)
            .where(
                WorkflowStepCheckpointRecord.organization_id == organization_id,
                WorkflowStepCheckpointRecord.review_id == review_id,
            )
            .order_by(
                WorkflowStepCheckpointRecord.workflow_run_id,
                WorkflowStepCheckpointRecord.step_order,
                WorkflowStepCheckpointRecord.step_key,
            )
        )
        return [
            step_checkpoint_to_domain(record) for record in await self._session.scalars(statement)
        ]

    async def reconcile(
        self,
        organization_id: UUID,
        review_id: UUID,
    ) -> ReconciliationReport:
        jobs_statement = select(WorkflowJobRecord).where(
            WorkflowJobRecord.organization_id == organization_id,
            WorkflowJobRecord.review_id == review_id,
        )
        attempts_statement = select(WorkflowJobAttemptRecord).where(
            WorkflowJobAttemptRecord.organization_id == organization_id,
            WorkflowJobAttemptRecord.review_id == review_id,
        )
        jobs = list(await self._session.scalars(jobs_statement))
        attempts = list(await self._session.scalars(attempts_statement))
        active_by_job: dict[UUID, list[WorkflowJobAttemptRecord]] = {}
        for attempt in attempts:
            if attempt.state in {
                JobAttemptState.CLAIMED.value,
                JobAttemptState.RUNNING.value,
            }:
                active_by_job.setdefault(attempt.job_id, []).append(attempt)
        issues: list[ReconciliationIssue] = []
        for job in jobs:
            active = active_by_job.get(job.id, [])
            if job.state == JobState.RUNNING.value and not active:
                issues.append(
                    ReconciliationIssue(
                        code="RUNNING_WITHOUT_ACTIVE_ATTEMPT",
                        severity=ReconciliationSeverity.ERROR,
                        job_id=job.id,
                        attempt_id=None,
                        message="running job has no claimed or running attempt",
                    )
                )
            if job.state != JobState.RUNNING.value and active:
                issues.extend(
                    ReconciliationIssue(
                        code="ACTIVE_ATTEMPT_FOR_NON_RUNNING_JOB",
                        severity=ReconciliationSeverity.ERROR,
                        job_id=job.id,
                        attempt_id=attempt.id,
                        message=f"active attempt exists while job is {job.state}",
                    )
                    for attempt in active
                )
            if job.state == JobState.QUEUED.value and job.attempt >= job.max_attempts:
                issues.append(
                    ReconciliationIssue(
                        code="QUEUED_WITH_EXHAUSTED_ATTEMPTS",
                        severity=ReconciliationSeverity.ERROR,
                        job_id=job.id,
                        attempt_id=None,
                        message="queued job cannot be claimed without explicit manual recovery",
                    )
                )
            if job.state == JobState.DEAD_LETTERED.value and job.dead_lettered_at is None:
                issues.append(
                    ReconciliationIssue(
                        code="DEAD_LETTERED_WITHOUT_TIMESTAMP",
                        severity=ReconciliationSeverity.WARNING,
                        job_id=job.id,
                        attempt_id=None,
                        message="dead-lettered job is missing its terminal timestamp",
                    )
                )
            if job.state == JobState.FAILED.value and job.failure_class:
                policy = RetryPolicy.from_json(
                    job.retry_policy,
                    fallback_max_attempts=job.max_attempts,
                    fallback_timeout_seconds=job.timeout_seconds,
                )
                if policy.should_retry(FailureClass(job.failure_class), job.attempt) and (
                    job.next_retry_at is None
                ):
                    issues.append(
                        ReconciliationIssue(
                            code="RETRYABLE_FAILURE_WITHOUT_SCHEDULE",
                            severity=ReconciliationSeverity.WARNING,
                            job_id=job.id,
                            attempt_id=None,
                            message="retryable failure has no next_retry_at schedule",
                        )
                    )
        return ReconciliationReport(
            organization_id=organization_id,
            review_id=review_id,
            generated_at=_now(),
            issues=tuple(issues),
        )

    async def _get_recovery_operation(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        operation: RecoveryOperationType,
        idempotency_key: str,
    ) -> Any | None:
        statement = select(WorkflowRecoveryOperationRecord).where(
            WorkflowRecoveryOperationRecord.organization_id == organization_id,
            WorkflowRecoveryOperationRecord.job_id == job_id,
            WorkflowRecoveryOperationRecord.operation == operation.value,
            WorkflowRecoveryOperationRecord.idempotency_key == idempotency_key,
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        return recovery_operation_to_domain(record) if record is not None else None

    async def _sync_step_checkpoint(
        self,
        job: WorkflowJobRecord,
        state: WorkflowStepState,
        *,
        output_digest: str | None = None,
        failure_class: FailureClass | None = None,
    ) -> None:
        if job.step_key is None or job.step_order is None:
            return
        statement = (
            select(WorkflowStepCheckpointRecord)
            .where(
                WorkflowStepCheckpointRecord.workflow_run_id == job.workflow_run_id,
                WorkflowStepCheckpointRecord.organization_id == job.organization_id,
                WorkflowStepCheckpointRecord.review_id == job.review_id,
                WorkflowStepCheckpointRecord.step_key == job.step_key,
            )
            .with_for_update()
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        now = _now()
        if record is None:
            record = WorkflowStepCheckpointRecord(
                workflow_run_id=job.workflow_run_id,
                job_id=job.id,
                organization_id=job.organization_id,
                review_id=job.review_id,
                step_key=job.step_key,
                step_order=job.step_order,
                definition_hash=job.definition_hash,
                state=state.value,
                checkpoint_version=1,
                output_digest=output_digest,
                failure_class=failure_class.value if failure_class else job.failure_class,
                checkpointed_at=now,
                updated_at=now,
            )
            self._session.add(record)
        else:
            record.job_id = job.id
            record.state = state.value
            record.checkpoint_version += 1
            record.output_digest = output_digest or record.output_digest
            record.failure_class = failure_class.value if failure_class else record.failure_class
            record.checkpointed_at = now
            record.updated_at = now

    @staticmethod
    def _digest_json(value: dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ).hexdigest()

    async def _expire_attempt(self, attempt: WorkflowJobAttemptRecord, now: datetime) -> None:
        statement = (
            select(WorkflowJobRecord)
            .where(
                WorkflowJobRecord.id == attempt.job_id,
                WorkflowJobRecord.organization_id == attempt.organization_id,
                WorkflowJobRecord.review_id == attempt.review_id,
            )
            .with_for_update()
        )
        job = (await self._session.execute(statement)).scalar_one_or_none()
        if job is None:
            raise ResourceNotFoundError("workflow job was not found")
        attempt.state = JobAttemptState.EXPIRED.value
        attempt.finished_at = now
        timed_out = attempt.deadline_at is not None and _as_utc(attempt.deadline_at) <= now
        failure_class = FailureClass.TIMEOUT if timed_out else FailureClass.LEASE_LOST
        attempt.failure_code = "TIMEOUT" if timed_out else "LEASE_EXPIRED"
        attempt.failure_message = (
            "workflow step timed out before completion"
            if timed_out
            else "worker lease expired before completion"
        )
        if job.state == JobState.RUNNING.value:
            job.failure_class = failure_class.value
            job.state = JobState.FAILED.value
            job.updated_at = now
            await self._append_job_event(
                organization_id=job.organization_id,
                job_id=job.id,
                from_state=JobState.RUNNING,
                to_state=JobState.FAILED,
                event_type=JobEventType.ATTEMPT_FAILED,
                reason=f"workflow attempt expired ({failure_class.value})",
            )
            policy = RetryPolicy.from_json(
                job.retry_policy,
                fallback_max_attempts=job.max_attempts,
                fallback_timeout_seconds=job.timeout_seconds,
            )
            if policy.should_retry(failure_class, attempt.attempt_number):
                job.state = JobState.QUEUED.value
                job.next_retry_at = now + timedelta(
                    seconds=policy.delay_for_attempt(attempt.attempt_number)
                )
                job.dead_lettered_at = None
                await self._append_job_event(
                    organization_id=job.organization_id,
                    job_id=job.id,
                    from_state=JobState.FAILED,
                    to_state=JobState.QUEUED,
                    event_type=JobEventType.ATTEMPT_REQUEUED,
                    reason=(f"expired attempt requeued; retry at {job.next_retry_at.isoformat()}"),
                )
                await self._sync_step_checkpoint(
                    job,
                    WorkflowStepState.QUEUED,
                    failure_class=failure_class,
                )
            else:
                job.state = JobState.DEAD_LETTERED.value
                job.dead_lettered_at = now
                job.next_retry_at = None
                await self._append_job_event(
                    organization_id=job.organization_id,
                    job_id=job.id,
                    from_state=JobState.FAILED,
                    to_state=JobState.DEAD_LETTERED,
                    event_type=JobEventType.ATTEMPT_DEAD_LETTERED,
                    reason=f"expired attempt dead-lettered ({failure_class.value})",
                )
                await self._sync_step_checkpoint(
                    job,
                    WorkflowStepState.DEAD_LETTERED,
                    failure_class=failure_class,
                )
        await self._refresh_worker(attempt.worker_id, now)

    async def _get_worker_for_update(self, worker_id: str) -> WorkflowWorkerRecord:
        statement = (
            select(WorkflowWorkerRecord)
            .where(WorkflowWorkerRecord.worker_id == worker_id)
            .with_for_update()
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        if record is None:
            raise ResourceNotFoundError("worker is not registered")
        return record

    async def _count_active_jobs(self, worker_id: str) -> int:
        statement = select(func.count(WorkflowJobAttemptRecord.id)).where(
            WorkflowJobAttemptRecord.worker_id == worker_id,
            WorkflowJobAttemptRecord.state.in_(
                [JobAttemptState.CLAIMED.value, JobAttemptState.RUNNING.value]
            ),
        )
        return int((await self._session.execute(statement)).scalar_one())

    async def _refresh_worker(self, worker_id: str, now: datetime) -> None:
        worker = await self._get_worker_for_update(worker_id)
        worker.active_jobs = await self._count_active_jobs(worker_id)
        worker.last_heartbeat_at = now
        worker.updated_at = now

    async def _get_active_attempt_for_update(
        self,
        *,
        worker_id: str,
        attempt_id: UUID,
        lease_token: str,
    ) -> tuple[WorkflowJobAttemptRecord, WorkflowJobRecord]:
        statement = (
            select(WorkflowJobAttemptRecord, WorkflowJobRecord)
            .join(
                WorkflowJobRecord,
                and_(
                    WorkflowJobRecord.id == WorkflowJobAttemptRecord.job_id,
                    WorkflowJobRecord.organization_id == WorkflowJobAttemptRecord.organization_id,
                    WorkflowJobRecord.review_id == WorkflowJobAttemptRecord.review_id,
                ),
            )
            .where(
                WorkflowJobAttemptRecord.id == attempt_id,
                WorkflowJobAttemptRecord.worker_id == worker_id,
                WorkflowJobAttemptRecord.lease_token == lease_token,
            )
            .with_for_update()
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            raise ResourceNotFoundError("workflow attempt was not found")
        attempt, job = row
        if attempt.state not in {
            JobAttemptState.CLAIMED.value,
            JobAttemptState.RUNNING.value,
        }:
            raise ConflictError("workflow attempt is no longer active")
        now = _now()
        if (
            min(
                _as_utc(attempt.lease_expires_at),
                _as_utc(attempt.deadline_at or attempt.lease_expires_at),
            )
            <= now
        ):
            await self._expire_attempt(attempt, now)
            await self._session.flush()
            raise ConflictError("workflow attempt lease or timeout has expired")
        return attempt, job

    async def _append_job_event(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        from_state: JobState | None,
        to_state: JobState,
        event_type: JobEventType,
        actor_user_id: UUID | None = None,
        reason: str | None,
    ) -> None:
        async def read_next_sequence() -> int:
            statement = select(func.coalesce(func.max(JobEventRecord.sequence), 0)).where(
                JobEventRecord.job_id == job_id,
                JobEventRecord.organization_id == organization_id,
            )
            return int((await self._session.execute(statement)).scalar_one()) + 1

        await insert_next_unique_integer(
            self._session,
            read_next_sequence,
            lambda sequence: JobEventRecord(
                organization_id=organization_id,
                job_id=job_id,
                sequence=sequence,
                event_type=event_type.value,
                from_state=from_state.value if from_state is not None else None,
                to_state=to_state.value,
                actor_user_id=actor_user_id,
                reason=reason[:2_000] if reason else None,
            ),
        )
