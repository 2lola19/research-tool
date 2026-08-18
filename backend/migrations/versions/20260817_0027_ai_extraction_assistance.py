"""Add governed AI structured extraction assistance.

Revision ID: 20260817_0027
Revises: 20260816_0026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260817_0027"
down_revision: str | None = "20260816_0026"
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
        "ai_extraction_policy_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("maximum_batch_size", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        _timestamps(),
        sa.UniqueConstraint(
            "organization_id", "review_id", "version", name="uq_ai_extraction_policy_version"
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_extraction_policy_tenant"
        ),
        sa.CheckConstraint("mode IN ('OFF','BLINDED_AI','ASSISTED')", name="ck_ai_extraction_mode"),
        sa.CheckConstraint(
            "maximum_batch_size BETWEEN 1 AND 100", name="ck_ai_extraction_batch_size"
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_extraction_policy_review",
            ondelete="CASCADE",
        ),
        _member("created_by_user_id", "fk_ai_extraction_policy_creator"),
    )
    op.create_table(
        "ai_extraction_proposal_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version_id", sa.Uuid(), nullable=False),
        sa.Column("schema_hash", sa.String(64), nullable=False),
        sa.Column("ordered_field_hash", sa.String(64), nullable=False),
        sa.Column("task_definition_version", sa.Integer(), nullable=False),
        sa.Column("assistance_mode", sa.String(20), nullable=False),
        sa.Column("source_manifest", sa.JSON(), nullable=False),
        sa.Column("selected_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("omitted_chunks", sa.JSON(), nullable=False),
        sa.Column("field_targets", sa.JSON(), nullable=False),
        sa.Column("selection_method", sa.String(80), nullable=False),
        sa.Column("chunk_manifest_hash", sa.String(64), nullable=False),
        sa.Column("selected_text_hash", sa.String(64), nullable=False),
        sa.Column("validation_results", sa.JSON(), nullable=False),
        _timestamps(),
        sa.UniqueConstraint("proposal_id", name="uq_ai_extraction_proposal"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_extraction_link_tenant"
        ),
        sa.CheckConstraint(
            "assistance_mode IN ('BLINDED_AI','ASSISTED')", name="ck_ai_extraction_link_mode"
        ),
        sa.CheckConstraint("length(schema_hash) = 64", name="ck_ai_extraction_schema_hash"),
        sa.CheckConstraint("length(ordered_field_hash) = 64", name="ck_ai_extraction_field_hash"),
        sa.CheckConstraint("length(chunk_manifest_hash) = 64", name="ck_ai_extraction_chunk_hash"),
        sa.CheckConstraint("length(selected_text_hash) = 64", name="ck_ai_extraction_text_hash"),
        sa.CheckConstraint("task_definition_version > 0", name="ck_ai_extraction_task_version"),
        _scoped("proposal_id", "ai_output_proposals", "fk_ai_extraction_proposal"),
        _scoped("ai_run_id", "ai_execution_runs", "fk_ai_extraction_run"),
        _scoped("assignment_id", "extraction_runs", "fk_ai_extraction_assignment"),
        _scoped("study_id", "studies", "fk_ai_extraction_study"),
        _scoped("schema_version_id", "extraction_schema_versions", "fk_ai_extraction_schema"),
    )
    op.create_index(
        "ix_ai_extraction_assignment",
        "ai_extraction_proposal_links",
        ["organization_id", "review_id", "assignment_id", "created_at"],
    )
    op.create_table(
        "ai_extraction_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_link_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("processing_run_id", sa.Uuid(), nullable=False),
        sa.Column("document_role", sa.String(40), nullable=False),
        sa.Column("document_content_hash", sa.String(64), nullable=False),
        sa.Column("parser_name", sa.String(120), nullable=False),
        sa.Column("parser_version", sa.String(80), nullable=False),
        sa.Column("parsed_content_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("proposal_link_id", "ordinal", name="uq_ai_extraction_source_ordinal"),
        sa.UniqueConstraint(
            "proposal_link_id", "document_id", name="uq_ai_extraction_source_document"
        ),
        sa.CheckConstraint(
            "document_version_id = document_id", name="ck_ai_extraction_doc_version"
        ),
        sa.CheckConstraint(
            "document_role IN "
            "('PRIMARY_FULL_TEXT','SUPPLEMENT','APPENDIX','OTHER_SUPPORTING_DOCUMENT')",
            name="ck_ai_extraction_source_role",
        ),
        _scoped("proposal_link_id", "ai_extraction_proposal_links", "fk_ai_extraction_source_link"),
        _scoped("article_id", "articles", "fk_ai_extraction_source_article"),
        _scoped("document_id", "documents", "fk_ai_extraction_source_document"),
        _scoped("document_version_id", "documents", "fk_ai_extraction_source_version"),
        _scoped(
            "processing_run_id",
            "document_processing_runs",
            "fk_ai_extraction_source_processing",
        ),
    )
    op.create_table(
        "ai_extraction_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_link_id", sa.Uuid(), nullable=False),
        sa.Column("field_key", sa.String(200), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.String(500), nullable=False),
        sa.Column("source_block_id", sa.Uuid(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(500), nullable=True),
        sa.Column("table_id", sa.String(200), nullable=True),
        sa.Column("figure_id", sa.String(200), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "proposal_link_id", "field_key", "ordinal", name="uq_ai_extraction_evidence_ordinal"
        ),
        _scoped(
            "proposal_link_id", "ai_extraction_proposal_links", "fk_ai_extraction_evidence_link"
        ),
        _scoped("document_id", "documents", "fk_ai_extraction_evidence_document"),
        _scoped("document_version_id", "documents", "fk_ai_extraction_evidence_version"),
        sa.ForeignKeyConstraint(
            ["source_block_id", "document_id", "organization_id", "review_id"],
            [
                "document_blocks.id",
                "document_blocks.document_id",
                "document_blocks.organization_id",
                "document_blocks.review_id",
            ],
            name="fk_ai_extraction_evidence_block",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_ai_extraction_evidence_field",
        "ai_extraction_evidence",
        ["proposal_link_id", "field_key"],
    )
    op.create_table(
        "ai_extraction_access_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("access_type", sa.String(30), nullable=False),
        sa.Column("canonical_run_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column(
            "accessed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "proposal_id", "reviewer_user_id", "access_type", name="uq_ai_extraction_access"
        ),
        sa.CheckConstraint(
            "access_type IN ('ASSISTED_VIEW','POST_SUBMISSION_REVEAL')",
            name="ck_ai_extraction_access_type",
        ),
        _scoped("proposal_id", "ai_output_proposals", "fk_ai_extraction_access_proposal"),
        _scoped("assignment_id", "extraction_runs", "fk_ai_extraction_access_assignment"),
        _scoped("canonical_run_id", "extraction_runs", "fk_ai_extraction_access_canonical_run"),
        _member("reviewer_user_id", "fk_ai_extraction_access_reviewer"),
    )
    op.create_table(
        "ai_extraction_field_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("field_key", sa.String(200), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("ai_value_snapshot", sa.JSON(), nullable=False),
        sa.Column("human_value_snapshot", sa.JSON(), nullable=True),
        sa.Column("canonical_value_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        _timestamps(),
        sa.CheckConstraint(
            "action IN ('ACCEPTED','EDITED','REJECTED','UNRESOLVED')",
            name="ck_ai_extraction_field_action",
        ),
        _scoped("proposal_id", "ai_output_proposals", "fk_ai_extraction_field_proposal"),
        _scoped("assignment_id", "extraction_runs", "fk_ai_extraction_field_assignment"),
        _scoped("canonical_value_id", "extraction_values", "fk_ai_extraction_field_value"),
        _member("reviewer_user_id", "fk_ai_extraction_field_reviewer"),
    )
    op.create_table(
        "ai_extraction_evaluation_datasets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version_id", sa.Uuid(), nullable=False),
        sa.Column("logical_key", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("reference_standard", sa.String(50), nullable=False),
        sa.Column("tolerance_policy_version", sa.String(80), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        _timestamps(),
        sa.UniqueConstraint(
            "organization_id",
            "review_id",
            "logical_key",
            "version",
            name="uq_ai_extraction_dataset_version",
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_extraction_dataset_tenant"
        ),
        _scoped(
            "schema_version_id", "extraction_schema_versions", "fk_ai_extraction_dataset_schema"
        ),
        _member("created_by_user_id", "fk_ai_extraction_dataset_creator"),
    )
    op.create_table(
        "ai_extraction_evaluation_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("field_key", sa.String(200), nullable=False),
        sa.Column("field_type", sa.String(30), nullable=False),
        sa.Column("reference_missingness", sa.String(40), nullable=False),
        sa.Column("reference_value", sa.JSON(), nullable=True),
        sa.Column("reference_unit", sa.String(100), nullable=True),
        sa.Column("reference_source_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=True),
        sa.Column("absolute_tolerance", sa.Float(), nullable=True),
        sa.UniqueConstraint("dataset_id", "ordinal", name="uq_ai_extraction_case_ordinal"),
        sa.UniqueConstraint(
            "dataset_id", "study_id", "field_key", name="uq_ai_extraction_case_field"
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_extraction_case_tenant"
        ),
        _scoped("dataset_id", "ai_extraction_evaluation_datasets", "fk_ai_extraction_case_dataset"),
        _scoped("study_id", "studies", "fk_ai_extraction_case_study"),
    )
    op.create_table(
        "ai_extraction_evaluation_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("result_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        _timestamps(),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_extraction_result_tenant"
        ),
        _scoped(
            "dataset_id", "ai_extraction_evaluation_datasets", "fk_ai_extraction_result_dataset"
        ),
        _member("created_by_user_id", "fk_ai_extraction_result_creator"),
    )
    op.create_table(
        "ai_extraction_evaluation_case_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_result_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=True),
        sa.Column("classification", sa.String(50), nullable=False),
        sa.Column("ai_status", sa.String(50), nullable=True),
        sa.Column("ai_value", sa.JSON(), nullable=True),
        sa.Column("reference_value", sa.JSON(), nullable=True),
        sa.Column("absolute_error", sa.Float(), nullable=True),
        sa.Column("relative_error", sa.Float(), nullable=True),
        sa.Column("evidence_valid", sa.Boolean(), nullable=False),
        sa.Column("error_categories", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_location", sa.JSON(), nullable=True),
        sa.UniqueConstraint("evaluation_result_id", "case_id", name="uq_ai_extraction_case_result"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_extraction_case_result_tenant"
        ),
        _scoped(
            "evaluation_result_id",
            "ai_extraction_evaluation_results",
            "fk_ai_extraction_case_result_evaluation",
        ),
        _scoped("case_id", "ai_extraction_evaluation_cases", "fk_ai_extraction_case_result_case"),
        _scoped("proposal_id", "ai_output_proposals", "fk_ai_extraction_case_result_proposal"),
    )
    op.create_table(
        "ai_extraction_error_classifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("case_result_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("classified_by_user_id", sa.Uuid(), nullable=False),
        _timestamps(),
        _scoped(
            "case_result_id",
            "ai_extraction_evaluation_case_results",
            "fk_ai_extraction_error_case_result",
        ),
        _member("classified_by_user_id", "fk_ai_extraction_error_classifier"),
    )


def downgrade() -> None:
    op.drop_table("ai_extraction_error_classifications")
    op.drop_table("ai_extraction_evaluation_case_results")
    op.drop_table("ai_extraction_evaluation_results")
    op.drop_table("ai_extraction_evaluation_cases")
    op.drop_table("ai_extraction_evaluation_datasets")
    op.drop_table("ai_extraction_field_reviews")
    op.drop_table("ai_extraction_access_events")
    op.drop_index("ix_ai_extraction_evidence_field", table_name="ai_extraction_evidence")
    op.drop_table("ai_extraction_evidence")
    op.drop_table("ai_extraction_sources")
    op.drop_index("ix_ai_extraction_assignment", table_name="ai_extraction_proposal_links")
    op.drop_table("ai_extraction_proposal_links")
    op.drop_table("ai_extraction_policy_versions")
