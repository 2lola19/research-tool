"""Add deterministic search execution and identification provenance.

Revision ID: 20260811_0018
Revises: 20260811_0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0018"
down_revision: str | None = "20260811_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("citation_source_records") as batch_op:
        batch_op.create_unique_constraint(
            "uq_citation_source_records_id_tenant",
            ["id", "organization_id", "review_id"],
        )
    with op.batch_alter_table("search_translations") as batch_op:
        batch_op.create_unique_constraint(
            "uq_search_translations_id_strategy_tenant",
            ["id", "search_strategy_version_id", "organization_id", "review_id"],
        )

    op.create_table(
        "identification_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("source_key", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=300), nullable=False),
        sa.Column("classification", sa.String(length=40), nullable=False),
        sa.Column("provider_name", sa.String(length=200), nullable=False),
        sa.Column("platform_name", sa.String(length=200), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "classification IN ("
            "'BIBLIOGRAPHIC_DATABASE','TRIAL_REGISTER','OTHER_REGISTER',"
            "'WEBSITE','ORGANIZATION','CITATION_SEARCHING','REFERENCE_LIST',"
            "'AUTHOR_CONTACT','MANUAL_IMPORT','OTHER_SOURCE')",
            name="ck_identification_sources_classification",
        ),
        sa.CheckConstraint("length(trim(source_key)) > 0", name="ck_identification_source_key"),
        sa.CheckConstraint("length(trim(display_name)) > 0", name="ck_identification_source_name"),
        sa.CheckConstraint(
            "length(trim(provider_name)) > 0", name="ck_identification_source_provider"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "review_id", "source_key", name="uq_identification_sources_key"
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_identification_sources_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_identification_sources_review_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_identification_sources_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "search_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("search_strategy_version_id", sa.Uuid(), nullable=True),
        sa.Column("search_translation_id", sa.Uuid(), nullable=True),
        sa.Column("supersedes_execution_id", sa.Uuid(), nullable=True),
        sa.Column("method", sa.String(length=30), nullable=False),
        sa.Column("exact_query", sa.Text(), nullable=True),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("software_version", sa.String(length=120), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "method IN ('API','FILE_IMPORT','MANUAL_RECORD','FIXTURE','MOCK','CONNECTOR')",
            name="ck_search_execution_method",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_search_executions_id_tenant"
        ),
        sa.UniqueConstraint(
            "supersedes_execution_id", name="uq_search_executions_single_correction"
        ),
        sa.ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_search_executions_review_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id", "organization_id", "review_id"],
            [
                "identification_sources.id",
                "identification_sources.organization_id",
                "identification_sources.review_id",
            ],
            name="fk_search_executions_source_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["search_strategy_version_id", "organization_id", "review_id"],
            [
                "search_strategy_versions.id",
                "search_strategy_versions.organization_id",
                "search_strategy_versions.review_id",
            ],
            name="fk_search_executions_strategy_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "search_translation_id",
                "search_strategy_version_id",
                "organization_id",
                "review_id",
            ],
            [
                "search_translations.id",
                "search_translations.search_strategy_version_id",
                "search_translations.organization_id",
                "search_translations.review_id",
            ],
            name="fk_search_executions_translation_strategy",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_execution_id", "organization_id", "review_id"],
            [
                "search_executions.id",
                "search_executions.organization_id",
                "search_executions.review_id",
            ],
            name="fk_search_executions_superseded_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_search_executions_creator_membership",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_search_executions_review_date",
        "search_executions",
        ["organization_id", "review_id", "executed_at", "id"],
    )

    op.create_table(
        "search_execution_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("search_execution_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider_result_count", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("sequence > 0", name="ck_search_execution_event_sequence"),
        sa.CheckConstraint(
            "status IN ('PLANNED','RUNNING','COMPLETED','PARTIAL','FAILED','CANCELLED')",
            name="ck_search_execution_status",
        ),
        sa.CheckConstraint(
            "provider_result_count IS NULL OR provider_result_count >= 0",
            name="ck_search_execution_result_count",
        ),
        sa.CheckConstraint(
            "status != 'COMPLETED' OR provider_result_count IS NOT NULL",
            name="ck_completed_search_execution_result_count",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "search_execution_id", "sequence", name="uq_search_execution_events_sequence"
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_search_execution_events_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["search_execution_id", "organization_id", "review_id"],
            [
                "search_executions.id",
                "search_executions.organization_id",
                "search_executions.review_id",
            ],
            name="fk_search_execution_events_execution_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "recorded_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_search_execution_events_actor_membership",
            ondelete="RESTRICT",
        ),
    )

    op.create_table(
        "search_execution_citation_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("search_execution_id", sa.Uuid(), nullable=False),
        sa.Column("citation_source_record_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("linked_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "search_execution_id",
            "citation_source_record_id",
            name="uq_search_execution_citation_link",
        ),
        sa.ForeignKeyConstraint(
            ["search_execution_id", "organization_id", "review_id"],
            [
                "search_executions.id",
                "search_executions.organization_id",
                "search_executions.review_id",
            ],
            name="fk_search_execution_links_execution_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["citation_source_record_id", "organization_id", "review_id"],
            [
                "citation_source_records.id",
                "citation_source_records.organization_id",
                "citation_source_records.review_id",
            ],
            name="fk_search_execution_links_citation_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "linked_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_search_execution_links_actor_membership",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_search_execution_links_citation",
        "search_execution_citation_links",
        ["organization_id", "review_id", "citation_source_record_id"],
    )

    op.create_table(
        "search_execution_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("search_execution_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=1000), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("media_type", sa.String(length=200), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("byte_size > 0", name="ck_search_execution_artifact_size"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_search_execution_artifact_hash"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
        sa.UniqueConstraint(
            "search_execution_id", "sha256", name="uq_search_execution_artifact_checksum"
        ),
        sa.UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_search_execution_artifact_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["search_execution_id", "organization_id", "review_id"],
            [
                "search_executions.id",
                "search_executions.organization_id",
                "search_executions.review_id",
            ],
            name="fk_search_execution_artifacts_execution_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_search_execution_artifacts_creator_membership",
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    op.drop_table("search_execution_artifacts")
    op.drop_index(
        "ix_search_execution_links_citation", table_name="search_execution_citation_links"
    )
    op.drop_table("search_execution_citation_links")
    op.drop_table("search_execution_events")
    op.drop_index("ix_search_executions_review_date", table_name="search_executions")
    op.drop_table("search_executions")
    op.drop_table("identification_sources")

    with op.batch_alter_table("search_translations") as batch_op:
        batch_op.drop_constraint("uq_search_translations_id_strategy_tenant", type_="unique")
    with op.batch_alter_table("citation_source_records") as batch_op:
        batch_op.drop_constraint("uq_citation_source_records_id_tenant", type_="unique")
