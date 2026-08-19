from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.workflow.recovery_domain import (
    FailureClass,
    RecoveryOperationType,
    WorkflowRecoveryOperation,
    WorkflowStepCheckpoint,
    WorkflowStepState,
)


class WorkflowStepCheckpointRecord(Base):
    __tablename__ = "workflow_step_checkpoints"
    __table_args__ = (
        CheckConstraint(
            "state IN ('PENDING', 'QUEUED', 'RUNNING', 'AWAITING_HUMAN', 'COMPLETED', "
            "'FAILED', 'DEAD_LETTERED', 'CANCELLED')",
            name="ck_workflow_step_checkpoint_state",
        ),
        CheckConstraint("checkpoint_version > 0", name="ck_workflow_step_checkpoint_version"),
        UniqueConstraint(
            "workflow_run_id",
            "step_key",
            name="uq_workflow_step_checkpoint_run_step",
        ),
        ForeignKeyConstraint(
            ["workflow_run_id", "organization_id", "review_id"],
            ["workflow_runs.id", "workflow_runs.organization_id", "workflow_runs.review_id"],
            name="fk_workflow_step_checkpoint_run_tenant_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["job_id", "organization_id", "review_id"],
            ["workflow_jobs.id", "workflow_jobs.organization_id", "workflow_jobs.review_id"],
            name="fk_workflow_step_checkpoint_job_tenant_review",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    workflow_run_id: Mapped[UUID] = mapped_column()
    job_id: Mapped[UUID | None] = mapped_column(nullable=True)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    step_key: Mapped[str] = mapped_column(String(120))
    step_order: Mapped[int] = mapped_column(Integer)
    definition_hash: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20))
    checkpoint_version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    output_digest: Mapped[str | None] = mapped_column(String(64))
    failure_class: Mapped[str | None] = mapped_column(String(20))
    checkpointed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorkflowRecoveryOperationRecord(Base):
    __tablename__ = "workflow_recovery_operations"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "operation",
            "idempotency_key",
            name="uq_workflow_recovery_operation_idempotency",
        ),
        CheckConstraint(
            "operation IN ('RESUME', 'MANUAL_RETRY')",
            name="ck_workflow_recovery_operation_type",
        ),
        CheckConstraint(
            "additional_attempts >= 0 AND additional_attempts <= 100",
            name="ck_workflow_recovery_additional_attempts",
        ),
        ForeignKeyConstraint(
            ["job_id", "organization_id", "review_id"],
            ["workflow_jobs.id", "workflow_jobs.organization_id", "workflow_jobs.review_id"],
            name="fk_workflow_recovery_operation_job_tenant_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_workflow_recovery_operation_actor_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    operation: Mapped[str] = mapped_column(String(20))
    idempotency_key: Mapped[str] = mapped_column(String(200))
    actor_user_id: Mapped[UUID | None] = mapped_column(nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    additional_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    resulting_state: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def step_checkpoint_to_domain(record: WorkflowStepCheckpointRecord) -> WorkflowStepCheckpoint:
    return WorkflowStepCheckpoint(
        id=record.id,
        workflow_run_id=record.workflow_run_id,
        job_id=record.job_id,
        organization_id=record.organization_id,
        review_id=record.review_id,
        step_key=record.step_key,
        step_order=record.step_order,
        definition_hash=record.definition_hash,
        state=WorkflowStepState(record.state),
        checkpoint_version=record.checkpoint_version,
        output_digest=record.output_digest,
        failure_class=(FailureClass(record.failure_class) if record.failure_class else None),
        checkpointed_at=_as_utc(record.checkpointed_at),
        updated_at=_as_utc(record.updated_at),
    )


def recovery_operation_to_domain(
    record: WorkflowRecoveryOperationRecord,
) -> WorkflowRecoveryOperation:
    return WorkflowRecoveryOperation(
        id=record.id,
        job_id=record.job_id,
        organization_id=record.organization_id,
        review_id=record.review_id,
        operation=RecoveryOperationType(record.operation),
        idempotency_key=record.idempotency_key,
        actor_user_id=record.actor_user_id,
        reason=record.reason,
        additional_attempts=record.additional_attempts,
        resulting_state=record.resulting_state,
        created_at=_as_utc(record.created_at),
    )
