"""Add lossless citation imports, source records, and Articles.

Revision ID: 20260810_0008
Revises: 20260810_0007
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0008"
down_revision: str | None = "20260810_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "articles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("publication_year", sa.Integer(), nullable=True),
        sa.Column("doi", sa.String(length=500), nullable=True),
        sa.Column("pmid", sa.String(length=50), nullable=True),
        sa.Column("authors", sa.JSON(), nullable=False),
        sa.Column("journal", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "publication_year IS NULL OR publication_year BETWEEN 1000 AND 3000",
            name="ck_articles_publication_year",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_articles_review_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_articles_id_tenant"),
    )
    op.create_table(
        "citation_import_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("source_format", sa.String(length=20), nullable=False),
        sa.Column("source_name", sa.String(length=500), nullable=False),
        sa.Column("source_content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("imported_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "length(content_hash) = 64", name="ck_citation_import_batches_hash_length"
        ),
        sa.CheckConstraint(
            "source_format IN ('RIS', 'BIBTEX', 'CSV')",
            name="ck_citation_import_batches_format",
        ),
        sa.CheckConstraint(
            "record_count > 0", name="ck_citation_import_batches_record_count"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "imported_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_citation_import_batches_importer_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_citation_import_batches_review_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_citation_import_batches_id_tenant"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "review_id",
            "source_format",
            "content_hash",
            name="uq_citation_import_batches_content",
        ),
    )
    op.create_table(
        "citation_source_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("import_batch_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=500), nullable=True),
        sa.Column("raw_metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_citation_source_records_article_tenant_review",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id", "organization_id", "review_id"],
            [
                "citation_import_batches.id",
                "citation_import_batches.organization_id",
                "citation_import_batches.review_id",
            ],
            name="fk_citation_source_records_batch_tenant_review",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "import_batch_id", "ordinal", name="uq_citation_source_records_batch_ordinal"
        ),
    )


def downgrade() -> None:
    op.drop_table("citation_source_records")
    op.drop_table("citation_import_batches")
    op.drop_table("articles")
