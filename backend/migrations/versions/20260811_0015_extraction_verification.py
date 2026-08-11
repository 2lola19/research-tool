"""Add deterministic extraction comparison and human adjudication records.

Revision ID: 20260811_0015
Revises: 20260811_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0015"
down_revision: str | None = "20260811_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extraction_conflicts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version_id", sa.Uuid(), nullable=False),
        sa.Column("field_key", sa.String(200), nullable=False),
        sa.Column("run_a_id", sa.Uuid(), nullable=False),
        sa.Column("run_b_id", sa.Uuid(), nullable=False),
        sa.Column("value_a", sa.JSON(), nullable=True),
        sa.Column("value_b", sa.JSON(), nullable=True),
        sa.Column("evidence_a", sa.JSON(), nullable=True),
        sa.Column("evidence_b", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("resolution", sa.String(50), nullable=True),
        sa.Column("adjudicated_value", sa.JSON(), nullable=True),
        sa.Column("adjudicated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_extraction_conflicts_id_tenant"),
        sa.ForeignKeyConstraint(["study_id", "organization_id", "review_id"], ["studies.id", "studies.organization_id", "studies.review_id"], name="fk_extraction_conflicts_study_tenant", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_a_id", "organization_id", "review_id"], ["extraction_runs.id", "extraction_runs.organization_id", "extraction_runs.review_id"], name="fk_extraction_conflicts_run_a_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_b_id", "organization_id", "review_id"], ["extraction_runs.id", "extraction_runs.organization_id", "extraction_runs.review_id"], name="fk_extraction_conflicts_run_b_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id", "adjudicated_by_user_id"], ["memberships.organization_id", "memberships.user_id"], name="fk_extraction_conflicts_adjudicator_membership", ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('OPEN','RESOLVED')", name="ck_extraction_conflicts_status"),
    )
    op.create_table(
        "extraction_verifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version_id", sa.Uuid(), nullable=False),
        sa.Column("field_key", sa.String(200), nullable=False),
        sa.Column("run_a_id", sa.Uuid(), nullable=False),
        sa.Column("run_b_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("conflict_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_extraction_verifications_id_tenant"),
        sa.UniqueConstraint("run_a_id", "run_b_id", "field_key", name="uq_extraction_verifications_pair_field"),
        sa.ForeignKeyConstraint(["study_id", "organization_id", "review_id"], ["studies.id", "studies.organization_id", "studies.review_id"], name="fk_extraction_verifications_study_tenant", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_a_id", "organization_id", "review_id"], ["extraction_runs.id", "extraction_runs.organization_id", "extraction_runs.review_id"], name="fk_extraction_verifications_run_a_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_b_id", "organization_id", "review_id"], ["extraction_runs.id", "extraction_runs.organization_id", "extraction_runs.review_id"], name="fk_extraction_verifications_run_b_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["conflict_id", "organization_id", "review_id"], ["extraction_conflicts.id", "extraction_conflicts.organization_id", "extraction_conflicts.review_id"], name="fk_extraction_verifications_conflict_tenant", ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('MATCHED','NEEDS_ADJUDICATION','ADJUDICATED')", name="ck_extraction_verifications_status"),
    )


def downgrade() -> None:
    op.drop_table("extraction_verifications")
    op.drop_table("extraction_conflicts")
