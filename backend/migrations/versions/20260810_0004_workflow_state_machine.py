"""Add tenant-scoped workflow runs, jobs, events, and human checkpoints.

Revision ID: 20260810_0004
Revises: 20260810_0003
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0004"
down_revision: str | None = "20260810_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_name", sa.String(length=120), nullable=False),
        sa.Column("workflow_version", sa.String(length=50), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('ACTIVE', 'PAUSED', 'COMPLETED', 'FAILED', 'CANCELLED')",
            name="ck_workflow_runs_state",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_workflow_runs_review_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_workflow_runs_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "review_id",
            "idempotency_key",
            name="uq_workflow_runs_tenant_idempotency",
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_workflow_runs_id_tenant_review"
        ),
    )
    op.create_table(
        "workflow_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("task_name", sa.String(length=120), nullable=False),
        sa.Column("task_version", sa.String(length=50), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("paused_from_state", sa.String(length=20), nullable=True),
        sa.Column("attempt", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("attempt >= 0", name="ck_workflow_jobs_attempt"),
        sa.CheckConstraint(
            "paused_from_state IS NULL OR paused_from_state IN "
            "('QUEUED', 'RUNNING', 'AWAITING_HUMAN')",
            name="ck_workflow_jobs_paused_from_state",
        ),
        sa.CheckConstraint(
            "state IN ('NOT_STARTED', 'QUEUED', 'RUNNING', 'AWAITING_HUMAN', "
            "'COMPLETED', 'FAILED', 'PAUSED', 'CANCELLED')",
            name="ck_workflow_jobs_state",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_run_id", "organization_id", "review_id"],
            ["workflow_runs.id", "workflow_runs.organization_id", "workflow_runs.review_id"],
            name="fk_workflow_jobs_run_tenant_review",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", name="uq_workflow_jobs_id_org"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            "review_id",
            name="uq_workflow_jobs_id_org_review",
        ),
        sa.UniqueConstraint(
            "workflow_run_id",
            "idempotency_key",
            name="uq_workflow_jobs_run_idempotency",
        ),
    )
    op.create_table(
        "job_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_state", sa.String(length=20), nullable=True),
        sa.Column("to_state", sa.String(length=20), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "organization_id"],
            ["workflow_jobs.id", "workflow_jobs.organization_id"],
            name="fk_job_events_job_org",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_job_events_actor_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "sequence", name="uq_job_events_job_sequence"),
    )
    op.create_table(
        "human_checkpoints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("request_message", sa.Text(), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("resolved_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(resolved_at IS NULL AND resolved_by_user_id IS NULL AND state = 'PENDING') OR "
            "(resolved_at IS NOT NULL AND resolved_by_user_id IS NOT NULL "
            "AND state IN ('APPROVED', 'REJECTED', 'CANCELLED'))",
            name="ck_human_checkpoints_resolution",
        ),
        sa.CheckConstraint(
            "state IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')",
            name="ck_human_checkpoints_state",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "organization_id", "review_id"],
            ["workflow_jobs.id", "workflow_jobs.organization_id", "workflow_jobs.review_id"],
            name="fk_human_checkpoints_job_tenant_review",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "requested_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_human_checkpoints_requester_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "resolved_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_human_checkpoints_resolver_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("human_checkpoints")
    op.drop_table("job_events")
    op.drop_table("workflow_jobs")
    op.drop_table("workflow_runs")
