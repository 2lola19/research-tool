"""Add non-destructive deduplication runs, candidates, and decisions.

Revision ID: 20260810_0009
Revises: 20260810_0008
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0009"
down_revision: str | None = "20260810_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "deduplication_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=50), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("article_count", sa.Integer(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "article_count >= 0", name="ck_deduplication_runs_article_count"
        ),
        sa.CheckConstraint(
            "candidate_count >= 0", name="ck_deduplication_runs_candidate_count"
        ),
        sa.CheckConstraint(
            "length(input_hash) = 64", name="ck_deduplication_runs_hash_length"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_deduplication_runs_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_deduplication_runs_review_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_deduplication_runs_id_tenant"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "review_id",
            "algorithm_version",
            "input_hash",
            name="uq_deduplication_runs_input",
        ),
    )
    op.create_table(
        "duplicate_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deduplication_run_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("left_article_id", sa.Uuid(), nullable=False),
        sa.Column("right_article_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=30), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "left_article_id <> right_article_id", name="ck_duplicate_candidates_distinct"
        ),
        sa.CheckConstraint(
            "reason IN ('DOI_EXACT', 'PMID_EXACT', 'TITLE_YEAR_EXACT', 'TITLE_FUZZY')",
            name="ck_duplicate_candidates_reason",
        ),
        sa.CheckConstraint(
            "score >= 0 AND score <= 1", name="ck_duplicate_candidates_score"
        ),
        sa.ForeignKeyConstraint(
            ["deduplication_run_id", "organization_id", "review_id"],
            [
                "deduplication_runs.id",
                "deduplication_runs.organization_id",
                "deduplication_runs.review_id",
            ],
            name="fk_duplicate_candidates_run_tenant_review",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["left_article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_duplicate_candidates_left_article_tenant_review",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["right_article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_duplicate_candidates_right_article_tenant_review",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_duplicate_candidates_id_tenant"
        ),
        sa.UniqueConstraint(
            "deduplication_run_id",
            "left_article_id",
            "right_article_id",
            name="uq_duplicate_candidates_run_pair",
        ),
    )
    op.create_table(
        "deduplication_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("retained_article_id", sa.Uuid(), nullable=True),
        sa.Column("decided_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "decision IN ('CONFIRMED_DUPLICATE', 'REJECTED')",
            name="ck_deduplication_decisions_decision",
        ),
        sa.CheckConstraint(
            "(decision = 'CONFIRMED_DUPLICATE' AND retained_article_id IS NOT NULL) OR "
            "(decision = 'REJECTED' AND retained_article_id IS NULL)",
            name="ck_deduplication_decisions_retained_article",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id", "organization_id", "review_id"],
            [
                "duplicate_candidates.id",
                "duplicate_candidates.organization_id",
                "duplicate_candidates.review_id",
            ],
            name="fk_deduplication_decisions_candidate_tenant_review",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "decided_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_deduplication_decisions_actor_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["retained_article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_deduplication_decisions_retained_article",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", name="uq_deduplication_decisions_candidate"),
    )


def downgrade() -> None:
    op.drop_table("deduplication_decisions")
    op.drop_table("duplicate_candidates")
    op.drop_table("deduplication_runs")
