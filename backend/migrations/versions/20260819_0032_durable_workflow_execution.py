"""Add durable workflow attempts, leases, worker health, and payload versions.

Revision ID: 20260819_0032
Revises: 20260819_0031
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_0032"
down_revision: str | None = "20260819_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workflow_jobs",
        sa.Column(
            "payload_schema",
            sa.String(length=120),
            server_default="workflow.generic",
            nullable=False,
        ),
    )
    op.add_column(
        "workflow_jobs",
        sa.Column("payload_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "workflow_jobs",
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
    )

    op.create_table(
        "workflow_job_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=160), nullable=False),
        sa.Column("lease_token", sa.String(length=160), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column(
            "claimed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_snapshot", sa.JSON(), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.CheckConstraint("attempt_number > 0", name="ck_workflow_attempt_number"),
        sa.CheckConstraint(
            "state IN ('CLAIMED', 'RUNNING', 'COMPLETED', 'FAILED', 'EXPIRED')",
            name="ck_workflow_attempt_state",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "organization_id", "review_id"],
            ["workflow_jobs.id", "workflow_jobs.organization_id", "workflow_jobs.review_id"],
            name="fk_workflow_attempt_job_tenant_review",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_workflow_attempt_job_number"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            "review_id",
            name="uq_workflow_attempt_id_tenant_review",
        ),
        sa.UniqueConstraint("lease_token", name="uq_workflow_attempt_lease_token"),
    )
    op.create_index(
        "ix_workflow_attempts_claimable",
        "workflow_job_attempts",
        ["organization_id", "state", "lease_expires_at"],
    )
    op.create_index(
        "ix_workflow_attempts_worker_state",
        "workflow_job_attempts",
        ["worker_id", "state"],
    )

    op.create_table(
        "workflow_workers",
        sa.Column("worker_id", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("active_jobs", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('STARTING', 'HEALTHY', 'DRAINING', 'STOPPED', 'FAILED')",
            name="ck_workflow_worker_status",
        ),
        sa.CheckConstraint(
            "capacity > 0 AND capacity <= 100",
            name="ck_workflow_worker_capacity",
        ),
        sa.CheckConstraint(
            "active_jobs >= 0 AND active_jobs <= capacity",
            name="ck_workflow_worker_active",
        ),
        sa.PrimaryKeyConstraint("worker_id"),
    )
    op.create_index(
        "ix_workflow_workers_heartbeat",
        "workflow_workers",
        ["last_heartbeat_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_workers_heartbeat", table_name="workflow_workers")
    op.drop_table("workflow_workers")
    op.drop_index("ix_workflow_attempts_worker_state", table_name="workflow_job_attempts")
    op.drop_index("ix_workflow_attempts_claimable", table_name="workflow_job_attempts")
    op.drop_table("workflow_job_attempts")
    with op.batch_alter_table("workflow_jobs") as batch_op:
        batch_op.drop_column("max_attempts")
        batch_op.drop_column("payload_version")
        batch_op.drop_column("payload_schema")
