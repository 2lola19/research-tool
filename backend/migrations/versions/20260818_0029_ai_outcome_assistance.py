"""Add governed AI outcome harmonization assistance.

Revision ID: 20260818_0029
Revises: 20260818_0028
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260818_0029"
down_revision: str | None = "20260818_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _scoped(column: str, table: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column, "organization_id", "review_id"],
        [f"{table}.id", f"{table}.organization_id", f"{table}.review_id"],
        name=name,
        ondelete="RESTRICT",
    )


def _member(column: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["organization_id", column],
        ["memberships.organization_id", "memberships.user_id"],
        name=name,
        ondelete="RESTRICT",
    )


def _timestamps() -> sa.Column[object]:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "ai_outcome_policy_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("maximum_batch_size", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        _timestamps(),
        sa.UniqueConstraint(
            "organization_id", "review_id", "version", name="uq_ai_outcome_policy_version"
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_outcome_policy_tenant"
        ),
        sa.CheckConstraint("maximum_batch_size BETWEEN 1 AND 100", name="ck_ai_outcome_batch_size"),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_outcome_policy_review",
            ondelete="CASCADE",
        ),
        _member("created_by_user_id", "fk_ai_outcome_policy_creator"),
    )
    op.create_table(
        "ai_outcome_proposal_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_value_id", sa.Uuid(), nullable=False),
        sa.Column("outcome_version_id", sa.Uuid(), nullable=False),
        sa.Column("outcome_version_hash", sa.String(64), nullable=False),
        sa.Column("extraction_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("task_definition_version", sa.Integer(), nullable=False),
        sa.Column("source_manifest", sa.JSON(), nullable=False),
        sa.Column("selected_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("omitted_chunks", sa.JSON(), nullable=False),
        sa.Column("selection_method", sa.String(100), nullable=False),
        sa.Column("chunk_manifest_hash", sa.String(64), nullable=False),
        sa.Column("selected_text_hash", sa.String(64), nullable=False),
        sa.Column("validation_results", sa.JSON(), nullable=False),
        _timestamps(),
        sa.UniqueConstraint("proposal_id", name="uq_ai_outcome_proposal"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_outcome_link_tenant"),
        sa.CheckConstraint("length(outcome_version_hash) = 64", name="ck_ai_outcome_version_hash"),
        sa.CheckConstraint(
            "length(extraction_snapshot_hash) = 64", name="ck_ai_outcome_extraction_hash"
        ),
        sa.CheckConstraint("length(chunk_manifest_hash) = 64", name="ck_ai_outcome_chunk_hash"),
        sa.CheckConstraint("length(selected_text_hash) = 64", name="ck_ai_outcome_text_hash"),
        sa.CheckConstraint("task_definition_version > 0", name="ck_ai_outcome_task_version"),
        _scoped("proposal_id", "ai_output_proposals", "fk_ai_outcome_proposal"),
        _scoped("ai_run_id", "ai_execution_runs", "fk_ai_outcome_run"),
        _scoped("study_id", "studies", "fk_ai_outcome_study"),
        _scoped("extraction_value_id", "extraction_values", "fk_ai_outcome_extraction_value"),
        _scoped("outcome_version_id", "outcome_definition_versions", "fk_ai_outcome_version"),
    )
    op.create_index(
        "ix_ai_outcome_extraction",
        "ai_outcome_proposal_links",
        ["organization_id", "review_id", "extraction_value_id", "created_at"],
    )
    op.create_table(
        "ai_outcome_access_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("access_type", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "accessed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "proposal_id", "reviewer_user_id", "access_type", name="uq_ai_outcome_access"
        ),
        sa.CheckConstraint(
            "access_type IN ('ASSISTED_VIEW','HUMAN_REVIEW')", name="ck_ai_outcome_access_type"
        ),
        _scoped("proposal_id", "ai_output_proposals", "fk_ai_outcome_access_proposal"),
        _member("reviewer_user_id", "fk_ai_outcome_access_reviewer"),
    )
    op.create_table(
        "ai_outcome_human_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("canonical_action", sa.String(40), nullable=True),
        sa.Column("canonical_subject_id", sa.Uuid(), nullable=True),
        sa.Column("ai_candidate_snapshot", sa.JSON(), nullable=False),
        sa.Column("human_payload_snapshot", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        _timestamps(),
        sa.CheckConstraint(
            "action IN ('ACCEPTED','EDITED','REJECTED','UNRESOLVED')",
            name="ck_ai_outcome_review_action",
        ),
        _scoped("proposal_id", "ai_output_proposals", "fk_ai_outcome_human_review_proposal"),
        _member("reviewer_user_id", "fk_ai_outcome_human_review_reviewer"),
    )
    op.create_table(
        "ai_outcome_evaluation_datasets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("logical_key", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("reference_standard", sa.String(40), nullable=False),
        sa.Column("cases", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        _timestamps(),
        sa.UniqueConstraint(
            "organization_id",
            "review_id",
            "logical_key",
            "version",
            name="uq_ai_outcome_dataset_version",
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_outcome_dataset_tenant"
        ),
        sa.CheckConstraint(
            "reference_standard IN ('HUMAN_HARMONIZED','CURATED_GOLD','FINAL_CANONICAL')",
            name="ck_ai_outcome_reference_standard",
        ),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_ai_outcome_dataset_hash"),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_outcome_dataset_review",
            ondelete="CASCADE",
        ),
        _member("created_by_user_id", "fk_ai_outcome_dataset_creator"),
    )
    op.create_table(
        "ai_outcome_evaluation_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("case_results", sa.JSON(), nullable=False),
        sa.Column("result_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        _timestamps(),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_outcome_result_tenant"
        ),
        _scoped("dataset_id", "ai_outcome_evaluation_datasets", "fk_ai_outcome_result_dataset"),
        _member("created_by_user_id", "fk_ai_outcome_result_creator"),
    )
    op.create_table(
        "ai_outcome_error_classifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_result_id", sa.Uuid(), nullable=False),
        sa.Column("case_key", sa.String(160), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("classified_by_user_id", sa.Uuid(), nullable=False),
        _timestamps(),
        _scoped(
            "evaluation_result_id", "ai_outcome_evaluation_results", "fk_ai_outcome_error_result"
        ),
        _member("classified_by_user_id", "fk_ai_outcome_error_classifier"),
    )


def downgrade() -> None:
    op.drop_table("ai_outcome_error_classifications")
    op.drop_table("ai_outcome_evaluation_results")
    op.drop_table("ai_outcome_evaluation_datasets")
    op.drop_table("ai_outcome_human_reviews")
    op.drop_table("ai_outcome_access_events")
    op.drop_index("ix_ai_outcome_extraction", table_name="ai_outcome_proposal_links")
    op.drop_table("ai_outcome_proposal_links")
    op.drop_table("ai_outcome_policy_versions")
