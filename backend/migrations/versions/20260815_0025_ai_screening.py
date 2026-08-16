"""Add governed AI screening assistance and deterministic evaluation records.

Revision ID: 20260815_0025
Revises: 20260814_0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0025"
down_revision: str | None = "20260814_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _review_fk(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["review_id", "organization_id"],
        ["reviews.id", "reviews.organization_id"],
        name=name,
        ondelete="CASCADE",
    )


def _membership_fk(column: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["organization_id", column],
        ["memberships.organization_id", "memberships.user_id"],
        name=name,
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.create_table(
        "ai_screening_policy_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("maximum_batch_size", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "organization_id", "review_id", "version", name="uq_ai_screening_policy_version"
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_screening_policy_tenant"
        ),
        sa.CheckConstraint("mode IN ('OFF','BLINDED_AI','ASSISTED')", name="ck_ai_screening_mode"),
        sa.CheckConstraint(
            "maximum_batch_size BETWEEN 1 AND 100", name="ck_ai_screening_batch_size"
        ),
        _review_fk("fk_ai_screening_policy_review"),
        _membership_fk("created_by_user_id", "fk_ai_screening_policy_creator"),
    )

    op.create_table(
        "ai_screening_proposal_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("ai_run_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("protocol_version_id", sa.Uuid(), nullable=False),
        sa.Column("protocol_content_hash", sa.String(64), nullable=False),
        sa.Column("eligibility_criteria_hash", sa.String(64), nullable=False),
        sa.Column("exclusion_criteria_hash", sa.String(64), nullable=False),
        sa.Column("citation_content_hash", sa.String(64), nullable=False),
        sa.Column("task_definition_version", sa.Integer(), nullable=False),
        sa.Column("assistance_mode", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("proposal_id", name="uq_ai_screening_proposal_link"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_screening_proposal_link_tenant"
        ),
        sa.CheckConstraint(
            "length(protocol_content_hash) = 64", name="ck_ai_screening_protocol_hash"
        ),
        sa.CheckConstraint(
            "length(eligibility_criteria_hash) = 64",
            name="ck_ai_screening_eligibility_hash",
        ),
        sa.CheckConstraint(
            "length(exclusion_criteria_hash) = 64", name="ck_ai_screening_exclusion_hash"
        ),
        sa.CheckConstraint(
            "length(citation_content_hash) = 64", name="ck_ai_screening_citation_hash"
        ),
        sa.CheckConstraint("task_definition_version > 0", name="ck_ai_screening_task_version"),
        sa.CheckConstraint(
            "assistance_mode IN ('BLINDED_AI','ASSISTED')",
            name="ck_ai_screening_link_mode",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_screening_link_proposal",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            [
                "ai_execution_runs.id",
                "ai_execution_runs.organization_id",
                "ai_execution_runs.review_id",
            ],
            name="fk_ai_screening_link_run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_ai_screening_link_article",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id", "organization_id", "review_id"],
            [
                "screening_assignments.id",
                "screening_assignments.organization_id",
                "screening_assignments.review_id",
            ],
            name="fk_ai_screening_link_assignment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["protocol_version_id", "organization_id", "review_id"],
            [
                "protocol_versions.id",
                "protocol_versions.organization_id",
                "protocol_versions.review_id",
            ],
            name="fk_ai_screening_link_protocol",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_ai_screening_proposal_links_article",
        "ai_screening_proposal_links",
        ["organization_id", "review_id", "article_id", "created_at"],
    )
    op.create_index(
        "ix_ai_screening_proposal_links_assignment",
        "ai_screening_proposal_links",
        ["organization_id", "review_id", "assignment_id", "created_at"],
    )

    op.create_table(
        "ai_screening_access_events",
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
            "proposal_id", "reviewer_user_id", "access_type", name="uq_ai_screening_access"
        ),
        sa.CheckConstraint(
            "access_type IN ('ASSISTED_VIEW','POST_DECISION_REVEAL')",
            name="ck_ai_screening_access_type",
        ),
        sa.CheckConstraint(
            "(access_type = 'ASSISTED_VIEW' AND screening_decision_id IS NULL) OR "
            "(access_type = 'POST_DECISION_REVEAL' AND screening_decision_id IS NOT NULL)",
            name="ck_ai_screening_reveal_decision",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_screening_access_proposal",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id", "organization_id", "review_id"],
            [
                "screening_assignments.id",
                "screening_assignments.organization_id",
                "screening_assignments.review_id",
            ],
            name="fk_ai_screening_access_assignment",
            ondelete="RESTRICT",
        ),
        _membership_fk("reviewer_user_id", "fk_ai_screening_access_reviewer"),
        sa.ForeignKeyConstraint(
            ["screening_decision_id"],
            ["screening_decisions.id"],
            name="fk_ai_screening_access_decision",
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "ai_screening_decision_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("screening_decision_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("human_reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("interaction", sa.String(20), nullable=False),
        sa.Column("disagreement", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("screening_decision_id", name="uq_ai_screening_decision_link"),
        sa.CheckConstraint(
            "interaction IN ('UNSEEN','VIEWED','ACCEPTED','OVERRIDDEN','DISAGREED')",
            name="ck_ai_screening_interaction",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_screening_decision_proposal",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["screening_decision_id"],
            ["screening_decisions.id"],
            name="fk_ai_screening_decision_canonical",
            ondelete="RESTRICT",
        ),
        _membership_fk("human_reviewer_user_id", "fk_ai_screening_decision_reviewer"),
    )

    op.create_table(
        "ai_screening_evaluation_datasets",
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
            name="uq_ai_screening_dataset_version",
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_screening_dataset_tenant"
        ),
        sa.CheckConstraint(
            "reference_standard IN ('ADJUDICATED_TITLE_ABSTRACT','CONSENSUS_DECISION',"
            "'FINAL_FULL_TEXT_INCLUSION','CURATED_DATASET')",
            name="ck_ai_screening_reference_standard",
        ),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_ai_screening_dataset_hash"),
        _review_fk("fk_ai_screening_dataset_review"),
        sa.ForeignKeyConstraint(
            ["protocol_version_id", "organization_id", "review_id"],
            [
                "protocol_versions.id",
                "protocol_versions.organization_id",
                "protocol_versions.review_id",
            ],
            name="fk_ai_screening_dataset_protocol",
            ondelete="RESTRICT",
        ),
        _membership_fk("created_by_user_id", "fk_ai_screening_dataset_creator"),
    )

    op.create_table(
        "ai_screening_evaluation_cases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("reference_decision", sa.String(20), nullable=False),
        sa.Column("reference_source_type", sa.String(50), nullable=False),
        sa.Column("reference_source_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("dataset_id", "ordinal", name="uq_ai_screening_case_ordinal"),
        sa.UniqueConstraint("dataset_id", "article_id", name="uq_ai_screening_case_article"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_screening_case_tenant"
        ),
        sa.CheckConstraint(
            "reference_decision IN ('RETAIN','EXCLUDE')",
            name="ck_ai_screening_reference_decision",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id", "organization_id", "review_id"],
            [
                "ai_screening_evaluation_datasets.id",
                "ai_screening_evaluation_datasets.organization_id",
                "ai_screening_evaluation_datasets.review_id",
            ],
            name="fk_ai_screening_case_dataset",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_ai_screening_case_article",
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "ai_screening_evaluation_results",
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
        sa.Column("calibration", sa.JSON(), nullable=False),
        sa.Column("threshold_simulation", sa.JSON(), nullable=False),
        sa.Column("high_risk_disagreements", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_screening_result_tenant"
        ),
        sa.CheckConstraint(
            "evaluation_policy IN ('CONSERVATIVE','STRICT_MODEL_DECISION','COVERAGE_ONLY')",
            name="ck_ai_screening_evaluation_policy",
        ),
        sa.CheckConstraint(
            "task_definition_version > 0", name="ck_ai_screening_result_task_version"
        ),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_ai_screening_result_hash"),
        sa.ForeignKeyConstraint(
            ["dataset_id", "organization_id", "review_id"],
            [
                "ai_screening_evaluation_datasets.id",
                "ai_screening_evaluation_datasets.organization_id",
                "ai_screening_evaluation_datasets.review_id",
            ],
            name="fk_ai_screening_result_dataset",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["protocol_version_id", "organization_id", "review_id"],
            [
                "protocol_versions.id",
                "protocol_versions.organization_id",
                "protocol_versions.review_id",
            ],
            name="fk_ai_screening_result_protocol",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_version_id", "organization_id"],
            ["ai_prompt_template_versions.id", "ai_prompt_template_versions.organization_id"],
            name="fk_ai_screening_result_prompt",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id", "organization_id"],
            ["ai_model_versions.id", "ai_model_versions.organization_id"],
            name="fk_ai_screening_result_model",
            ondelete="RESTRICT",
        ),
        _membership_fk("created_by_user_id", "fk_ai_screening_result_creator"),
    )

    op.create_table(
        "ai_screening_evaluation_case_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("evaluation_result_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False),
        sa.Column("suggestion", sa.String(20), nullable=False),
        sa.Column("reference_decision", sa.String(20), nullable=False),
        sa.Column("model_reported_confidence", sa.Float(), nullable=False),
        sa.Column("disagreement", sa.String(50), nullable=False),
        sa.UniqueConstraint("evaluation_result_id", "case_id", name="uq_ai_screening_case_result"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_screening_case_result_tenant"
        ),
        sa.CheckConstraint(
            "suggestion IN ('INCLUDE','EXCLUDE','MAYBE','ABSTAIN')",
            name="ck_ai_screening_case_suggestion",
        ),
        sa.CheckConstraint(
            "reference_decision IN ('RETAIN','EXCLUDE')",
            name="ck_ai_screening_case_result_reference",
        ),
        sa.CheckConstraint(
            "model_reported_confidence >= 0 AND model_reported_confidence <= 1",
            name="ck_ai_screening_case_confidence",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_result_id", "organization_id", "review_id"],
            [
                "ai_screening_evaluation_results.id",
                "ai_screening_evaluation_results.organization_id",
                "ai_screening_evaluation_results.review_id",
            ],
            name="fk_ai_screening_case_result_result",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["case_id", "organization_id", "review_id"],
            [
                "ai_screening_evaluation_cases.id",
                "ai_screening_evaluation_cases.organization_id",
                "ai_screening_evaluation_cases.review_id",
            ],
            name="fk_ai_screening_case_result_case",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_screening_case_result_proposal",
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "ai_screening_error_classifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_result_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("classified_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "category IN ('POPULATION_MISUNDERSTANDING','INTERVENTION_MISUNDERSTANDING',"
            "'COMPARATOR_MISUNDERSTANDING','OUTCOME_MISUNDERSTANDING','DESIGN_MISUNDERSTANDING',"
            "'LANGUAGE_OR_PUBLICATION_TYPE','MISSING_INFORMATION','CRITERION_AMBIGUITY',"
            "'HALLUCINATED_CRITERION','OTHER')",
            name="ck_ai_screening_error_category",
        ),
        sa.ForeignKeyConstraint(
            ["case_result_id", "organization_id", "review_id"],
            [
                "ai_screening_evaluation_case_results.id",
                "ai_screening_evaluation_case_results.organization_id",
                "ai_screening_evaluation_case_results.review_id",
            ],
            name="fk_ai_screening_error_case",
            ondelete="RESTRICT",
        ),
        _membership_fk("classified_by_user_id", "fk_ai_screening_error_actor"),
    )


def downgrade() -> None:
    op.drop_table("ai_screening_error_classifications")
    op.drop_table("ai_screening_evaluation_case_results")
    op.drop_table("ai_screening_evaluation_results")
    op.drop_table("ai_screening_evaluation_cases")
    op.drop_table("ai_screening_evaluation_datasets")
    op.drop_table("ai_screening_decision_links")
    op.drop_table("ai_screening_access_events")
    op.drop_index(
        "ix_ai_screening_proposal_links_assignment", table_name="ai_screening_proposal_links"
    )
    op.drop_index(
        "ix_ai_screening_proposal_links_article", table_name="ai_screening_proposal_links"
    )
    op.drop_table("ai_screening_proposal_links")
    op.drop_table("ai_screening_policy_versions")
