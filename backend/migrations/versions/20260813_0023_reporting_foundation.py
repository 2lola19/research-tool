"""Add immutable structured reporting and reproducibility artifacts.

Revision ID: 20260813_0023
Revises: 20260812_0022
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0023"
down_revision: str | None = "20260812_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "report_specifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("logical_key", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_report_specifications_id_tenant"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "review_id",
            "logical_key",
            "version",
            name="uq_report_specifications_version",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_report_specifications_review_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_report_specifications_creator",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_report_specifications_review",
        "report_specifications",
        ["organization_id", "review_id", "report_type"],
    )
    op.create_table(
        "report_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("specification_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source_references", sa.JSON(), nullable=False),
        sa.Column("source_hashes", sa.JSON(), nullable=False),
        sa.Column("structured_content", sa.JSON(), nullable=True),
        sa.Column("scientific_content_hash", sa.String(64), nullable=True),
        sa.Column("renderer_version", sa.String(120), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(2000), nullable=True),
        sa.CheckConstraint(
            "status IN ('QUEUED','RUNNING','COMPLETED','FAILED')", name="ck_report_snapshot_status"
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_report_snapshots_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_report_snapshots_review_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["specification_id", "organization_id", "review_id"],
            [
                "report_specifications.id",
                "report_specifications.organization_id",
                "report_specifications.review_id",
            ],
            name="fk_report_snapshots_specification",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_report_snapshots_creator",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_report_snapshots_review",
        "report_snapshots",
        ["organization_id", "review_id", "created_at"],
    )
    op.create_table(
        "report_artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("report_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("report_format", sa.String(10), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("media_type", sa.String(200), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "report_format IN ('JSON','XLSX','HTML','ZIP')", name="ck_report_artifact_format"
        ),
        sa.CheckConstraint("byte_size >= 0", name="ck_report_artifact_size"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_report_artifacts_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["report_snapshot_id", "organization_id", "review_id"],
            [
                "report_snapshots.id",
                "report_snapshots.organization_id",
                "report_snapshots.review_id",
            ],
            name="fk_report_artifacts_snapshot",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_report_artifacts_snapshot",
        "report_artifacts",
        ["organization_id", "review_id", "report_snapshot_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_report_artifacts_snapshot", table_name="report_artifacts")
    op.drop_table("report_artifacts")
    op.drop_index("ix_report_snapshots_review", table_name="report_snapshots")
    op.drop_table("report_snapshots")
    op.drop_index("ix_report_specifications_review", table_name="report_specifications")
    op.drop_table("report_specifications")
