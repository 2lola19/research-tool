"""Add canonical search strategy versions and deterministic translations.

Revision ID: 20260810_0007
Revises: 20260810_0006
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0007"
down_revision: str | None = "20260810_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_strategy_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("protocol_version_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "length(content_hash) = 64", name="ck_search_strategy_versions_hash_length"
        ),
        sa.CheckConstraint(
            "version > 0", name="ck_search_strategy_versions_positive_version"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_search_strategy_versions_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["protocol_version_id", "organization_id", "review_id"],
            [
                "protocol_versions.id",
                "protocol_versions.organization_id",
                "protocol_versions.review_id",
            ],
            name="fk_search_strategy_versions_protocol_tenant_review",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_search_strategy_versions_review_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_search_strategy_versions_id_tenant"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "review_id",
            "version",
            name="uq_search_strategy_versions_review_version",
        ),
    )
    op.create_table(
        "search_translations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("search_strategy_version_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("translator_version", sa.String(length=50), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_search_translations_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["search_strategy_version_id", "organization_id", "review_id"],
            [
                "search_strategy_versions.id",
                "search_strategy_versions.organization_id",
                "search_strategy_versions.review_id",
            ],
            name="fk_search_translations_strategy_tenant_review",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "search_strategy_version_id",
            "provider",
            "translator_version",
            name="uq_search_translations_strategy_provider_version",
        ),
    )


def downgrade() -> None:
    op.drop_table("search_translations")
    op.drop_table("search_strategy_versions")
