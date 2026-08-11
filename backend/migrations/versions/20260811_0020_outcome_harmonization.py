"""Add outcome and effect-estimate harmonization foundation.

Revision ID: 20260811_0020
Revises: 20260811_0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0020"
down_revision: str | None = "20260811_0019"
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
        "outcome_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "review_id", "key", name="uq_outcome_key"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_outcome_id_tenant"),
        _review_fk("fk_outcome_review_tenant"),
        _actor_fk("created_by_user_id", "fk_outcome_creator_membership"),
    )
    op.create_table(
        "outcome_timepoint_windows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("anchor", sa.String(30), nullable=False),
        sa.Column("minimum_days", sa.Numeric(30, 12)),
        sa.Column("maximum_days", sa.Numeric(30, 12)),
        sa.Column("rule_version", sa.String(100), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "minimum_days IS NULL OR minimum_days >= 0", name="ck_timepoint_minimum"
        ),
        sa.CheckConstraint(
            "maximum_days IS NULL OR maximum_days >= 0", name="ck_timepoint_maximum"
        ),
        sa.CheckConstraint(
            "minimum_days IS NULL OR maximum_days IS NULL OR minimum_days <= maximum_days",
            name="ck_timepoint_range",
        ),
        sa.CheckConstraint(
            "anchor IN ('BASELINE','RANDOMIZATION','INTERVENTION_START','DIAGNOSIS','OTHER')",
            name="ck_timepoint_anchor",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "review_id", "key", "rule_version", name="uq_timepoint_window_rule"
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_timepoint_window_tenant"
        ),
        _review_fk("fk_timepoint_window_review_tenant"),
        _actor_fk("created_by_user_id", "fk_timepoint_window_creator_membership"),
    )
    op.create_table(
        "outcome_unit_definitions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("dimension", sa.String(120), nullable=False),
        sa.Column("context_key", sa.String(120), nullable=False),
        sa.Column("base_unit_key", sa.String(120), nullable=False),
        sa.Column("multiplier_to_base", sa.Numeric(38, 18), nullable=False),
        sa.Column("offset_to_base", sa.Numeric(38, 18), nullable=False),
        sa.Column("precision", sa.Integer(), nullable=False),
        sa.Column("rule_version", sa.String(100), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("multiplier_to_base > 0", name="ck_unit_multiplier_positive"),
        sa.CheckConstraint("precision >= 0 AND precision <= 18", name="ck_unit_precision"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "review_id", "key", "rule_version", name="uq_unit_rule"
        ),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_unit_id_tenant"),
        _review_fk("fk_unit_review_tenant"),
        _actor_fk("created_by_user_id", "fk_unit_creator_membership"),
    )
    op.create_table(
        "outcome_measurement_scales",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("minimum", sa.Numeric(30, 12)),
        sa.Column("maximum", sa.Numeric(30, 12)),
        sa.Column("directionality", sa.String(30), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "minimum IS NULL OR maximum IS NULL OR minimum < maximum",
            name="ck_measurement_scale_range",
        ),
        sa.CheckConstraint(
            "directionality IN ('HIGHER_BETTER','HIGHER_WORSE','NEUTRAL','NOT_APPLICABLE','UNKNOWN')",
            name="ck_measurement_scale_direction",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "review_id", "key", name="uq_measurement_scale_key"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_measurement_scale_tenant"
        ),
        _review_fk("fk_measurement_scale_review_tenant"),
        _actor_fk("created_by_user_id", "fk_measurement_scale_creator_membership"),
    )
    op.create_table(
        "outcome_definition_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("outcome_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("protocol_version_id", sa.Uuid()),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("version > 0", name="ck_outcome_version_positive"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_outcome_version_hash"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outcome_id", "version", name="uq_outcome_version_number"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_outcome_version_tenant"),
        sa.ForeignKeyConstraint(
            ["outcome_id", "organization_id", "review_id"],
            [
                "outcome_definitions.id",
                "outcome_definitions.organization_id",
                "outcome_definitions.review_id",
            ],
            name="fk_outcome_version_outcome_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["protocol_version_id", "organization_id", "review_id"],
            [
                "protocol_versions.id",
                "protocol_versions.organization_id",
                "protocol_versions.review_id",
            ],
            name="fk_outcome_version_protocol_tenant",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_outcome_version_creator_membership"),
    )
    op.create_table(
        "outcome_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_value_id", sa.Uuid(), nullable=False),
        sa.Column("outcome_version_id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("reported_value", sa.Numeric(38, 12)),
        sa.Column("reported_unit", sa.String(120)),
        sa.Column("reported_unit_id", sa.Uuid()),
        sa.Column("normalized_value", sa.Numeric(38, 12)),
        sa.Column("normalized_unit_id", sa.Uuid()),
        sa.Column("conversion_rule_version", sa.String(100)),
        sa.Column("reported_time_value", sa.Numeric(30, 12)),
        sa.Column("reported_time_unit", sa.String(20)),
        sa.Column("reported_time_anchor", sa.String(30)),
        sa.Column("normalized_time_days", sa.Numeric(30, 12)),
        sa.Column("timepoint_window_id", sa.Uuid()),
        sa.Column("timepoint_rule_version", sa.String(100)),
        sa.Column("measurement_scale_id", sa.Uuid()),
        sa.Column("direction_transformation", sa.String(30), nullable=False),
        sa.Column("transformation_reason", sa.Text()),
        sa.Column("extraction_verified", sa.Boolean(), nullable=False),
        sa.Column("supersedes_mapping_id", sa.Uuid()),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_outcome_mapping_tenant"),
        sa.UniqueConstraint("supersedes_mapping_id", name="uq_outcome_mapping_single_successor"),
        sa.ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_outcome_mapping_study_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_value_id", "organization_id", "review_id"],
            [
                "extraction_values.id",
                "extraction_values.organization_id",
                "extraction_values.review_id",
            ],
            name="fk_outcome_mapping_extraction_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["outcome_version_id", "organization_id", "review_id"],
            [
                "outcome_definition_versions.id",
                "outcome_definition_versions.organization_id",
                "outcome_definition_versions.review_id",
            ],
            name="fk_outcome_mapping_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reported_unit_id", "organization_id", "review_id"],
            [
                "outcome_unit_definitions.id",
                "outcome_unit_definitions.organization_id",
                "outcome_unit_definitions.review_id",
            ],
            name="fk_outcome_mapping_reported_unit_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["normalized_unit_id", "organization_id", "review_id"],
            [
                "outcome_unit_definitions.id",
                "outcome_unit_definitions.organization_id",
                "outcome_unit_definitions.review_id",
            ],
            name="fk_outcome_mapping_normalized_unit_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["timepoint_window_id", "organization_id", "review_id"],
            [
                "outcome_timepoint_windows.id",
                "outcome_timepoint_windows.organization_id",
                "outcome_timepoint_windows.review_id",
            ],
            name="fk_outcome_mapping_timepoint_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["measurement_scale_id", "organization_id", "review_id"],
            [
                "outcome_measurement_scales.id",
                "outcome_measurement_scales.organization_id",
                "outcome_measurement_scales.review_id",
            ],
            name="fk_outcome_mapping_scale_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_mapping_id", "organization_id", "review_id"],
            [
                "outcome_mappings.id",
                "outcome_mappings.organization_id",
                "outcome_mappings.review_id",
            ],
            name="fk_outcome_mapping_successor_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "method IN ('MANUAL','DETERMINISTIC_RULE','IMPORTED')",
            name="ck_outcome_mapping_method",
        ),
        sa.CheckConstraint(
            "reported_time_unit IS NULL OR reported_time_unit IN ('DAY','WEEK','MONTH','YEAR')",
            name="ck_outcome_mapping_time_unit",
        ),
        sa.CheckConstraint(
            "reported_time_anchor IS NULL OR reported_time_anchor IN ('BASELINE','RANDOMIZATION','INTERVENTION_START','DIAGNOSIS','OTHER')",
            name="ck_outcome_mapping_time_anchor",
        ),
        sa.CheckConstraint(
            "direction_transformation IN ('NONE','SIGN_REVERSED')",
            name="ck_outcome_mapping_direction_transform",
        ),
        _actor_fk("created_by_user_id", "fk_outcome_mapping_actor_membership"),
    )
    op.create_index(
        "ix_outcome_mappings_review_study",
        "outcome_mappings",
        ["organization_id", "review_id", "study_id", "outcome_version_id", "id"],
    )
    op.create_table(
        "effect_estimates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("outcome_version_id", sa.Uuid(), nullable=False),
        sa.Column("effect_measure", sa.String(30), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False),
        sa.Column("estimate", sa.Numeric(38, 12)),
        sa.Column("standard_error", sa.Numeric(38, 12)),
        sa.Column("variance", sa.Numeric(38, 12)),
        sa.Column("variance_scale", sa.String(20), nullable=False),
        sa.Column("ci_lower", sa.Numeric(38, 12)),
        sa.Column("ci_upper", sa.Numeric(38, 12)),
        sa.Column("confidence_level", sa.Numeric(8, 6)),
        sa.Column("adjustment", sa.String(20), nullable=False),
        sa.Column("analysis_population", sa.String(30), nullable=False),
        sa.Column("covariates", sa.Text()),
        sa.Column("model_description", sa.Text()),
        sa.Column("timepoint_window_id", sa.Uuid()),
        sa.Column("unit_id", sa.Uuid()),
        sa.Column("measurement_scale_id", sa.Uuid()),
        sa.Column("components", sa.JSON(), nullable=False),
        sa.Column("source_mapping_ids", sa.JSON(), nullable=False),
        sa.Column("source_evidence_location_id", sa.Uuid()),
        sa.Column("calculation_version", sa.String(100)),
        sa.Column("zero_event_pattern", sa.String(30), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_effect_estimate_tenant"),
        sa.ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_effect_estimate_study_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["outcome_version_id", "organization_id", "review_id"],
            [
                "outcome_definition_versions.id",
                "outcome_definition_versions.organization_id",
                "outcome_definition_versions.review_id",
            ],
            name="fk_effect_estimate_outcome_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["timepoint_window_id", "organization_id", "review_id"],
            [
                "outcome_timepoint_windows.id",
                "outcome_timepoint_windows.organization_id",
                "outcome_timepoint_windows.review_id",
            ],
            name="fk_effect_estimate_timepoint_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id", "organization_id", "review_id"],
            [
                "outcome_unit_definitions.id",
                "outcome_unit_definitions.organization_id",
                "outcome_unit_definitions.review_id",
            ],
            name="fk_effect_estimate_unit_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["measurement_scale_id", "organization_id", "review_id"],
            [
                "outcome_measurement_scales.id",
                "outcome_measurement_scales.organization_id",
                "outcome_measurement_scales.review_id",
            ],
            name="fk_effect_estimate_scale_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_evidence_location_id", "organization_id", "review_id"],
            [
                "document_evidence_locations.id",
                "document_evidence_locations.organization_id",
                "document_evidence_locations.review_id",
            ],
            name="fk_effect_estimate_evidence_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "effect_measure IN ('RR','OR','RD','MD','SMD','HR','PROPORTION','MEAN','RATE')",
            name="ck_effect_measure",
        ),
        sa.CheckConstraint("origin IN ('REPORTED','DERIVED')", name="ck_effect_origin"),
        sa.CheckConstraint("variance_scale IN ('NATURAL','LOG')", name="ck_effect_variance_scale"),
        sa.CheckConstraint("adjustment IN ('UNADJUSTED','ADJUSTED')", name="ck_effect_adjustment"),
        sa.CheckConstraint(
            "analysis_population IN ('INTENTION_TO_TREAT','PER_PROTOCOL','MODIFIED_ITT','SAFETY','UNCLEAR','OTHER')",
            name="ck_effect_population",
        ),
        sa.CheckConstraint(
            "zero_event_pattern IN ('NONE','INTERVENTION_ONLY','COMPARATOR_ONLY','DOUBLE_ZERO','BOUNDARY_CELL')",
            name="ck_effect_zero_pattern",
        ),
        _actor_fk("created_by_user_id", "fk_effect_estimate_actor_membership"),
    )
    op.create_index(
        "ix_effect_estimates_review_outcome",
        "effect_estimates",
        ["organization_id", "review_id", "outcome_version_id", "study_id", "effect_measure", "id"],
    )
    op.create_table(
        "effect_estimate_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("effect_estimate_id", sa.Uuid(), nullable=False),
        sa.Column("mapping_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.CheckConstraint("ordinal > 0", name="ck_effect_source_ordinal"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("effect_estimate_id", "mapping_id", name="uq_effect_source_mapping"),
        sa.ForeignKeyConstraint(
            ["effect_estimate_id", "organization_id", "review_id"],
            [
                "effect_estimates.id",
                "effect_estimates.organization_id",
                "effect_estimates.review_id",
            ],
            name="fk_effect_source_estimate_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["mapping_id", "organization_id", "review_id"],
            [
                "outcome_mappings.id",
                "outcome_mappings.organization_id",
                "outcome_mappings.review_id",
            ],
            name="fk_effect_source_mapping_tenant",
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "synthesis_candidate_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("outcome_version_id", sa.Uuid(), nullable=False),
        sa.Column("effect_measure", sa.String(30), nullable=False),
        sa.Column("timepoint_window_id", sa.Uuid()),
        sa.Column("population_label", sa.String(300)),
        sa.Column("estimate_ids", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_candidate_set_tenant"),
        sa.ForeignKeyConstraint(
            ["outcome_version_id", "organization_id", "review_id"],
            [
                "outcome_definition_versions.id",
                "outcome_definition_versions.organization_id",
                "outcome_definition_versions.review_id",
            ],
            name="fk_candidate_set_outcome_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["timepoint_window_id", "organization_id", "review_id"],
            [
                "outcome_timepoint_windows.id",
                "outcome_timepoint_windows.organization_id",
                "outcome_timepoint_windows.review_id",
            ],
            name="fk_candidate_set_timepoint_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "effect_measure IN ('RR','OR','RD','MD','SMD','HR','PROPORTION','MEAN','RATE')",
            name="ck_candidate_effect_measure",
        ),
        _actor_fk("created_by_user_id", "fk_candidate_set_actor_membership"),
    )
    op.create_table(
        "analysis_readiness_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_set_id", sa.Uuid(), nullable=False),
        sa.Column("algorithm_version", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("blockers", sa.JSON(), nullable=False),
        sa.Column("evaluated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_readiness_snapshot_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["candidate_set_id", "organization_id", "review_id"],
            [
                "synthesis_candidate_sets.id",
                "synthesis_candidate_sets.organization_id",
                "synthesis_candidate_sets.review_id",
            ],
            name="fk_readiness_candidate_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('READY','NOT_READY','NEEDS_HARMONIZATION','NEEDS_REVIEW')",
            name="ck_readiness_status",
        ),
        _actor_fk("evaluated_by_user_id", "fk_readiness_actor_membership"),
    )
    op.create_table(
        "synthesis_candidate_estimates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_set_id", sa.Uuid(), nullable=False),
        sa.Column("estimate_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.CheckConstraint("ordinal > 0", name="ck_candidate_estimate_ordinal"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_set_id", "estimate_id", name="uq_candidate_estimate"),
        sa.ForeignKeyConstraint(
            ["candidate_set_id", "organization_id", "review_id"],
            [
                "synthesis_candidate_sets.id",
                "synthesis_candidate_sets.organization_id",
                "synthesis_candidate_sets.review_id",
            ],
            name="fk_candidate_estimate_set_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["estimate_id", "organization_id", "review_id"],
            [
                "effect_estimates.id",
                "effect_estimates.organization_id",
                "effect_estimates.review_id",
            ],
            name="fk_candidate_estimate_effect_tenant",
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    op.drop_table("synthesis_candidate_estimates")
    op.drop_table("analysis_readiness_snapshots")
    op.drop_table("synthesis_candidate_sets")
    op.drop_table("effect_estimate_sources")
    op.drop_index("ix_effect_estimates_review_outcome", table_name="effect_estimates")
    op.drop_table("effect_estimates")
    op.drop_index("ix_outcome_mappings_review_study", table_name="outcome_mappings")
    op.drop_table("outcome_mappings")
    op.drop_table("outcome_definition_versions")
    op.drop_table("outcome_measurement_scales")
    op.drop_table("outcome_unit_definitions")
    op.drop_table("outcome_timepoint_windows")
    op.drop_table("outcome_definitions")
