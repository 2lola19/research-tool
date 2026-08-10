"""Add append-only provenance, audit, prompt, and AI-run ledgers.

Revision ID: 20260810_0005
Revises: 20260810_0004
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0005"
down_revision: str | None = "20260810_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_key", sa.String(length=120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("version > 0", name="ck_prompt_versions_positive_version"),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_prompt_versions_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", name="uq_prompt_versions_id_org"),
        sa.UniqueConstraint(
            "organization_id", "prompt_key", "version", name="uq_prompt_versions_key_version"
        ),
    )
    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("prompt_version_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=160), nullable=False),
        sa.Column("model_version", sa.String(length=100), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("output_snapshot", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("status IN ('SUCCEEDED', 'FAILED')", name="ck_ai_runs_status"),
        sa.ForeignKeyConstraint(
            ["prompt_version_id", "organization_id"],
            ["prompt_versions.id", "prompt_versions.organization_id"],
            name="fk_ai_runs_prompt_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_runs_review_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_runs_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_runs_id_tenant"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=True),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("before_snapshot", sa.JSON(), nullable=True),
        sa.Column("after_snapshot", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_audit_events_review_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_audit_events_actor_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "scientific_provenance",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("subject_type", sa.String(length=120), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(length=120), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("source_locator", sa.JSON(), nullable=False),
        sa.Column("method_name", sa.String(length=160), nullable=False),
        sa.Column("method_version", sa.String(length=100), nullable=False),
        sa.Column("actor_kind", sa.String(length=20), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("ai_run_id", sa.Uuid(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("verification_state", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "(actor_kind = 'HUMAN' AND actor_user_id IS NOT NULL AND ai_run_id IS NULL) "
            "OR (actor_kind = 'AI' AND actor_user_id IS NULL AND ai_run_id IS NOT NULL) "
            "OR (actor_kind = 'SYSTEM' AND actor_user_id IS NULL AND ai_run_id IS NULL)",
            name="ck_provenance_actor_reference",
        ),
        sa.CheckConstraint(
            "actor_kind IN ('HUMAN', 'AI', 'SYSTEM')", name="ck_provenance_actor_kind"
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_provenance_confidence",
        ),
        sa.CheckConstraint(
            "(source_type IS NULL AND source_id IS NULL) OR "
            "(source_type IS NOT NULL AND source_id IS NOT NULL)",
            name="ck_provenance_source_pair",
        ),
        sa.CheckConstraint(
            "verification_state IN ('UNVERIFIED', 'HUMAN_VERIFIED', 'REJECTED')",
            name="ck_provenance_verification_state",
        ),
        sa.ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            ["ai_runs.id", "ai_runs.organization_id", "ai_runs.review_id"],
            name="fk_provenance_ai_run_tenant_review",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_provenance_actor_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_provenance_review_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("scientific_provenance")
    op.drop_table("audit_events")
    op.drop_table("ai_runs")
    op.drop_table("prompt_versions")
