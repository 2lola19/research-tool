"""Add governed AI full-text screening and document-grounded evaluation.

Revision ID: 20260816_0026
Revises: 20260815_0025
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_0026"
down_revision: str | None = "20260815_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _scoped_fk(columns: list[str], table: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [*columns, "organization_id", "review_id"],
        [*[f"{table}.id" for _column in columns], f"{table}.organization_id", f"{table}.review_id"],
        name=name,
        ondelete="RESTRICT",
    )


def _member_fk(column: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["organization_id", column],
        ["memberships.organization_id", "memberships.user_id"],
        name=name,
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.create_table(
        "ai_full_text_proposal_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("protocol_version_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("processing_run_id", sa.Uuid(), nullable=False),
        sa.Column("document_role", sa.String(40), nullable=False),
        sa.Column("parser_name", sa.String(120), nullable=False),
        sa.Column("parser_version", sa.String(80), nullable=False),
        sa.Column("protocol_content_hash", sa.String(64), nullable=False),
        sa.Column("exclusion_criteria_hash", sa.String(64), nullable=False),
        sa.Column("citation_content_hash", sa.String(64), nullable=False),
        sa.Column("document_content_hash", sa.String(64), nullable=False),
        sa.Column("parsed_representation_hash", sa.String(64), nullable=False),
        sa.Column("selected_text_hash", sa.String(64), nullable=False),
        sa.Column("chunk_manifest_hash", sa.String(64), nullable=False),
        sa.Column("selected_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("omitted_chunks", sa.JSON(), nullable=False),
        sa.Column("selection_method", sa.String(80), nullable=False),
        sa.Column("task_definition_version", sa.Integer(), nullable=False),
        sa.Column("assistance_mode", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("proposal_id", name="uq_ai_full_text_proposal"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_full_text_link_tenant"
        ),
        sa.CheckConstraint(
            "assistance_mode IN ('BLINDED_AI','ASSISTED')", name="ck_ai_full_text_mode"
        ),
        sa.CheckConstraint(
            "document_role IN ('PRIMARY_FULL_TEXT','SUPPLEMENT','APPENDIX','OTHER_SUPPORTING_DOCUMENT')",
            name="ck_ai_full_text_document_role",
        ),
        sa.CheckConstraint(
            "document_version_id = document_id", name="ck_ai_full_text_document_version"
        ),
        sa.CheckConstraint("task_definition_version > 0", name="ck_ai_full_text_task_version"),
        *[
            sa.CheckConstraint(f"length({column}) = 64", name=name)
            for column, name in (
                ("protocol_content_hash", "ck_ai_full_text_protocol_hash"),
                ("exclusion_criteria_hash", "ck_ai_full_text_criteria_hash"),
                ("citation_content_hash", "ck_ai_full_text_citation_hash"),
                ("document_content_hash", "ck_ai_full_text_document_hash"),
                ("parsed_representation_hash", "ck_ai_full_text_parsed_hash"),
                ("selected_text_hash", "ck_ai_full_text_selected_hash"),
                ("chunk_manifest_hash", "ck_ai_full_text_manifest_hash"),
            )
        ],
        _scoped_fk(["proposal_id"], "ai_output_proposals", "fk_ai_full_text_proposal"),
        _scoped_fk(["ai_run_id"], "ai_execution_runs", "fk_ai_full_text_run"),
        _scoped_fk(["article_id"], "articles", "fk_ai_full_text_article"),
        _scoped_fk(["assignment_id"], "screening_assignments", "fk_ai_full_text_assignment"),
        _scoped_fk(["protocol_version_id"], "protocol_versions", "fk_ai_full_text_protocol"),
        _scoped_fk(["document_id"], "documents", "fk_ai_full_text_document"),
        _scoped_fk(["document_version_id"], "documents", "fk_ai_full_text_document_version"),
        _scoped_fk(
            ["processing_run_id"], "document_processing_runs", "fk_ai_full_text_processing_run"
        ),
    )
    op.create_index(
        "ix_ai_full_text_assignment",
        "ai_full_text_proposal_links",
        ["organization_id", "review_id", "assignment_id", "created_at"],
    )
    op.create_index(
        "ix_ai_full_text_document",
        "ai_full_text_proposal_links",
        ["organization_id", "review_id", "document_version_id", "created_at"],
    )

    op.create_table(
        "ai_full_text_access_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("access_type", sa.String(30), nullable=False),
        sa.Column("screening_decision_id", sa.Uuid(), nullable=True),
        sa.Column("accessed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "proposal_id", "reviewer_user_id", "access_type", name="uq_ai_full_text_access"
        ),
        sa.CheckConstraint(
            "access_type IN ('ASSISTED_VIEW','POST_DECISION_REVEAL')",
            name="ck_ai_full_text_access_type",
        ),
        sa.CheckConstraint(
            "(access_type = 'ASSISTED_VIEW' AND screening_decision_id IS NULL) OR "
            "(access_type = 'POST_DECISION_REVEAL' AND screening_decision_id IS NOT NULL)",
            name="ck_ai_full_text_access_decision",
        ),
        _scoped_fk(["proposal_id"], "ai_output_proposals", "fk_ai_full_text_access_proposal"),
        _scoped_fk(["assignment_id"], "screening_assignments", "fk_ai_full_text_access_assignment"),
        _member_fk("reviewer_user_id", "fk_ai_full_text_access_reviewer"),
        sa.ForeignKeyConstraint(
            ["screening_decision_id"],
            ["screening_decisions.id"],
            name="fk_ai_full_text_access_canonical_decision",
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "ai_full_text_decision_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("screening_decision_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("human_reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("interaction", sa.String(20), nullable=False),
        sa.Column("disagreement", sa.String(50), nullable=False),
        sa.Column("exclusion_criterion_from_ai", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("screening_decision_id", name="uq_ai_full_text_decision"),
        sa.CheckConstraint(
            "interaction IN ('UNSEEN','VIEWED','ACCEPTED','OVERRIDDEN','DISAGREED')",
            name="ck_ai_full_text_interaction",
        ),
        _scoped_fk(["proposal_id"], "ai_output_proposals", "fk_ai_full_text_decision_proposal"),
        _member_fk("human_reviewer_user_id", "fk_ai_full_text_decision_reviewer"),
        sa.ForeignKeyConstraint(
            ["screening_decision_id"],
            ["screening_decisions.id"],
            name="fk_ai_full_text_decision_canonical",
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "ai_full_text_evaluation_datasets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("logical_key", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("protocol_version_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("reference_standard", sa.String(50), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "organization_id",
            "review_id",
            "logical_key",
            "version",
            name="uq_ai_full_text_dataset_version",
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_full_text_dataset_tenant"
        ),
        sa.CheckConstraint(
            "reference_standard IN ('ADJUDICATED_FULL_TEXT','REVIEWER_CONSENSUS','FINAL_HUMAN_FULL_TEXT','CURATED_DATASET')",
            name="ck_ai_full_text_reference_standard",
        ),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_ai_full_text_dataset_hash"),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_full_text_dataset_review",
            ondelete="CASCADE",
        ),
        _scoped_fk(
            ["protocol_version_id"], "protocol_versions", "fk_ai_full_text_dataset_protocol"
        ),
        _member_fk("created_by_user_id", "fk_ai_full_text_dataset_creator"),
    )

    op.create_table(
        "ai_full_text_evaluation_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("processing_run_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("reference_decision", sa.String(20), nullable=False),
        sa.Column("reference_exclusion_criterion_id", sa.String(200), nullable=True),
        sa.Column("reference_source_type", sa.String(50), nullable=False),
        sa.Column("reference_source_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_snapshot_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("dataset_id", "ordinal", name="uq_ai_full_text_case_ordinal"),
        sa.UniqueConstraint(
            "dataset_id", "document_version_id", name="uq_ai_full_text_case_document"
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_full_text_case_tenant"
        ),
        sa.CheckConstraint(
            "reference_decision IN ('RETAIN','EXCLUDE')", name="ck_ai_full_text_reference_decision"
        ),
        sa.CheckConstraint(
            "document_version_id = document_id", name="ck_ai_full_text_case_document_version"
        ),
        sa.CheckConstraint(
            "length(evidence_snapshot_hash) = 64", name="ck_ai_full_text_case_evidence_hash"
        ),
        _scoped_fk(
            ["dataset_id"], "ai_full_text_evaluation_datasets", "fk_ai_full_text_case_dataset"
        ),
        _scoped_fk(["article_id"], "articles", "fk_ai_full_text_case_article"),
        _scoped_fk(["document_id"], "documents", "fk_ai_full_text_case_document"),
        _scoped_fk(["document_version_id"], "documents", "fk_ai_full_text_case_document_version"),
        _scoped_fk(
            ["processing_run_id"], "document_processing_runs", "fk_ai_full_text_case_processing_run"
        ),
    )

    op.create_table(
        "ai_full_text_evaluation_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("protocol_version_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_version_id", sa.Uuid(), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), nullable=False),
        sa.Column("task_definition_version", sa.Integer(), nullable=False),
        sa.Column("evaluation_policy", sa.String(30), nullable=False),
        sa.Column("metric_version", sa.String(80), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_full_text_result_tenant"
        ),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_ai_full_text_result_hash"),
        _scoped_fk(
            ["dataset_id"], "ai_full_text_evaluation_datasets", "fk_ai_full_text_result_dataset"
        ),
        _scoped_fk(["protocol_version_id"], "protocol_versions", "fk_ai_full_text_result_protocol"),
        sa.ForeignKeyConstraint(
            ["prompt_version_id", "organization_id"],
            ["ai_prompt_template_versions.id", "ai_prompt_template_versions.organization_id"],
            name="fk_ai_full_text_result_prompt",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id", "organization_id"],
            ["ai_model_versions.id", "ai_model_versions.organization_id"],
            name="fk_ai_full_text_result_model",
            ondelete="RESTRICT",
        ),
        _member_fk("created_by_user_id", "fk_ai_full_text_result_creator"),
    )

    op.create_table(
        "ai_full_text_evaluation_case_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("evaluation_result_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("suggestion", sa.String(20), nullable=False),
        sa.Column("reference_decision", sa.String(20), nullable=False),
        sa.Column("model_reported_confidence", sa.Float(), nullable=False),
        sa.Column("proposed_criterion_ids", sa.JSON(), nullable=False),
        sa.Column("reference_criterion_id", sa.String(200), nullable=True),
        sa.Column("criterion_correct", sa.Boolean(), nullable=True),
        sa.Column("evidence_valid", sa.Boolean(), nullable=False),
        sa.Column("evidence_issue_codes", sa.JSON(), nullable=False),
        sa.Column("evidence_sections", sa.JSON(), nullable=False),
        sa.Column("disagreement", sa.String(50), nullable=False),
        sa.UniqueConstraint("evaluation_result_id", "case_id", name="uq_ai_full_text_case_result"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_full_text_case_result_tenant"
        ),
        _scoped_fk(
            ["evaluation_result_id"],
            "ai_full_text_evaluation_results",
            "fk_ai_full_text_case_result_result",
        ),
        _scoped_fk(
            ["case_id"], "ai_full_text_evaluation_cases", "fk_ai_full_text_case_result_case"
        ),
        _scoped_fk(["proposal_id"], "ai_output_proposals", "fk_ai_full_text_case_result_proposal"),
    )

    op.create_table(
        "ai_full_text_error_classifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_result_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("classified_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        _scoped_fk(
            ["case_result_id"], "ai_full_text_evaluation_case_results", "fk_ai_full_text_error_case"
        ),
        _member_fk("classified_by_user_id", "fk_ai_full_text_error_actor"),
    )


def downgrade() -> None:
    op.drop_table("ai_full_text_error_classifications")
    op.drop_table("ai_full_text_evaluation_case_results")
    op.drop_table("ai_full_text_evaluation_results")
    op.drop_table("ai_full_text_evaluation_cases")
    op.drop_table("ai_full_text_evaluation_datasets")
    op.drop_table("ai_full_text_decision_links")
    op.drop_table("ai_full_text_access_events")
    op.drop_index("ix_ai_full_text_document", table_name="ai_full_text_proposal_links")
    op.drop_index("ix_ai_full_text_assignment", table_name="ai_full_text_proposal_links")
    op.drop_table("ai_full_text_proposal_links")
