from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.db.base import Base
from backend.app.db.sequence import insert_next_unique_integer
from backend.app.orchestration.contracts import JobState
from backend.app.workflow.domain import (
    CheckpointState,
    HumanCheckpoint,
    JobEvent,
    JobEventType,
    WorkflowJob,
    WorkflowRun,
    WorkflowRunState,
    validate_job_transition,
)


class WorkflowRunRecord(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "review_id",
            "idempotency_key",
            name="uq_workflow_runs_tenant_idempotency",
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            "review_id",
            name="uq_workflow_runs_id_tenant_review",
        ),
        CheckConstraint(
            "state IN ('ACTIVE', 'PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED')",
            name="ck_workflow_runs_state",
        ),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_workflow_runs_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_workflow_runs_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    workflow_name: Mapped[str] = mapped_column(String(120))
    workflow_version: Mapped[str] = mapped_column(String(50))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(20))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class WorkflowJobRecord(Base):
    __tablename__ = "workflow_jobs"
    __table_args__ = (
        UniqueConstraint(
            "workflow_run_id",
            "idempotency_key",
            name="uq_workflow_jobs_run_idempotency",
        ),
        UniqueConstraint("id", "organization_id", name="uq_workflow_jobs_id_org"),
        UniqueConstraint(
            "id",
            "organization_id",
            "review_id",
            name="uq_workflow_jobs_id_org_review",
        ),
        CheckConstraint(
            "state IN ('NOT_STARTED', 'QUEUED', 'RUNNING', 'AWAITING_HUMAN', "
            "'COMPLETED', 'FAILED', 'PAUSED', 'CANCELLED')",
            name="ck_workflow_jobs_state",
        ),
        CheckConstraint(
            "paused_from_state IS NULL OR paused_from_state IN "
            "('QUEUED', 'RUNNING', 'AWAITING_HUMAN')",
            name="ck_workflow_jobs_paused_from_state",
        ),
        CheckConstraint("attempt >= 0", name="ck_workflow_jobs_attempt"),
        ForeignKeyConstraint(
            ["workflow_run_id", "organization_id", "review_id"],
            [
                "workflow_runs.id",
                "workflow_runs.organization_id",
                "workflow_runs.review_id",
            ],
            name="fk_workflow_jobs_run_tenant_review",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_run_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    task_name: Mapped[str] = mapped_column(String(120))
    task_version: Mapped[str] = mapped_column(String(50))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(20))
    paused_from_state: Mapped[str | None] = mapped_column(String(20))
    attempt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class JobEventRecord(Base):
    __tablename__ = "job_events"
    __table_args__ = (
        UniqueConstraint("job_id", "sequence", name="uq_job_events_job_sequence"),
        ForeignKeyConstraint(
            ["job_id", "organization_id"],
            ["workflow_jobs.id", "workflow_jobs.organization_id"],
            name="fk_job_events_job_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_job_events_actor_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    job_id: Mapped[UUID] = mapped_column()
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(40))
    from_state: Mapped[str | None] = mapped_column(String(20))
    to_state: Mapped[str] = mapped_column(String(20))
    actor_user_id: Mapped[UUID | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class HumanCheckpointRecord(Base):
    __tablename__ = "human_checkpoints"
    __table_args__ = (
        CheckConstraint(
            "state IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')",
            name="ck_human_checkpoints_state",
        ),
        CheckConstraint(
            "(resolved_at IS NULL AND resolved_by_user_id IS NULL AND state = 'PENDING') OR "
            "(resolved_at IS NOT NULL AND resolved_by_user_id IS NOT NULL "
            "AND state IN ('APPROVED', 'REJECTED', 'CANCELLED'))",
            name="ck_human_checkpoints_resolution",
        ),
        ForeignKeyConstraint(
            ["job_id", "organization_id", "review_id"],
            ["workflow_jobs.id", "workflow_jobs.organization_id", "workflow_jobs.review_id"],
            name="fk_human_checkpoints_job_tenant_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "requested_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_human_checkpoints_requester_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "resolved_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_human_checkpoints_resolver_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    state: Mapped[str] = mapped_column(String(20))
    request_message: Mapped[str] = mapped_column(Text)
    requested_by_user_id: Mapped[UUID] = mapped_column()
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    decision_note: Mapped[str | None] = mapped_column(Text)
    resolved_by_user_id: Mapped[UUID | None] = mapped_column()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def _run_to_domain(record: WorkflowRunRecord) -> WorkflowRun:
    now = datetime.now(UTC)
    return WorkflowRun(
        id=record.id,
        organization_id=record.organization_id,
        review_id=record.review_id,
        workflow_name=record.workflow_name,
        workflow_version=record.workflow_version,
        idempotency_key=record.idempotency_key,
        state=WorkflowRunState(record.state),
        created_by_user_id=record.created_by_user_id,
        created_at=record.created_at or now,
        updated_at=record.updated_at or now,
    )


def _job_to_domain(record: WorkflowJobRecord) -> WorkflowJob:
    now = datetime.now(UTC)
    return WorkflowJob(
        id=record.id,
        workflow_run_id=record.workflow_run_id,
        organization_id=record.organization_id,
        review_id=record.review_id,
        task_name=record.task_name,
        task_version=record.task_version,
        idempotency_key=record.idempotency_key,
        payload=record.payload,
        state=JobState(record.state),
        paused_from_state=(
            JobState(record.paused_from_state) if record.paused_from_state is not None else None
        ),
        attempt=record.attempt,
        created_at=record.created_at or now,
        updated_at=record.updated_at or now,
    )


def _event_to_domain(record: JobEventRecord) -> JobEvent:
    return JobEvent(
        id=record.id,
        job_id=record.job_id,
        sequence=record.sequence,
        event_type=JobEventType(record.event_type),
        from_state=JobState(record.from_state) if record.from_state is not None else None,
        to_state=JobState(record.to_state),
        actor_user_id=record.actor_user_id,
        reason=record.reason,
        occurred_at=record.occurred_at or datetime.now(UTC),
    )


def _checkpoint_to_domain(record: HumanCheckpointRecord) -> HumanCheckpoint:
    return HumanCheckpoint(
        id=record.id,
        job_id=record.job_id,
        organization_id=record.organization_id,
        review_id=record.review_id,
        state=CheckpointState(record.state),
        request_message=record.request_message,
        requested_by_user_id=record.requested_by_user_id,
        requested_at=record.requested_at or datetime.now(UTC),
        decision_note=record.decision_note,
        resolved_by_user_id=record.resolved_by_user_id,
        resolved_at=record.resolved_at,
    )


class SqlAlchemyWorkflowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_run(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        workflow_name: str,
        workflow_version: str,
        idempotency_key: str,
        created_by_user_id: UUID,
    ) -> WorkflowRun:
        record = WorkflowRunRecord(
            organization_id=organization_id,
            review_id=review_id,
            workflow_name=workflow_name,
            workflow_version=workflow_version,
            idempotency_key=idempotency_key,
            state=WorkflowRunState.ACTIVE.value,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _run_to_domain(record)

    async def get_run_by_idempotency(
        self,
        organization_id: UUID,
        review_id: UUID,
        idempotency_key: str,
    ) -> WorkflowRun | None:
        statement = select(WorkflowRunRecord).where(
            WorkflowRunRecord.organization_id == organization_id,
            WorkflowRunRecord.review_id == review_id,
            WorkflowRunRecord.idempotency_key == idempotency_key,
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        return _run_to_domain(record) if record is not None else None

    async def create_job(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        workflow_run_id: UUID,
        task_name: str,
        task_version: str,
        idempotency_key: str,
        payload: dict[str, Any],
        actor_user_id: UUID | None,
    ) -> WorkflowJob:
        record = WorkflowJobRecord(
            workflow_run_id=workflow_run_id,
            organization_id=organization_id,
            review_id=review_id,
            task_name=task_name,
            task_version=task_version,
            idempotency_key=idempotency_key,
            payload=payload,
            state=JobState.QUEUED.value,
            attempt=0,
        )
        self._session.add(record)
        await self._session.flush()
        self._session.add(
            JobEventRecord(
                organization_id=organization_id,
                job_id=record.id,
                sequence=1,
                event_type=JobEventType.SUBMITTED.value,
                from_state=None,
                to_state=JobState.QUEUED.value,
                actor_user_id=actor_user_id,
                reason=None,
            )
        )
        await self._session.flush()
        await self._session.refresh(record)
        return _job_to_domain(record)

    async def get_run(
        self,
        organization_id: UUID,
        review_id: UUID,
        workflow_run_id: UUID,
    ) -> WorkflowRun | None:
        statement = select(WorkflowRunRecord).where(
            WorkflowRunRecord.organization_id == organization_id,
            WorkflowRunRecord.review_id == review_id,
            WorkflowRunRecord.id == workflow_run_id,
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        return _run_to_domain(record) if record is not None else None

    async def list_runs(self, organization_id: UUID, review_id: UUID) -> list[WorkflowRun]:
        statement = (
            select(WorkflowRunRecord)
            .where(
                WorkflowRunRecord.organization_id == organization_id,
                WorkflowRunRecord.review_id == review_id,
            )
            .order_by(WorkflowRunRecord.created_at, WorkflowRunRecord.id)
        )
        records = (await self._session.scalars(statement)).all()
        return [_run_to_domain(record) for record in records]

    async def get_job_by_idempotency(
        self,
        organization_id: UUID,
        workflow_run_id: UUID,
        idempotency_key: str,
    ) -> WorkflowJob | None:
        statement = select(WorkflowJobRecord).where(
            WorkflowJobRecord.organization_id == organization_id,
            WorkflowJobRecord.workflow_run_id == workflow_run_id,
            WorkflowJobRecord.idempotency_key == idempotency_key,
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        return _job_to_domain(record) if record is not None else None

    async def get_job(self, organization_id: UUID, job_id: UUID) -> WorkflowJob | None:
        statement = select(WorkflowJobRecord).where(
            WorkflowJobRecord.organization_id == organization_id,
            WorkflowJobRecord.id == job_id,
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        return _job_to_domain(record) if record is not None else None

    async def list_jobs(self, organization_id: UUID, review_id: UUID) -> list[WorkflowJob]:
        statement = (
            select(WorkflowJobRecord)
            .where(
                WorkflowJobRecord.organization_id == organization_id,
                WorkflowJobRecord.review_id == review_id,
            )
            .order_by(WorkflowJobRecord.created_at, WorkflowJobRecord.id)
        )
        records = (await self._session.scalars(statement)).all()
        return [_job_to_domain(record) for record in records]

    async def transition_job(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        target_state: JobState,
        actor_user_id: UUID | None,
        reason: str | None,
    ) -> WorkflowJob:
        statement = (
            select(WorkflowJobRecord)
            .where(
                WorkflowJobRecord.organization_id == organization_id,
                WorkflowJobRecord.id == job_id,
            )
            .with_for_update()
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        if record is None:
            raise ResourceNotFoundError("workflow job was not found")
        current_state = JobState(record.state)
        validate_job_transition(current_state, target_state)
        if target_state == JobState.PAUSED:
            record.paused_from_state = current_state.value
        elif current_state == JobState.PAUSED:
            record.paused_from_state = None
        if target_state == JobState.RUNNING:
            record.attempt += 1
        record.state = target_state.value
        record.updated_at = datetime.now(UTC)

        async def read_next_sequence() -> int:
            sequence_statement = select(func.coalesce(func.max(JobEventRecord.sequence), 0)).where(
                JobEventRecord.job_id == job_id,
                JobEventRecord.organization_id == organization_id,
            )
            return int((await self._session.execute(sequence_statement)).scalar_one()) + 1

        await insert_next_unique_integer(
            self._session,
            read_next_sequence,
            lambda sequence: JobEventRecord(
                organization_id=organization_id,
                job_id=job_id,
                sequence=sequence,
                event_type=JobEventType.STATE_CHANGED.value,
                from_state=current_state.value,
                to_state=target_state.value,
                actor_user_id=actor_user_id,
                reason=reason.strip() if reason else None,
            ),
        )
        await self._session.refresh(record)
        return _job_to_domain(record)

    async def list_job_events(
        self,
        organization_id: UUID,
        job_id: UUID,
    ) -> list[JobEvent]:
        statement = (
            select(JobEventRecord)
            .where(
                JobEventRecord.organization_id == organization_id,
                JobEventRecord.job_id == job_id,
            )
            .order_by(JobEventRecord.sequence)
        )
        records = (await self._session.scalars(statement)).all()
        return [_event_to_domain(record) for record in records]

    async def create_checkpoint(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        requested_by_user_id: UUID,
        request_message: str,
    ) -> HumanCheckpoint:
        job = await self.get_job(organization_id, job_id)
        if job is None:
            raise ResourceNotFoundError("workflow job was not found")
        record = HumanCheckpointRecord(
            job_id=job.id,
            organization_id=organization_id,
            review_id=job.review_id,
            state=CheckpointState.PENDING.value,
            request_message=request_message.strip(),
            requested_by_user_id=requested_by_user_id,
        )
        self._session.add(record)
        await self._session.flush()
        await self._append_event(
            organization_id=organization_id,
            job=job,
            event_type=JobEventType.CHECKPOINT_REQUESTED,
            actor_user_id=requested_by_user_id,
            reason=request_message,
        )
        await self._session.refresh(record)
        return _checkpoint_to_domain(record)

    async def get_checkpoint(
        self,
        organization_id: UUID,
        checkpoint_id: UUID,
    ) -> HumanCheckpoint | None:
        statement = select(HumanCheckpointRecord).where(
            HumanCheckpointRecord.organization_id == organization_id,
            HumanCheckpointRecord.id == checkpoint_id,
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        return _checkpoint_to_domain(record) if record is not None else None

    async def resolve_checkpoint(
        self,
        *,
        organization_id: UUID,
        checkpoint_id: UUID,
        decision: CheckpointState,
        resolved_by_user_id: UUID,
        decision_note: str | None,
    ) -> HumanCheckpoint:
        statement = (
            select(HumanCheckpointRecord)
            .where(
                HumanCheckpointRecord.organization_id == organization_id,
                HumanCheckpointRecord.id == checkpoint_id,
            )
            .with_for_update()
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        if record is None:
            raise ResourceNotFoundError("human checkpoint was not found")
        if record.state != CheckpointState.PENDING.value:
            raise ConflictError("human checkpoint has already been resolved")
        job = await self.get_job(organization_id, record.job_id)
        if job is None:
            raise ResourceNotFoundError("workflow job was not found")
        record.state = decision.value
        record.decision_note = decision_note.strip() if decision_note else None
        record.resolved_by_user_id = resolved_by_user_id
        record.resolved_at = datetime.now(UTC)
        await self._append_event(
            organization_id=organization_id,
            job=job,
            event_type=JobEventType.CHECKPOINT_RESOLVED,
            actor_user_id=resolved_by_user_id,
            reason=record.decision_note or decision.value,
        )
        await self._session.flush()
        await self._session.refresh(record)
        return _checkpoint_to_domain(record)

    async def _append_event(
        self,
        *,
        organization_id: UUID,
        job: WorkflowJob,
        event_type: JobEventType,
        actor_user_id: UUID | None,
        reason: str | None,
    ) -> None:
        async def read_next_sequence() -> int:
            sequence_statement = select(func.coalesce(func.max(JobEventRecord.sequence), 0)).where(
                JobEventRecord.job_id == job.id,
                JobEventRecord.organization_id == organization_id,
            )
            return int((await self._session.execute(sequence_statement)).scalar_one()) + 1

        await insert_next_unique_integer(
            self._session,
            read_next_sequence,
            lambda sequence: JobEventRecord(
                organization_id=organization_id,
                job_id=job.id,
                sequence=sequence,
                event_type=event_type.value,
                from_state=job.state.value,
                to_state=job.state.value,
                actor_user_id=actor_user_id,
                reason=reason.strip() if reason else None,
            ),
        )
