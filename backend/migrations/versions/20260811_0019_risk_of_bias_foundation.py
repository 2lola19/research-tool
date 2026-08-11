"""Add versioned Risk of Bias instruments and independent assessments.

Revision ID: 20260811_0019
Revises: 20260811_0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0019"
down_revision: str | None = "20260811_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_review_fk(name: str) -> sa.ForeignKeyConstraint:
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


def _evidence_fk(column: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column, "organization_id", "review_id"],
        [
            "document_evidence_locations.id",
            "document_evidence_locations.organization_id",
            "document_evidence_locations.review_id",
        ],
        name=name,
        ondelete="RESTRICT",
    )


def upgrade() -> None:
    with op.batch_alter_table("studies") as batch_op:
        batch_op.add_column(sa.Column("study_design", sa.String(length=100), nullable=True))

    op.create_table(
        "rob_instruments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "review_id", "key", name="uq_rob_instrument_key"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_rob_instrument_id_tenant"
        ),
        _tenant_review_fk("fk_rob_instrument_review_tenant"),
        _membership_fk("created_by_user_id", "fk_rob_instrument_creator_membership"),
    )
    op.create_table(
        "rob_instrument_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("version > 0", name="ck_rob_version_positive"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_rob_version_hash"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instrument_id", "version", name="uq_rob_instrument_version_number"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_rob_version_id_tenant"),
        sa.ForeignKeyConstraint(
            ["instrument_id", "organization_id", "review_id"],
            ["rob_instruments.id", "rob_instruments.organization_id", "rob_instruments.review_id"],
            name="fk_rob_version_instrument_tenant",
            ondelete="CASCADE",
        ),
        _membership_fk("created_by_user_id", "fk_rob_version_creator_membership"),
    )
    op.create_table(
        "rob_instrument_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instrument_version_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("decided_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("decision IN ('APPROVED','REJECTED')", name="ck_rob_version_decision"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("instrument_version_id", name="uq_rob_version_decision"),
        sa.ForeignKeyConstraint(
            ["instrument_version_id", "organization_id", "review_id"],
            [
                "rob_instrument_versions.id",
                "rob_instrument_versions.organization_id",
                "rob_instrument_versions.review_id",
            ],
            name="fk_rob_decision_version_tenant",
            ondelete="CASCADE",
        ),
        _membership_fk("decided_by_user_id", "fk_rob_decision_actor_membership"),
    )
    op.create_table(
        "rob_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_version_id", sa.Uuid(), nullable=False),
        sa.Column("assessor_user_id", sa.Uuid(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("supersedes_assessment_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("overall_suggested_judgment", sa.String(length=120), nullable=True),
        sa.Column("overall_final_judgment", sa.String(length=120), nullable=True),
        sa.Column("overall_rationale", sa.Text(), nullable=True),
        sa.Column("overall_override_reason", sa.Text(), nullable=True),
        sa.Column("overall_evidence_location_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("round_number > 0 AND revision > 0", name="ck_rob_assessment_numbers"),
        sa.CheckConstraint(
            "status IN ('IN_PROGRESS','SUBMITTED')", name="ck_rob_assessment_status"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_rob_assessment_id_tenant"
        ),
        sa.UniqueConstraint(
            "study_id",
            "instrument_version_id",
            "round_number",
            "assessor_user_id",
            "revision",
            name="uq_rob_assessment_assessor_revision",
        ),
        sa.UniqueConstraint("supersedes_assessment_id", name="uq_rob_assessment_single_correction"),
        sa.ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_rob_assessment_study_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_version_id", "organization_id", "review_id"],
            [
                "rob_instrument_versions.id",
                "rob_instrument_versions.organization_id",
                "rob_instrument_versions.review_id",
            ],
            name="fk_rob_assessment_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_assessment_id", "organization_id", "review_id"],
            ["rob_assessments.id", "rob_assessments.organization_id", "rob_assessments.review_id"],
            name="fk_rob_assessment_correction_tenant",
            ondelete="RESTRICT",
        ),
        _evidence_fk("overall_evidence_location_id", "fk_rob_assessment_overall_evidence_tenant"),
        _membership_fk("assessor_user_id", "fk_rob_assessment_assessor_membership"),
    )
    op.create_index(
        "ix_rob_assessments_review_study",
        "rob_assessments",
        ["organization_id", "review_id", "study_id", "status", "id"],
    )
    op.create_table(
        "rob_answers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("question_key", sa.String(length=120), nullable=False),
        sa.Column("answer", sa.String(length=120), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("evidence_location_id", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id", "question_key", name="uq_rob_answer_question"),
        sa.ForeignKeyConstraint(
            ["assessment_id", "organization_id", "review_id"],
            ["rob_assessments.id", "rob_assessments.organization_id", "rob_assessments.review_id"],
            name="fk_rob_answer_assessment_tenant",
            ondelete="CASCADE",
        ),
        _evidence_fk("evidence_location_id", "fk_rob_answer_evidence_tenant"),
    )
    op.create_table(
        "rob_domain_judgments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("domain_key", sa.String(length=120), nullable=False),
        sa.Column("suggested_judgment", sa.String(length=120), nullable=True),
        sa.Column("final_judgment", sa.String(length=120), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("evidence_location_id", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id", "domain_key", name="uq_rob_domain_judgment"),
        sa.ForeignKeyConstraint(
            ["assessment_id", "organization_id", "review_id"],
            ["rob_assessments.id", "rob_assessments.organization_id", "rob_assessments.review_id"],
            name="fk_rob_domain_assessment_tenant",
            ondelete="CASCADE",
        ),
        _evidence_fk("evidence_location_id", "fk_rob_domain_evidence_tenant"),
    )
    op.create_table(
        "rob_comparisons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("instrument_version_id", sa.Uuid(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("assessment_a_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_b_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("differences", sa.JSON(), nullable=False),
        sa.Column("compared_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("compared_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('AGREEMENT','CONFLICT')", name="ck_rob_comparison_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_rob_comparison_id_tenant"
        ),
        sa.UniqueConstraint("assessment_a_id", "assessment_b_id", name="uq_rob_comparison_pair"),
        sa.ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_rob_comparison_study_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_version_id", "organization_id", "review_id"],
            [
                "rob_instrument_versions.id",
                "rob_instrument_versions.organization_id",
                "rob_instrument_versions.review_id",
            ],
            name="fk_rob_comparison_version_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_a_id", "organization_id", "review_id"],
            ["rob_assessments.id", "rob_assessments.organization_id", "rob_assessments.review_id"],
            name="fk_rob_comparison_a_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assessment_b_id", "organization_id", "review_id"],
            ["rob_assessments.id", "rob_assessments.organization_id", "rob_assessments.review_id"],
            name="fk_rob_comparison_b_tenant",
            ondelete="RESTRICT",
        ),
        _membership_fk("compared_by_user_id", "fk_rob_comparison_actor_membership"),
    )
    op.create_table(
        "rob_adjudications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("comparison_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("final_snapshot", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence_location_id", sa.Uuid(), nullable=True),
        sa.Column("adjudicated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("adjudicated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("comparison_id", name="uq_rob_adjudication_comparison"),
        sa.ForeignKeyConstraint(
            ["comparison_id", "organization_id", "review_id"],
            ["rob_comparisons.id", "rob_comparisons.organization_id", "rob_comparisons.review_id"],
            name="fk_rob_adjudication_comparison_tenant",
            ondelete="RESTRICT",
        ),
        _evidence_fk("evidence_location_id", "fk_rob_adjudication_evidence_tenant"),
        _membership_fk("adjudicated_by_user_id", "fk_rob_adjudication_actor_membership"),
    )


def downgrade() -> None:
    op.drop_table("rob_adjudications")
    op.drop_table("rob_comparisons")
    op.drop_table("rob_domain_judgments")
    op.drop_table("rob_answers")
    op.drop_index("ix_rob_assessments_review_study", table_name="rob_assessments")
    op.drop_table("rob_assessments")
    op.drop_table("rob_instrument_decisions")
    op.drop_table("rob_instrument_versions")
    op.drop_table("rob_instruments")
    with op.batch_alter_table("studies") as batch_op:
        batch_op.drop_column("study_design")
