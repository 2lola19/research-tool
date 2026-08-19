"""Add versioned retry policy, step checkpoints, and recovery operations.

Revision ID: 20260819_0033
Revises: 20260819_0032
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_0033"
down_revision: str | None = "20260819_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _workflow_job_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("retry_policy", sa.JSON(), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), server_default="300", nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_class", sa.String(length=20), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recovery_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("step_key", sa.String(length=120), nullable=True),
        sa.Column("step_order", sa.Integer(), nullable=True),
        sa.Column("definition_hash", sa.String(length=64), nullable=True),
    )


def _create_workflow_job_checks() -> None:
    op.create_check_constraint(
        "ck_workflow_jobs_state",
        "workflow_jobs",
        "state IN ('NOT_STARTED', 'QUEUED', 'RUNNING', 'AWAITING_HUMAN', "
        "'COMPLETED', 'FAILED', 'DEAD_LETTERED', 'PAUSED', 'CANCELLED')",
    )
    op.create_check_constraint(
        "ck_workflow_jobs_timeout_seconds",
        "workflow_jobs",
        "timeout_seconds >= 5 AND timeout_seconds <= 86400",
    )
    op.create_check_constraint(
        "ck_workflow_jobs_recovery_count",
        "workflow_jobs",
        "recovery_count >= 0",
    )


def _drop_workflow_job_checks() -> None:
    op.drop_constraint("ck_workflow_jobs_recovery_count", "workflow_jobs", type_="check")
    op.drop_constraint("ck_workflow_jobs_timeout_seconds", "workflow_jobs", type_="check")
    op.drop_constraint("ck_workflow_jobs_state", "workflow_jobs", type_="check")


def _create_original_workflow_job_state_check() -> None:
    op.create_check_constraint(
        "ck_workflow_jobs_state",
        "workflow_jobs",
        "state IN ('NOT_STARTED', 'QUEUED', 'RUNNING', 'AWAITING_HUMAN', "
        "'COMPLETED', 'FAILED', 'PAUSED', 'CANCELLED')",
    )


def upgrade() -> None:
    if _is_postgresql():
        for column in _workflow_job_columns():
            op.add_column("workflow_jobs", column)
        op.drop_constraint("ck_workflow_jobs_state", "workflow_jobs", type_="check")
        _create_workflow_job_checks()
        op.add_column(
            "workflow_job_attempts",
            sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        )
    else:
        with op.batch_alter_table("workflow_jobs", recreate="always") as batch_op:
            for column in _workflow_job_columns():
                batch_op.add_column(column)
            batch_op.drop_constraint("ck_workflow_jobs_state", type_="check")
            batch_op.create_check_constraint(
                "ck_workflow_jobs_state",
                "state IN ('NOT_STARTED', 'QUEUED', 'RUNNING', 'AWAITING_HUMAN', "
                "'COMPLETED', 'FAILED', 'DEAD_LETTERED', 'PAUSED', 'CANCELLED')",
            )
            batch_op.create_check_constraint(
                "ck_workflow_jobs_timeout_seconds",
                "timeout_seconds >= 5 AND timeout_seconds <= 86400",
            )
            batch_op.create_check_constraint(
                "ck_workflow_jobs_recovery_count",
                "recovery_count >= 0",
            )

        with op.batch_alter_table("workflow_job_attempts", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index(
        "ix_workflow_jobs_retry_schedule",
        "workflow_jobs",
        ["organization_id", "state", "next_retry_at"],
    )

    op.create_table(
        "workflow_step_checkpoints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("step_key", sa.String(length=120), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("definition_hash", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("checkpoint_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("output_digest", sa.String(length=64), nullable=True),
        sa.Column("failure_class", sa.String(length=20), nullable=True),
        sa.Column("checkpointed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('PENDING', 'QUEUED', 'RUNNING', 'AWAITING_HUMAN', 'COMPLETED', "
            "'FAILED', 'DEAD_LETTERED', 'CANCELLED')",
            name="ck_workflow_step_checkpoint_state",
        ),
        sa.CheckConstraint(
            "checkpoint_version > 0",
            name="ck_workflow_step_checkpoint_version",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id", "organization_id", "review_id"],
            ["workflow_runs.id", "workflow_runs.organization_id", "workflow_runs.review_id"],
            name="fk_workflow_step_checkpoint_run_tenant_review",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "organization_id", "review_id"],
            ["workflow_jobs.id", "workflow_jobs.organization_id", "workflow_jobs.review_id"],
            name="fk_workflow_step_checkpoint_job_tenant_review",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_run_id",
            "step_key",
            name="uq_workflow_step_checkpoint_run_step",
        ),
    )
    op.create_index(
        "ix_workflow_step_checkpoints_review",
        "workflow_step_checkpoints",
        ["organization_id", "review_id", "state"],
    )

    op.create_table(
        "workflow_recovery_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=20), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("additional_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("resulting_state", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "operation IN ('RESUME', 'MANUAL_RETRY')",
            name="ck_workflow_recovery_operation_type",
        ),
        sa.CheckConstraint(
            "additional_attempts >= 0 AND additional_attempts <= 100",
            name="ck_workflow_recovery_additional_attempts",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "organization_id", "review_id"],
            ["workflow_jobs.id", "workflow_jobs.organization_id", "workflow_jobs.review_id"],
            name="fk_workflow_recovery_operation_job_tenant_review",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_workflow_recovery_operation_actor_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id",
            "operation",
            "idempotency_key",
            name="uq_workflow_recovery_operation_idempotency",
        ),
    )
    op.create_index(
        "ix_workflow_recovery_operations_review",
        "workflow_recovery_operations",
        ["organization_id", "review_id", "operation"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_recovery_operations_review",
        table_name="workflow_recovery_operations",
    )
    op.drop_table("workflow_recovery_operations")
    op.drop_index(
        "ix_workflow_step_checkpoints_review",
        table_name="workflow_step_checkpoints",
    )
    op.drop_table("workflow_step_checkpoints")
    op.drop_index("ix_workflow_jobs_retry_schedule", table_name="workflow_jobs")

    if _is_postgresql():
        op.drop_column("workflow_job_attempts", "deadline_at")
        _drop_workflow_job_checks()
        _create_original_workflow_job_state_check()
        for column in (
            "definition_hash",
            "step_order",
            "step_key",
            "recovery_count",
            "dead_lettered_at",
            "failure_class",
            "next_retry_at",
            "timeout_seconds",
            "retry_policy",
        ):
            op.drop_column("workflow_jobs", column)
    else:
        with op.batch_alter_table("workflow_job_attempts", recreate="always") as batch_op:
            batch_op.drop_column("deadline_at")

        with op.batch_alter_table("workflow_jobs", recreate="always") as batch_op:
            batch_op.drop_constraint("ck_workflow_jobs_recovery_count", type_="check")
            batch_op.drop_constraint("ck_workflow_jobs_timeout_seconds", type_="check")
            batch_op.drop_constraint("ck_workflow_jobs_state", type_="check")
            batch_op.create_check_constraint(
                "ck_workflow_jobs_state",
                "state IN ('NOT_STARTED', 'QUEUED', 'RUNNING', 'AWAITING_HUMAN', "
                "'COMPLETED', 'FAILED', 'PAUSED', 'CANCELLED')",
            )
            for column in (
                "definition_hash",
                "step_order",
                "step_key",
                "recovery_count",
                "dead_lettered_at",
                "failure_class",
                "next_retry_at",
                "timeout_seconds",
                "retry_policy",
            ):
                batch_op.drop_column(column)
