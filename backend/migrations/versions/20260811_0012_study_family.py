"""Add non-destructive study families and article links.

Revision ID: 20260811_0012
Revises: 20260810_0011
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0012"
down_revision: str | None = "20260810_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "studies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("study_key", sa.String(100), nullable=False),
        sa.Column("label", sa.String(500), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "review_id", "study_key", name="uq_studies_review_key"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_studies_id_tenant"),
        sa.ForeignKeyConstraint(["review_id", "organization_id"], ["reviews.id", "reviews.organization_id"], name="fk_studies_review_tenant", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id", "created_by_user_id"], ["memberships.organization_id", "memberships.user_id"], name="fk_studies_creator_membership", ondelete="RESTRICT"),
        sa.CheckConstraint("length(trim(study_key)) > 0", name="ck_studies_key_present"),
    )
    op.create_table(
        "study_article_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source_evidence", sa.JSON(), nullable=True),
        sa.Column("linked_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unlinked_by_user_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_study_links_id_tenant"),
        sa.ForeignKeyConstraint(["study_id", "organization_id", "review_id"], ["studies.id", "studies.organization_id", "studies.review_id"], name="fk_study_links_study_tenant", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["article_id", "organization_id", "review_id"], ["articles.id", "articles.organization_id", "articles.review_id"], name="fk_study_links_article_tenant", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id", "linked_by_user_id"], ["memberships.organization_id", "memberships.user_id"], name="fk_study_links_creator_membership", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id", "unlinked_by_user_id"], ["memberships.organization_id", "memberships.user_id"], name="fk_study_links_remover_membership", ondelete="RESTRICT"),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_study_links_confidence"),
        sa.CheckConstraint("role IN ('PRIMARY','PROTOCOL','FOLLOW_UP','SUBGROUP','SECONDARY_ANALYSIS','CONFERENCE_ABSTRACT','CORRECTION','SUPPLEMENT','OTHER')", name="ck_study_links_role"),
        sa.CheckConstraint("method IN ('MANUAL','EXACT_REGISTRY_MATCH','METADATA_MATCH','AI_SUGGESTED','IMPORTED')", name="ck_study_links_method"),
    )


def downgrade() -> None:
    op.drop_table("study_article_links")
    op.drop_table("studies")
