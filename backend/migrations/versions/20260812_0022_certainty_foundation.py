"""Add structured certainty-of-evidence foundation.

Revision ID: 20260812_0022
Revises: 20260812_0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0022"
down_revision: str | None = "20260812_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id() -> sa.Column[sa.Uuid]:
    return sa.Column("id", sa.Uuid(), primary_key=True)


def _scope() -> tuple[sa.Column[sa.Uuid], sa.Column[sa.Uuid]]:
    return sa.Column("organization_id", sa.Uuid(), nullable=False), sa.Column(
        "review_id", sa.Uuid(), nullable=False
    )


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
        "certainty_frameworks",
        _id(),
        *_scope(),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("organization_id", "review_id", "key", name="uq_cert_framework_key"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_cert_framework_tenant"),
        _review_fk("fk_cert_framework_review"),
        _actor_fk("created_by_user_id", "fk_cert_framework_actor"),
    )
    op.create_table(
        "certainty_framework_versions",
        _id(),
        sa.Column("framework_id", sa.Uuid(), nullable=False),
        *_scope(),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("framework_id", "version", name="uq_cert_framework_version"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_cert_version_tenant"),
        sa.ForeignKeyConstraint(
            ["framework_id", "organization_id", "review_id"],
            [
                "certainty_frameworks.id",
                "certainty_frameworks.organization_id",
                "certainty_frameworks.review_id",
            ],
            name="fk_cert_version_framework",
            ondelete="CASCADE",
        ),
        _actor_fk("created_by_user_id", "fk_cert_version_actor"),
        sa.CheckConstraint("version > 0", name="ck_cert_version_positive"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_cert_version_hash"),
    )
    op.create_table(
        "certainty_threshold_versions",
        _id(),
        *_scope(),
        sa.Column("outcome_version_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("outcome_version_id", "version", name="uq_cert_threshold_version"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_cert_threshold_tenant"),
        sa.ForeignKeyConstraint(
            ["outcome_version_id", "organization_id", "review_id"],
            [
                "outcome_definition_versions.id",
                "outcome_definition_versions.organization_id",
                "outcome_definition_versions.review_id",
            ],
            name="fk_cert_threshold_outcome",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_cert_threshold_actor"),
        sa.CheckConstraint("version > 0", name="ck_cert_threshold_version"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_cert_threshold_hash"),
    )
    op.create_table(
        "certainty_assessments",
        _id(),
        *_scope(),
        sa.Column("outcome_version_id", sa.Uuid(), nullable=False),
        sa.Column("timepoint_window_id", sa.Uuid()),
        sa.Column("analysis_specification_version_id", sa.Uuid()),
        sa.Column("meta_analysis_run_id", sa.Uuid()),
        sa.Column("framework_version_id", sa.Uuid(), nullable=False),
        sa.Column("threshold_version_id", sa.Uuid()),
        sa.Column("assessor_user_id", sa.Uuid(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("supersedes_assessment_id", sa.Uuid()),
        sa.Column("evidence_body_type", sa.String(30), nullable=False),
        sa.Column("evidence_body", sa.JSON(), nullable=False),
        sa.Column("starting_certainty", sa.String(20), nullable=False),
        sa.Column("starting_rationale", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("candidate_certainty", sa.String(20)),
        sa.Column("final_certainty", sa.String(20)),
        sa.Column("final_rationale", sa.Text()),
        sa.Column("override_reason", sa.Text()),
        sa.Column("evidence_snapshot", sa.JSON()),
        sa.Column("evidence_hash", sa.String(64)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_cert_assessment_tenant"),
        sa.UniqueConstraint(
            "review_id",
            "outcome_version_id",
            "framework_version_id",
            "assessor_user_id",
            "round_number",
            "revision",
            name="uq_cert_assessment_revision",
        ),
        _review_fk("fk_cert_assessment_review"),
        _actor_fk("assessor_user_id", "fk_cert_assessment_assessor"),
        sa.ForeignKeyConstraint(
            ["outcome_version_id", "organization_id", "review_id"],
            [
                "outcome_definition_versions.id",
                "outcome_definition_versions.organization_id",
                "outcome_definition_versions.review_id",
            ],
            name="fk_cert_assessment_outcome",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["timepoint_window_id", "organization_id", "review_id"],
            [
                "outcome_timepoint_windows.id",
                "outcome_timepoint_windows.organization_id",
                "outcome_timepoint_windows.review_id",
            ],
            name="fk_cert_assessment_timepoint",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_specification_version_id", "organization_id", "review_id"],
            [
                "analysis_specification_versions.id",
                "analysis_specification_versions.organization_id",
                "analysis_specification_versions.review_id",
            ],
            name="fk_cert_assessment_spec",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["meta_analysis_run_id", "organization_id", "review_id"],
            [
                "meta_analysis_runs.id",
                "meta_analysis_runs.organization_id",
                "meta_analysis_runs.review_id",
            ],
            name="fk_cert_assessment_run",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["framework_version_id", "organization_id", "review_id"],
            [
                "certainty_framework_versions.id",
                "certainty_framework_versions.organization_id",
                "certainty_framework_versions.review_id",
            ],
            name="fk_cert_assessment_framework",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["threshold_version_id", "organization_id", "review_id"],
            [
                "certainty_threshold_versions.id",
                "certainty_threshold_versions.organization_id",
                "certainty_threshold_versions.review_id",
            ],
            name="fk_cert_assessment_threshold",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_assessment_id", "organization_id", "review_id"],
            [
                "certainty_assessments.id",
                "certainty_assessments.organization_id",
                "certainty_assessments.review_id",
            ],
            name="fk_cert_assessment_supersedes",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("round_number > 0 AND revision > 0", name="ck_cert_assessment_numbers"),
        sa.CheckConstraint(
            "status IN ('IN_PROGRESS','SUBMITTED')", name="ck_cert_assessment_status"
        ),
        sa.CheckConstraint(
            "evidence_body_type IN ('RANDOMIZED','OBSERVATIONAL','MIXED','OTHER')",
            name="ck_cert_evidence_body_type",
        ),
        sa.CheckConstraint(
            "starting_certainty IN ('HIGH','MODERATE','LOW','VERY_LOW')", name="ck_cert_starting"
        ),
        sa.CheckConstraint(
            "candidate_certainty IS NULL OR candidate_certainty IN "
            "('HIGH','MODERATE','LOW','VERY_LOW')",
            name="ck_cert_candidate",
        ),
        sa.CheckConstraint(
            "final_certainty IS NULL OR final_certainty IN ('HIGH','MODERATE','LOW','VERY_LOW')",
            name="ck_cert_final",
        ),
        sa.CheckConstraint(
            "evidence_hash IS NULL OR length(evidence_hash) = 64", name="ck_cert_evidence_hash"
        ),
        sa.CheckConstraint(
            "(status = 'IN_PROGRESS' AND submitted_at IS NULL) OR "
            "(status = 'SUBMITTED' AND submitted_at IS NOT NULL "
            "AND candidate_certainty IS NOT NULL AND final_certainty IS NOT NULL "
            "AND final_rationale IS NOT NULL AND evidence_snapshot IS NOT NULL "
            "AND evidence_hash IS NOT NULL)",
            name="ck_cert_submission",
        ),
    )
    op.create_table(
        "certainty_domain_judgments",
        _id(),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        *_scope(),
        sa.Column("domain_key", sa.String(120), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("magnitude", sa.Integer(), nullable=False),
        sa.Column("judgment", sa.String(120), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence_location_id", sa.Uuid()),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("assessment_id", "domain_key", name="uq_cert_domain_assessment"),
        sa.ForeignKeyConstraint(
            ["assessment_id", "organization_id", "review_id"],
            [
                "certainty_assessments.id",
                "certainty_assessments.organization_id",
                "certainty_assessments.review_id",
            ],
            name="fk_cert_domain_assessment",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_location_id", "organization_id", "review_id"],
            [
                "document_evidence_locations.id",
                "document_evidence_locations.organization_id",
                "document_evidence_locations.review_id",
            ],
            name="fk_cert_domain_evidence",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("direction IN ('DOWNGRADE','UPGRADE')", name="ck_cert_domain_direction"),
        sa.CheckConstraint("magnitude >= 0 AND magnitude <= 2", name="ck_cert_domain_magnitude"),
    )
    op.create_table(
        "certainty_comparisons",
        _id(),
        *_scope(),
        sa.Column("outcome_version_id", sa.Uuid(), nullable=False),
        sa.Column("framework_version_id", sa.Uuid(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("assessment_a_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_b_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("differences", sa.JSON(), nullable=False),
        sa.Column("compared_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "compared_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("adjudicated_snapshot", sa.JSON()),
        sa.Column("adjudicated_by_user_id", sa.Uuid()),
        sa.Column("adjudication_reason", sa.Text()),
        sa.Column("adjudication_evidence_location_id", sa.Uuid()),
        sa.Column("adjudicated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("assessment_a_id", "assessment_b_id", name="uq_cert_comparison_pair"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_cert_comparison_tenant"),
        _review_fk("fk_cert_comparison_review"),
        _actor_fk("compared_by_user_id", "fk_cert_comparison_actor"),
        _actor_fk("adjudicated_by_user_id", "fk_cert_adjudication_actor"),
        sa.ForeignKeyConstraint(
            ["outcome_version_id", "organization_id", "review_id"],
            [
                "outcome_definition_versions.id",
                "outcome_definition_versions.organization_id",
                "outcome_definition_versions.review_id",
            ],
            name="fk_cert_comparison_outcome",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["framework_version_id", "organization_id", "review_id"],
            [
                "certainty_framework_versions.id",
                "certainty_framework_versions.organization_id",
                "certainty_framework_versions.review_id",
            ],
            name="fk_cert_comparison_framework",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["adjudication_evidence_location_id", "organization_id", "review_id"],
            [
                "document_evidence_locations.id",
                "document_evidence_locations.organization_id",
                "document_evidence_locations.review_id",
            ],
            name="fk_cert_adjudication_evidence",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_a_id", "organization_id", "review_id"],
            [
                "certainty_assessments.id",
                "certainty_assessments.organization_id",
                "certainty_assessments.review_id",
            ],
            name="fk_cert_comparison_a",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_b_id", "organization_id", "review_id"],
            [
                "certainty_assessments.id",
                "certainty_assessments.organization_id",
                "certainty_assessments.review_id",
            ],
            name="fk_cert_comparison_b",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('AGREEMENT','CONFLICT','ADJUDICATED')", name="ck_cert_comparison_status"
        ),
        sa.CheckConstraint(
            "assessment_a_id <> assessment_b_id", name="ck_cert_comparison_distinct"
        ),
        sa.CheckConstraint(
            "(status <> 'ADJUDICATED' AND adjudicated_by_user_id IS NULL "
            "AND adjudication_reason IS NULL "
            "AND adjudicated_at IS NULL) OR "
            "(status = 'ADJUDICATED' AND adjudicated_by_user_id IS NOT NULL "
            "AND adjudication_reason IS NOT NULL "
            "AND adjudicated_at IS NOT NULL)",
            name="ck_cert_adjudication_complete",
        ),
    )
    op.create_table(
        "summary_of_findings_snapshots",
        _id(),
        *_scope(),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("row", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_sof_snapshot_tenant"),
        sa.ForeignKeyConstraint(
            ["assessment_id", "organization_id", "review_id"],
            [
                "certainty_assessments.id",
                "certainty_assessments.organization_id",
                "certainty_assessments.review_id",
            ],
            name="fk_sof_assessment",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_sof_actor"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_sof_hash"),
    )
    for table, columns in (
        ("certainty_frameworks", ["organization_id", "review_id"]),
        ("certainty_assessments", ["organization_id", "review_id", "outcome_version_id"]),
        ("certainty_comparisons", ["organization_id", "review_id"]),
        ("summary_of_findings_snapshots", ["organization_id", "review_id"]),
    ):
        op.create_index(f"ix_{table}_review", table, columns)


def downgrade() -> None:
    for table in (
        "summary_of_findings_snapshots",
        "certainty_comparisons",
        "certainty_domain_judgments",
        "certainty_assessments",
        "certainty_threshold_versions",
        "certainty_framework_versions",
        "certainty_frameworks",
    ):
        op.drop_table(table)
