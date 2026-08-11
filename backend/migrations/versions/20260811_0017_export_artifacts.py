"""Add immutable reproducible export artifacts.

Revision ID: 20260811_0017
Revises: 20260811_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0017"
down_revision: str | None = "20260811_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "export_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("prisma_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("export_format", sa.String(length=10), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("media_type", sa.String(length=200), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("export_format IN ('CSV','XLSX','JSON','RIS')", name="ck_export_format"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_export_sha256_length"),
        sa.CheckConstraint("byte_size >= 0", name="ck_export_byte_size"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_export_artifacts_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_export_artifacts_review_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["prisma_snapshot_id", "organization_id", "review_id"],
            [
                "prisma_snapshots.id",
                "prisma_snapshots.organization_id",
                "prisma_snapshots.review_id",
            ],
            name="fk_export_artifacts_prisma_snapshot",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_export_artifacts_creator_membership",
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    op.drop_table("export_artifacts")
