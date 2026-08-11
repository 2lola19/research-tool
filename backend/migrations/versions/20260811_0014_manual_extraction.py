"""Add provenance-first manual extraction runs and typed values.

Revision ID: 20260811_0014
Revises: 20260811_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0014"
down_revision: str | None = "20260811_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("schema_version_id", sa.Uuid(), nullable=False),
        sa.Column("extractor_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_extraction_runs_id_tenant"),
        sa.ForeignKeyConstraint(["review_id", "organization_id"], ["reviews.id", "reviews.organization_id"], name="fk_extraction_runs_review_tenant", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["study_id", "organization_id", "review_id"], ["studies.id", "studies.organization_id", "studies.review_id"], name="fk_extraction_runs_study_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["schema_version_id", "organization_id", "review_id"], ["extraction_schema_versions.id", "extraction_schema_versions.organization_id", "extraction_schema_versions.review_id"], name="fk_extraction_runs_schema_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id", "extractor_user_id"], ["memberships.organization_id", "memberships.user_id"], name="fk_extraction_runs_extractor_membership", ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('NOT_STARTED','IN_PROGRESS','COMPLETED','NEEDS_REVIEW','VERIFIED','CONFLICT')", name="ck_extraction_runs_status"),
    )
    op.create_table(
        "extraction_values",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("field_key", sa.String(200), nullable=False),
        sa.Column("missingness", sa.String(20), nullable=False),
        sa.Column("value_integer", sa.Integer(), nullable=True),
        sa.Column("value_decimal", sa.Numeric(30, 12), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_boolean", sa.Boolean(), nullable=True),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("unit", sa.String(100), nullable=True),
        sa.Column("source_article_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_location_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_extraction_values_id_tenant"),
        sa.UniqueConstraint("run_id", "field_key", name="uq_extraction_values_run_field"),
        sa.ForeignKeyConstraint(["run_id", "organization_id", "review_id"], ["extraction_runs.id", "extraction_runs.organization_id", "extraction_runs.review_id"], name="fk_extraction_values_run_tenant", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_article_id", "organization_id", "review_id"], ["articles.id", "articles.organization_id", "articles.review_id"], name="fk_extraction_values_article_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evidence_location_id", "organization_id", "review_id"], ["document_evidence_locations.id", "document_evidence_locations.organization_id", "document_evidence_locations.review_id"], name="fk_extraction_values_evidence_tenant", ondelete="RESTRICT"),
        sa.CheckConstraint("missingness IN ('VALUE_REPORTED','NOT_REPORTED','UNCLEAR','NOT_APPLICABLE','NEEDS_REVIEW')", name="ck_extraction_values_missingness"),
    )


def downgrade() -> None:
    op.drop_table("extraction_values")
    op.drop_table("extraction_runs")
