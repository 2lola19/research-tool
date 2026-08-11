"""Add immutable, versioned extraction schema definitions.

Revision ID: 20260811_0013
Revises: 20260811_0012
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0013"
down_revision: str | None = "20260811_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extraction_schemas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_extraction_schemas_id_tenant"),
        sa.UniqueConstraint("organization_id", "review_id", "name", name="uq_extraction_schemas_review_name"),
        sa.ForeignKeyConstraint(["review_id", "organization_id"], ["reviews.id", "reviews.organization_id"], name="fk_extraction_schemas_review_tenant", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id", "created_by_user_id"], ["memberships.organization_id", "memberships.user_id"], name="fk_extraction_schemas_creator_membership", ondelete="RESTRICT"),
    )
    op.create_table(
        "extraction_schema_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schema_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_extraction_schema_versions_id_tenant"),
        sa.UniqueConstraint("schema_id", "version", name="uq_extraction_schema_versions_number"),
        sa.ForeignKeyConstraint(["schema_id", "organization_id", "review_id"], ["extraction_schemas.id", "extraction_schemas.organization_id", "extraction_schemas.review_id"], name="fk_extraction_schema_versions_schema_tenant", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id", "created_by_user_id"], ["memberships.organization_id", "memberships.user_id"], name="fk_extraction_schema_versions_creator_membership", ondelete="RESTRICT"),
        sa.CheckConstraint("version > 0", name="ck_extraction_schema_versions_positive"),
        sa.CheckConstraint("length(content_hash) = 64", name="ck_extraction_schema_versions_hash_length"),
    )


def downgrade() -> None:
    op.drop_table("extraction_schema_versions")
    op.drop_table("extraction_schemas")
