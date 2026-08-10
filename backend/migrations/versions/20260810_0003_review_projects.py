"""Expand reviews into administratively managed projects.

Revision ID: 20260810_0003
Revises: 20260810_0002
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0003"
down_revision: str | None = "20260810_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reviews", sa.Column("project_slug", sa.String(length=100), nullable=True))
    op.add_column("reviews", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "reviews",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("reviews", sa.Column("archived_by_user_id", sa.Uuid(), nullable=True))
    op.execute(
        sa.text(
            "UPDATE reviews SET project_slug = "
            "'review-' || substr(lower(replace(CAST(id AS VARCHAR), '-', '')), 1, 32)"
        )
    )
    with op.batch_alter_table("reviews") as batch_op:
        batch_op.alter_column("project_slug", existing_type=sa.String(length=100), nullable=False)
        batch_op.create_unique_constraint(
            "uq_reviews_org_project_slug",
            ["organization_id", "project_slug"],
        )
        batch_op.create_check_constraint(
            "ck_reviews_project_slug_present",
            "length(trim(project_slug)) > 0",
        )
        batch_op.create_check_constraint(
            "ck_reviews_archive_metadata",
            "(archived_at IS NULL AND archived_by_user_id IS NULL) OR "
            "(archived_at IS NOT NULL AND archived_by_user_id IS NOT NULL)",
        )
        batch_op.create_foreign_key(
            "fk_reviews_archiver_membership",
            "memberships",
            ["organization_id", "archived_by_user_id"],
            ["organization_id", "user_id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("reviews") as batch_op:
        batch_op.drop_constraint("fk_reviews_archiver_membership", type_="foreignkey")
        batch_op.drop_constraint("ck_reviews_archive_metadata", type_="check")
        batch_op.drop_constraint("ck_reviews_project_slug_present", type_="check")
        batch_op.drop_constraint("uq_reviews_org_project_slug", type_="unique")
        batch_op.drop_column("archived_by_user_id")
        batch_op.drop_column("archived_at")
        batch_op.drop_column("description")
        batch_op.drop_column("project_slug")
