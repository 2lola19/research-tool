"""Persist provider-neutral scholarly search attempt provenance.

Revision ID: 20260819_0034
Revises: 20260819_0033
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_0034"
down_revision: str | None = "20260819_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_provider_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("search_execution_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=80), nullable=False),
        sa.Column("provider_version", sa.String(length=120), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("failure_class", sa.String(length=30), nullable=True),
        sa.Column("response_byte_size", sa.Integer(), server_default="0", nullable=False),
        sa.Column("response_sha256", sa.String(length=64), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("page_number > 0", name="ck_search_provider_attempt_page"),
        sa.CheckConstraint("attempt_number > 0", name="ck_search_provider_attempt_number"),
        sa.CheckConstraint("response_byte_size >= 0", name="ck_search_provider_attempt_size"),
        sa.CheckConstraint(
            "failure_class IS NULL OR failure_class IN "
            "('TRANSIENT','RATE_LIMITED','TIMEOUT','PERMANENT','INVALID_RESPONSE','BLOCKED')",
            name="ck_search_provider_attempt_failure_class",
        ),
        sa.CheckConstraint(
            "response_sha256 IS NULL OR length(response_sha256) = 64",
            name="ck_search_provider_attempt_hash",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["search_execution_id", "organization_id", "review_id"],
            [
                "search_executions.id",
                "search_executions.organization_id",
                "search_executions.review_id",
            ],
            name="fk_search_provider_attempt_execution_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_search_provider_attempt_creator_membership",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_search_provider_attempts_execution",
        "search_provider_attempts",
        [
            "organization_id",
            "review_id",
            "search_execution_id",
            "page_number",
            "attempt_number",
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_search_provider_attempts_execution", table_name="search_provider_attempts")
    op.drop_table("search_provider_attempts")
