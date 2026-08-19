"""Add read-only evidence-aware Review copilot storage.

Revision ID: 20260819_0031
Revises: 20260819_0030
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_0031"
down_revision: str | None = "20260819_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_copilot_policy_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("maximum_query_characters", sa.Integer(), nullable=False),
        sa.Column("maximum_context_items", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "review_id", "version", name="uq_ai_copilot_policy_version"
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_copilot_policy_tenant"
        ),
        sa.CheckConstraint(
            "maximum_query_characters BETWEEN 100 AND 4000",
            name="ck_ai_copilot_query_characters",
        ),
        sa.CheckConstraint(
            "maximum_context_items BETWEEN 2 AND 200",
            name="ck_ai_copilot_context_items",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_copilot_policy_review",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_copilot_policy_creator",
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "ai_copilot_queries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("task_key", sa.String(50), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), nullable=True),
        sa.Column("proposal_id", sa.Uuid(), nullable=True),
        sa.Column("answer_snapshot", sa.JSON(), nullable=True),
        sa.Column("validation_results", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_copilot_query_tenant"
        ),
        sa.CheckConstraint(
            "task_key IN ('PROJECT_STATUS','WORKFLOW_BLOCKERS','PROVENANCE_NAVIGATION')",
            name="ck_ai_copilot_task_key",
        ),
        sa.CheckConstraint(
            "status IN ('SUCCEEDED','ABSTAINED','FAILED','INVALID_OUTPUT')",
            name="ck_ai_copilot_query_status",
        ),
        sa.CheckConstraint("length(context_hash) = 64", name="ck_ai_copilot_context_hash"),
        sa.CheckConstraint("length(query_text) BETWEEN 1 AND 4000", name="ck_ai_copilot_query_text"),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_copilot_query_review",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_copilot_query_creator",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            ["ai_execution_runs.id", "ai_execution_runs.organization_id", "ai_execution_runs.review_id"],
            name="fk_ai_copilot_query_run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            ["ai_output_proposals.id", "ai_output_proposals.organization_id", "ai_output_proposals.review_id"],
            name="fk_ai_copilot_query_proposal",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_ai_copilot_queries_review_created",
        "ai_copilot_queries",
        ["organization_id", "review_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_copilot_queries_review_created", table_name="ai_copilot_queries")
    op.drop_table("ai_copilot_queries")
    op.drop_table("ai_copilot_policy_versions")
