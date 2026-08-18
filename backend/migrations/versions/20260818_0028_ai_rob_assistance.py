"""Add governed AI Risk of Bias assistance.

Revision ID: 20260818_0028
Revises: 20260817_0027
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260818_0028"
down_revision: str | None = "20260817_0027"
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
        "ai_rob_policy_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("maximum_batch_size", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        _timestamps(),
        sa.UniqueConstraint("organization_id", "review_id", "version", name="uq_ai_rob_policy_version"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_rob_policy_tenant"),
        sa.CheckConstraint("mode IN ('OFF','BLINDED_AI','ASSISTED')", name="ck_ai_rob_mode"),
        sa.CheckConstraint("maximum_batch_size BETWEEN 1 AND 100", name="ck_ai_rob_batch_size"),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_rob_policy_review",
            ondelete="CASCADE",
        ),
        _member("created_by_user_id", "fk_ai_rob_policy_creator"),
    )
    op.create_table(
        "ai_rob_proposal_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_version_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_content_hash", sa.String(64), nullable=False),
        sa.Column("task_definition_version", sa.Integer(), nullable=False),
        sa.Column("assistance_mode", sa.String(20), nullable=False),
        sa.Column("source_manifest", sa.JSON(), nullable=False),
        sa.Column("selected_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("omitted_chunks", sa.JSON(), nullable=False),
        sa.Column("selection_method", sa.String(100), nullable=False),
        sa.Column("chunk_manifest_hash", sa.String(64), nullable=False),
        sa.Column("selected_text_hash", sa.String(64), nullable=False),
        sa.Column("validation_results", sa.JSON(), nullable=False),
        sa.Column("domain_suggestions", sa.JSON(), nullable=False),
        sa.Column("overall_suggestion", sa.String(120), nullable=True),
        _timestamps(),
        sa.UniqueConstraint("proposal_id", name="uq_ai_rob_proposal"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_rob_link_tenant"),
        sa.CheckConstraint("assistance_mode IN ('BLINDED_AI','ASSISTED')", name="ck_ai_rob_link_mode"),
        sa.CheckConstraint("length(instrument_content_hash) = 64", name="ck_ai_rob_instrument_hash"),
        sa.CheckConstraint("length(chunk_manifest_hash) = 64", name="ck_ai_rob_chunk_hash"),
        sa.CheckConstraint("length(selected_text_hash) = 64", name="ck_ai_rob_text_hash"),
        sa.CheckConstraint("task_definition_version > 0", name="ck_ai_rob_task_version"),
        _scoped("proposal_id", "ai_output_proposals", "fk_ai_rob_proposal"),
        _scoped("ai_run_id", "ai_execution_runs", "fk_ai_rob_run"),
        _scoped("assessment_id", "rob_assessments", "fk_ai_rob_assessment"),
        _scoped("study_id", "studies", "fk_ai_rob_study"),
        _scoped("instrument_version_id", "rob_instrument_versions", "fk_ai_rob_instrument_version"),
    )
    op.create_index(
        "ix_ai_rob_assessment",
        "ai_rob_proposal_links",
        ["organization_id", "review_id", "assessment_id", "created_at"],
    )
    op.create_table(
        "ai_rob_sources",
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
        sa.Column("block_count", sa.Integer(), nullable=False),
        sa.UniqueConstraint("proposal_link_id", "ordinal", name="uq_ai_rob_source_ordinal"),
        sa.UniqueConstraint("proposal_link_id", "document_id", name="uq_ai_rob_source_document"),
        sa.CheckConstraint("document_version_id = document_id", name="ck_ai_rob_source_version"),
        _scoped("proposal_link_id", "ai_rob_proposal_links", "fk_ai_rob_source_link"),
        _scoped("article_id", "articles", "fk_ai_rob_source_article"),
        _scoped("document_id", "documents", "fk_ai_rob_source_document"),
        _scoped("document_version_id", "documents", "fk_ai_rob_source_document_version"),
        _scoped("processing_run_id", "document_processing_runs", "fk_ai_rob_source_processing"),
    )
    op.create_table(
        "ai_rob_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_link_id", sa.Uuid(), nullable=False),
        sa.Column("question_key", sa.String(120), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.String(500), nullable=False),
        sa.Column("source_block_id", sa.Uuid(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(500), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "proposal_link_id", "question_key", "ordinal", name="uq_ai_rob_evidence_ordinal"
        ),
        _scoped("proposal_link_id", "ai_rob_proposal_links", "fk_ai_rob_evidence_link"),
        _scoped("document_id", "documents", "fk_ai_rob_evidence_document"),
        _scoped("document_version_id", "documents", "fk_ai_rob_evidence_document_version"),
        sa.ForeignKeyConstraint(
            ["source_block_id", "document_id", "organization_id", "review_id"],
            ["document_blocks.id", "document_blocks.document_id", "document_blocks.organization_id", "document_blocks.review_id"],
            name="fk_ai_rob_evidence_block",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_ai_rob_evidence_question",
        "ai_rob_evidence",
        ["proposal_link_id", "question_key"],
    )
    op.create_table(
        "ai_rob_access_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("access_type", sa.String(30), nullable=False),
        sa.Column("canonical_assessment_id", sa.Uuid(), nullable=True),
        sa.Column("accessed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("proposal_id", "reviewer_user_id", "access_type", name="uq_ai_rob_access"),
        sa.CheckConstraint(
            "access_type IN ('ASSISTED_VIEW','POST_SUBMISSION_REVEAL')",
            name="ck_ai_rob_access_type",
        ),
        _scoped("proposal_id", "ai_output_proposals", "fk_ai_rob_access_proposal"),
        _scoped("assessment_id", "rob_assessments", "fk_ai_rob_access_assessment"),
        _scoped("canonical_assessment_id", "rob_assessments", "fk_ai_rob_access_canonical_assessment"),
        _member("reviewer_user_id", "fk_ai_rob_access_reviewer"),
    )
    op.create_table(
        "ai_rob_answer_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("question_key", sa.String(120), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("ai_answer_snapshot", sa.JSON(), nullable=False),
        sa.Column("human_answer_snapshot", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        _timestamps(),
        sa.CheckConstraint(
            "action IN ('ACCEPTED','EDITED','REJECTED','UNRESOLVED')",
            name="ck_ai_rob_answer_review_action",
        ),
        _scoped("proposal_id", "ai_output_proposals", "fk_ai_rob_answer_review_proposal"),
        _scoped("assessment_id", "rob_assessments", "fk_ai_rob_answer_review_assessment"),
        _member("reviewer_user_id", "fk_ai_rob_answer_review_reviewer"),
    )
    op.create_table(
        "ai_rob_evaluation_datasets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_version_id", sa.Uuid(), nullable=False),
        sa.Column("logical_key", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("reference_standard", sa.String(40), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        _timestamps(),
        sa.UniqueConstraint(
            "organization_id", "review_id", "logical_key", "version", name="uq_ai_rob_dataset_version"
        ),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_rob_dataset_tenant"),
        sa.CheckConstraint(
            "reference_standard IN ('ADJUDICATED_ASSESSMENT','DUAL_HUMAN_ASSESSMENT','CURATED_GOLD')",
            name="ck_ai_rob_reference_standard",
        ),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_ai_rob_dataset_hash"),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_rob_dataset_review",
            ondelete="CASCADE",
        ),
        _scoped("instrument_version_id", "rob_instrument_versions", "fk_ai_rob_dataset_instrument"),
        _member("created_by_user_id", "fk_ai_rob_dataset_creator"),
    )
    op.create_table(
        "ai_rob_evaluation_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=True),
        sa.Column("question_key", sa.String(120), nullable=False),
        sa.Column("reference_answers", sa.JSON(), nullable=False),
        sa.Column("reference_domains", sa.JSON(), nullable=True),
        sa.Column("reference_overall", sa.String(120), nullable=True),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=True),
        sa.UniqueConstraint("dataset_id", "ordinal", name="uq_ai_rob_case_ordinal"),
        sa.UniqueConstraint("dataset_id", "study_id", "question_key", name="uq_ai_rob_case_question"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_rob_case_tenant"),
        _scoped("dataset_id", "ai_rob_evaluation_datasets", "fk_ai_rob_case_dataset"),
        _scoped("study_id", "studies", "fk_ai_rob_case_study"),
        _scoped("assessment_id", "rob_assessments", "fk_ai_rob_case_assessment"),
    )
    op.create_table(
        "ai_rob_evaluation_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("result_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        _timestamps(),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_rob_result_tenant"),
        _scoped("dataset_id", "ai_rob_evaluation_datasets", "fk_ai_rob_result_dataset"),
        _member("created_by_user_id", "fk_ai_rob_result_creator"),
    )
    op.create_table(
        "ai_rob_evaluation_case_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_result_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=True),
        sa.Column("classification", sa.String(40), nullable=False),
        sa.Column("signalling_agreement", sa.Boolean(), nullable=False),
        sa.Column("domain_agreement", sa.Boolean(), nullable=False),
        sa.Column("overall_agreement", sa.Boolean(), nullable=False),
        sa.Column("evidence_grounding_valid", sa.Boolean(), nullable=False),
        sa.Column("abstention", sa.Boolean(), nullable=False),
        sa.Column("dangerous_underestimation", sa.Boolean(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.UniqueConstraint("evaluation_result_id", "case_id", name="uq_ai_rob_case_result"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_rob_case_result_tenant"),
        _scoped("evaluation_result_id", "ai_rob_evaluation_results", "fk_ai_rob_case_result_result"),
        _scoped("case_id", "ai_rob_evaluation_cases", "fk_ai_rob_case_result_case"),
        _scoped("proposal_id", "ai_output_proposals", "fk_ai_rob_case_result_proposal"),
    )
    op.create_table(
        "ai_rob_error_classifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("case_result_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("classified_by_user_id", sa.Uuid(), nullable=False),
        _timestamps(),
        _scoped("case_result_id", "ai_rob_evaluation_case_results", "fk_ai_rob_error_case_result"),
        _member("classified_by_user_id", "fk_ai_rob_error_classifier"),
    )


def downgrade() -> None:
    op.drop_table("ai_rob_error_classifications")
    op.drop_table("ai_rob_evaluation_case_results")
    op.drop_table("ai_rob_evaluation_results")
    op.drop_table("ai_rob_evaluation_cases")
    op.drop_table("ai_rob_evaluation_datasets")
    op.drop_table("ai_rob_answer_reviews")
    op.drop_table("ai_rob_access_events")
    op.drop_index("ix_ai_rob_evidence_question", table_name="ai_rob_evidence")
    op.drop_table("ai_rob_evidence")
    op.drop_table("ai_rob_sources")
    op.drop_index("ix_ai_rob_assessment", table_name="ai_rob_proposal_links")
    op.drop_table("ai_rob_proposal_links")
    op.drop_table("ai_rob_policy_versions")
