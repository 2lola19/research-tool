"""Add blinded screening rounds, decisions, outcomes, and progression.

Revision ID: 20260810_0010
Revises: 20260810_0009
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0010"
down_revision: str | None = "20260810_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "screening_rounds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("stage", sa.String(length=30), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("required_decisions", sa.Integer(), nullable=False),
        sa.Column("blinded", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by_user_id", sa.Uuid(), nullable=True),
        sa.CheckConstraint(
            "(state = 'OPEN' AND closed_at IS NULL AND closed_by_user_id IS NULL) OR "
            "(state = 'CLOSED' AND closed_at IS NOT NULL AND closed_by_user_id IS NOT NULL)",
            name="ck_screening_rounds_close_metadata",
        ),
        sa.CheckConstraint(
            "required_decisions BETWEEN 1 AND 10", name="ck_screening_rounds_required_decisions"
        ),
        sa.CheckConstraint("stage IN ('TITLE_ABSTRACT', 'FULL_TEXT')", name="ck_screening_rounds_stage"),
        sa.CheckConstraint("state IN ('OPEN', 'CLOSED')", name="ck_screening_rounds_state"),
        sa.ForeignKeyConstraint(
            ["organization_id", "closed_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_screening_rounds_closer_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_screening_rounds_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_screening_rounds_review_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_screening_rounds_id_tenant"),
        sa.UniqueConstraint(
            "organization_id", "review_id", "sequence", name="uq_screening_rounds_sequence"
        ),
    )
    op.create_table(
        "screening_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("round_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_screening_assignments_article_tenant_review",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "assigned_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_screening_assignments_assigner_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "reviewer_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_screening_assignments_reviewer_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["round_id", "organization_id", "review_id"],
            ["screening_rounds.id", "screening_rounds.organization_id", "screening_rounds.review_id"],
            name="fk_screening_assignments_round_tenant_review",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            "review_id",
            "round_id",
            "article_id",
            "reviewer_user_id",
            name="uq_screening_assignments_decision_boundary",
        ),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_screening_assignments_id_tenant"),
        sa.UniqueConstraint(
            "round_id", "article_id", "reviewer_user_id", name="uq_screening_assignments_target"
        ),
    )
    op.create_table(
        "screening_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("round_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("decision IN ('INCLUDE', 'EXCLUDE')", name="ck_screening_decisions_decision"),
        sa.CheckConstraint(
            "(decision = 'INCLUDE' AND exclusion_reason IS NULL) OR "
            "(decision = 'EXCLUDE' AND exclusion_reason IS NOT NULL)",
            name="ck_screening_decisions_exclusion_reason",
        ),
        sa.ForeignKeyConstraint(
            [
                "assignment_id",
                "organization_id",
                "review_id",
                "round_id",
                "article_id",
                "reviewer_user_id",
            ],
            [
                "screening_assignments.id",
                "screening_assignments.organization_id",
                "screening_assignments.review_id",
                "screening_assignments.round_id",
                "screening_assignments.article_id",
                "screening_assignments.reviewer_user_id",
            ],
            name="fk_screening_decisions_assignment_tenant_review",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", name="uq_screening_decisions_assignment"),
    )
    op.create_table(
        "screening_outcomes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("round_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('INCLUDE', 'EXCLUDE', 'CONFLICT')", name="ck_screening_outcomes_outcome"
        ),
        sa.ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_screening_outcomes_article_tenant_review",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["round_id", "organization_id", "review_id"],
            ["screening_rounds.id", "screening_rounds.organization_id", "screening_rounds.review_id"],
            name="fk_screening_outcomes_round_tenant_review",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_screening_outcomes_id_tenant"),
        sa.UniqueConstraint("round_id", "article_id", name="uq_screening_outcomes_round_article"),
    )
    op.create_table(
        "screening_adjudications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("outcome_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("decided_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "decision IN ('INCLUDE', 'EXCLUDE')", name="ck_screening_adjudications_decision"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "decided_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_screening_adjudications_actor_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["outcome_id", "organization_id", "review_id"],
            ["screening_outcomes.id", "screening_outcomes.organization_id", "screening_outcomes.review_id"],
            name="fk_screening_adjudications_outcome_tenant_review",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outcome_id", name="uq_screening_adjudications_outcome"),
    )
    op.create_table(
        "screening_progressions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("source_round_id", sa.Uuid(), nullable=False),
        sa.Column("target_round_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_screening_progressions_article",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_screening_progressions_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_round_id", "organization_id", "review_id"],
            ["screening_rounds.id", "screening_rounds.organization_id", "screening_rounds.review_id"],
            name="fk_screening_progressions_source_round",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_round_id", "organization_id", "review_id"],
            ["screening_rounds.id", "screening_rounds.organization_id", "screening_rounds.review_id"],
            name="fk_screening_progressions_target_round",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_round_id", "target_round_id", "article_id", name="uq_screening_progressions_path"
        ),
    )


def downgrade() -> None:
    op.drop_table("screening_progressions")
    op.drop_table("screening_adjudications")
    op.drop_table("screening_outcomes")
    op.drop_table("screening_decisions")
    op.drop_table("screening_assignments")
    op.drop_table("screening_rounds")
