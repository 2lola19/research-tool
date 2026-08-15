"""Add provider-neutral AI execution, attempts, validation, and proposals.

Revision ID: 20260814_0024
Revises: 20260813_0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0024"
down_revision: str | None = "20260813_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_model_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(80), nullable=False),
        sa.Column("model_identifier", sa.String(160), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("configuration_version", sa.Integer(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("structured_output_supported", sa.Boolean(), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=True),
        sa.Column("pricing", sa.JSON(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("deprecated", sa.Boolean(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("id", "organization_id", name="uq_ai_model_versions_id_org"),
        sa.UniqueConstraint(
            "organization_id",
            "provider_key",
            "model_identifier",
            "configuration_version",
            name="uq_ai_model_version",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name="fk_ai_model_org", ondelete="CASCADE"
        ),
    )
    op.create_table(
        "ai_prompt_template_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_key", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(240), nullable=False),
        sa.Column("task_type", sa.String(60), nullable=False),
        sa.Column("system_instructions", sa.Text(), nullable=False),
        sa.Column("user_template", sa.Text(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=False),
        sa.Column("validation_requirements", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("id", "organization_id", name="uq_ai_prompt_versions_id_org"),
        sa.UniqueConstraint(
            "organization_id", "prompt_key", "version", name="uq_ai_prompt_version"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_prompt_creator",
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "ai_execution_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("task_type", sa.String(60), nullable=False),
        sa.Column("task_definition_key", sa.String(120), nullable=False),
        sa.Column("task_definition_version", sa.Integer(), nullable=False),
        sa.Column("output_schema_version", sa.Integer(), nullable=False),
        sa.Column("prompt_version_id", sa.Uuid(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("policy_snapshot", sa.JSON(), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("rendered_prompt", sa.Text(), nullable=False),
        sa.Column("rendered_prompt_hash", sa.String(64), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("identical_prior_run_id", sa.Uuid(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','TIMED_OUT','CANCELLED','INVALID_OUTPUT')",  # noqa: E501
            name="ck_ai_execution_run_state",
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_execution_runs_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_execution_run_review",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_version_id", "organization_id"],
            ["ai_prompt_template_versions.id", "ai_prompt_template_versions.organization_id"],
            name="fk_ai_execution_run_prompt",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id", "organization_id"],
            ["ai_model_versions.id", "ai_model_versions.organization_id"],
            name="fk_ai_execution_run_model",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_execution_run_creator",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_ai_execution_runs_review",
        "ai_execution_runs",
        ["organization_id", "review_id", "created_at"],
    )
    op.create_table(
        "ai_run_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("provider_key", sa.String(80), nullable=False),
        sa.Column("model_identifier", sa.String(160), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("error_kind", sa.String(40), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider_request_id", sa.String(200), nullable=True),
        sa.Column("response_snapshot", sa.JSON(), nullable=True),
        sa.Column("response_hash", sa.String(64), nullable=True),
        sa.Column("usage", sa.JSON(), nullable=False),
        sa.Column("estimated_cost", sa.String(80), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("ai_run_id", "attempt_number", name="uq_ai_run_attempt_number"),
        sa.ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            [
                "ai_execution_runs.id",
                "ai_execution_runs.organization_id",
                "ai_execution_runs.review_id",
            ],
            name="fk_ai_attempt_run",
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "ai_validation_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.String(30), nullable=False),
        sa.Column("valid", sa.Boolean(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("validator_version", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            [
                "ai_execution_runs.id",
                "ai_execution_runs.organization_id",
                "ai_execution_runs.review_id",
            ],
            name="fk_ai_validation_run",
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "ai_output_proposals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), nullable=False),
        sa.Column("task_type", sa.String(60), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("structured_value", sa.JSON(), nullable=False),
        sa.Column("evidence_references", sa.JSON(), nullable=False),
        sa.Column("model_reported_confidence", sa.Float(), nullable=True),
        sa.Column("response_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "model_reported_confidence IS NULL OR (model_reported_confidence >= 0 AND model_reported_confidence <= 1)",  # noqa: E501
            name="ck_ai_proposal_confidence",
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_output_proposal_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            [
                "ai_execution_runs.id",
                "ai_execution_runs.organization_id",
                "ai_execution_runs.review_id",
            ],
            name="fk_ai_proposal_run",
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "ai_review_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("canonical_subject_type", sa.String(100), nullable=True),
        sa.Column("canonical_subject_id", sa.Uuid(), nullable=True),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("decision IN ('ACCEPTED','REJECTED')", name="ck_ai_review_decision"),
        sa.UniqueConstraint("proposal_id", name="uq_ai_proposal_single_decision"),
        sa.ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_review_decision_proposal",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "reviewer_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_review_decision_reviewer",
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_review_decisions")
    op.drop_table("ai_output_proposals")
    op.drop_table("ai_validation_results")
    op.drop_table("ai_run_attempts")
    op.drop_index("ix_ai_execution_runs_review", table_name="ai_execution_runs")
    op.drop_table("ai_execution_runs")
    op.drop_table("ai_prompt_template_versions")
    op.drop_table("ai_model_versions")
