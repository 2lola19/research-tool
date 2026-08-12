"""Add deterministic statistical synthesis foundation.

Revision ID: 20260812_0021
Revises: 20260811_0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0021"
down_revision: str | None = "20260811_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _review_fk(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["review_id", "organization_id"],
        ["reviews.id", "reviews.organization_id"],
        name=name,
        ondelete="CASCADE",
    )


def _actor_fk(column: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["organization_id", column],
        ["memberships.organization_id", "memberships.user_id"],
        name=name,
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    op.create_table(
        "analysis_specifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "review_id", "key", name="uq_analysis_spec_key"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_analysis_spec_tenant"),
        _review_fk("fk_analysis_spec_review_tenant"),
        _actor_fk("created_by_user_id", "fk_analysis_spec_creator_membership"),
    )
    op.create_table(
        "analysis_specification_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("specification_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("outcome_version_id", sa.Uuid(), nullable=False),
        sa.Column("timepoint_window_id", sa.Uuid()),
        sa.Column("effect_measure", sa.String(30), nullable=False),
        sa.Column("model", sa.String(30), nullable=False),
        sa.Column("heterogeneity_estimator", sa.String(40), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("version > 0", name="ck_analysis_spec_version_positive"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_analysis_spec_version_hash"),
        sa.CheckConstraint(
            "effect_measure IN ('RR','OR','RD','MD','SMD','HR','PROPORTION','MEAN','RATE')",
            name="ck_analysis_spec_effect_measure",
        ),
        sa.CheckConstraint(
            "model IN ('FIXED_EFFECT','RANDOM_EFFECTS')", name="ck_analysis_spec_model"
        ),
        sa.CheckConstraint(
            "heterogeneity_estimator IN ('NONE','DERSIMONIAN_LAIRD')",
            name="ck_analysis_spec_estimator",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("specification_id", "version", name="uq_analysis_spec_version"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_analysis_spec_version_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["specification_id", "organization_id", "review_id"],
            [
                "analysis_specifications.id",
                "analysis_specifications.organization_id",
                "analysis_specifications.review_id",
            ],
            name="fk_analysis_spec_version_spec_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["outcome_version_id", "organization_id", "review_id"],
            [
                "outcome_definition_versions.id",
                "outcome_definition_versions.organization_id",
                "outcome_definition_versions.review_id",
            ],
            name="fk_analysis_spec_version_outcome_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["timepoint_window_id", "organization_id", "review_id"],
            [
                "outcome_timepoint_windows.id",
                "outcome_timepoint_windows.organization_id",
                "outcome_timepoint_windows.review_id",
            ],
            name="fk_analysis_spec_version_timepoint_tenant",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_analysis_spec_version_creator_membership"),
    )
    op.create_table(
        "analysis_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("specification_version_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_set_id", sa.Uuid(), nullable=False),
        sa.Column("included_estimate_ids", sa.JSON(), nullable=False),
        sa.Column("excluded_estimates", sa.JSON(), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("length(input_hash) = 64", name="ck_analysis_set_hash"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_analysis_set_tenant"),
        sa.ForeignKeyConstraint(
            ["specification_version_id", "organization_id", "review_id"],
            [
                "analysis_specification_versions.id",
                "analysis_specification_versions.organization_id",
                "analysis_specification_versions.review_id",
            ],
            name="fk_analysis_set_spec_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_set_id", "organization_id", "review_id"],
            [
                "synthesis_candidate_sets.id",
                "synthesis_candidate_sets.organization_id",
                "synthesis_candidate_sets.review_id",
            ],
            name="fk_analysis_set_candidate_tenant",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_analysis_set_creator_membership"),
    )
    op.create_index(
        "ix_analysis_set_spec",
        "analysis_sets",
        ["organization_id", "review_id", "specification_version_id"],
    )
    op.create_table(
        "analysis_set_estimates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_set_id", sa.Uuid(), nullable=False),
        sa.Column("estimate_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.CheckConstraint("ordinal > 0", name="ck_analysis_set_estimate_ordinal"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_set_id", "estimate_id", name="uq_analysis_set_estimate"),
        sa.UniqueConstraint("analysis_set_id", "ordinal", name="uq_analysis_set_estimate_ordinal"),
        sa.ForeignKeyConstraint(
            ["analysis_set_id", "organization_id", "review_id"],
            ["analysis_sets.id", "analysis_sets.organization_id", "analysis_sets.review_id"],
            name="fk_analysis_set_estimate_set_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["estimate_id", "organization_id", "review_id"],
            [
                "effect_estimates.id",
                "effect_estimates.organization_id",
                "effect_estimates.review_id",
            ],
            name="fk_analysis_set_estimate_effect_tenant",
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "meta_analysis_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("specification_version_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_set_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("algorithm_name", sa.String(100), nullable=False),
        sa.Column("algorithm_version", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("provider_version", sa.String(100), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("result_hash", sa.String(64)),
        sa.Column("result", sa.JSON()),
        sa.Column("diagnostics", sa.JSON(), nullable=False),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('PLANNED','RUNNING','COMPLETED','FAILED')", name="ck_meta_run_status"
        ),
        sa.CheckConstraint("length(input_hash) = 64", name="ck_meta_run_input_hash"),
        sa.CheckConstraint(
            "result_hash IS NULL OR length(result_hash) = 64", name="ck_meta_run_result_hash"
        ),
        sa.CheckConstraint(
            "(status = 'COMPLETED' AND result_hash IS NOT NULL "
            "AND completed_at IS NOT NULL AND failure_reason IS NULL) OR "
            "(status = 'FAILED' AND result_hash IS NULL "
            "AND completed_at IS NOT NULL AND failure_reason IS NOT NULL) OR "
            "(status IN ('PLANNED','RUNNING') AND result_hash IS NULL "
            "AND completed_at IS NULL)",
            name="ck_meta_run_terminal_state",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_meta_run_tenant"),
        sa.ForeignKeyConstraint(
            ["specification_version_id", "organization_id", "review_id"],
            [
                "analysis_specification_versions.id",
                "analysis_specification_versions.organization_id",
                "analysis_specification_versions.review_id",
            ],
            name="fk_meta_run_spec_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_set_id", "organization_id", "review_id"],
            ["analysis_sets.id", "analysis_sets.organization_id", "analysis_sets.review_id"],
            name="fk_meta_run_analysis_set_tenant",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_meta_run_creator_membership"),
    )
    op.create_index(
        "ix_meta_run_analysis_set",
        "meta_analysis_runs",
        ["organization_id", "review_id", "analysis_set_id"],
    )
    op.create_table(
        "meta_analysis_study_weights",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("estimate_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_estimate", sa.Numeric(38, 12), nullable=False),
        sa.Column("presentation_estimate", sa.Numeric(38, 12), nullable=False),
        sa.Column("ci_lower", sa.Numeric(38, 12), nullable=False),
        sa.Column("ci_upper", sa.Numeric(38, 12), nullable=False),
        sa.Column("raw_weight", sa.Numeric(38, 12), nullable=False),
        sa.Column("normalized_weight_percent", sa.Numeric(38, 12), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "study_id", name="uq_meta_weight_study"),
        sa.UniqueConstraint("run_id", "estimate_id", name="uq_meta_weight_estimate"),
        sa.ForeignKeyConstraint(
            ["run_id", "organization_id", "review_id"],
            [
                "meta_analysis_runs.id",
                "meta_analysis_runs.organization_id",
                "meta_analysis_runs.review_id",
            ],
            name="fk_meta_weight_run_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_meta_weight_study_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["estimate_id", "organization_id", "review_id"],
            [
                "effect_estimates.id",
                "effect_estimates.organization_id",
                "effect_estimates.review_id",
            ],
            name="fk_meta_weight_estimate_tenant",
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "meta_analysis_sensitivity_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("omitted_study_id", sa.Uuid(), nullable=False),
        sa.Column("omitted_estimate_id", sa.Uuid(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("result_hash", sa.String(64), nullable=False),
        sa.CheckConstraint("length(result_hash) = 64", name="ck_meta_sensitivity_hash"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "omitted_study_id", name="uq_meta_sensitivity_study"),
        sa.ForeignKeyConstraint(
            ["run_id", "organization_id", "review_id"],
            [
                "meta_analysis_runs.id",
                "meta_analysis_runs.organization_id",
                "meta_analysis_runs.review_id",
            ],
            name="fk_meta_sensitivity_run_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["omitted_study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_meta_sensitivity_study_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["omitted_estimate_id", "organization_id", "review_id"],
            [
                "effect_estimates.id",
                "effect_estimates.organization_id",
                "effect_estimates.review_id",
            ],
            name="fk_meta_sensitivity_estimate_tenant",
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "analysis_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(40), nullable=False),
        sa.Column("renderer_version", sa.String(100), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("byte_size >= 0", name="ck_analysis_artifact_size"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_analysis_artifact_hash"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_analysis_artifact_tenant"
        ),
        sa.UniqueConstraint(
            "run_id", "artifact_type", "renderer_version", name="uq_analysis_artifact_run"
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "organization_id", "review_id"],
            [
                "meta_analysis_runs.id",
                "meta_analysis_runs.organization_id",
                "meta_analysis_runs.review_id",
            ],
            name="fk_analysis_artifact_run_tenant",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_analysis_artifact_creator_membership"),
    )


def downgrade() -> None:
    op.drop_table("analysis_artifacts")
    op.drop_table("meta_analysis_sensitivity_results")
    op.drop_table("meta_analysis_study_weights")
    op.drop_index("ix_meta_run_analysis_set", table_name="meta_analysis_runs")
    op.drop_table("meta_analysis_runs")
    op.drop_table("analysis_set_estimates")
    op.drop_index("ix_analysis_set_spec", table_name="analysis_sets")
    op.drop_table("analysis_sets")
    op.drop_table("analysis_specification_versions")
    op.drop_table("analysis_specifications")
