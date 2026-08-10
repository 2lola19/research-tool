"""Add document storage, canonical processing, and full-text screening foundation.

Revision ID: 20260810_0011
Revises: 20260810_0010
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0011"
down_revision: str | None = "20260810_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("retrieval_method", sa.String(length=30), nullable=False),
        sa.Column("source_name", sa.String(length=300), nullable=False),
        sa.Column("source_identifier", sa.String(length=500), nullable=True),
        sa.Column("source_url", sa.String(length=2000), nullable=True),
        sa.Column("license", sa.String(length=300), nullable=True),
        sa.Column("access_classification", sa.String(length=80), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("original_filename", sa.String(length=500), nullable=True),
        sa.Column("media_type", sa.String(length=120), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('NOT_REQUESTED', 'RETRIEVAL_PENDING', 'RETRIEVED', 'OPEN_ACCESS', "
            "'USER_UPLOADED', 'EXTERNAL_LINK_ONLY', 'PAYWALLED', 'NOT_FOUND', 'INVALID_FILE', "
            "'PROCESSING', 'PROCESSED', 'PROCESSING_FAILED', 'RETRACTION_WARNING', "
            "'SUPPLEMENT_AVAILABLE')",
            name="ck_documents_status",
        ),
        sa.CheckConstraint(
            "retrieval_method IN ('PUBLISHER', 'REPOSITORY', 'USER_UPLOAD', 'EXTERNAL_LINK', 'MANUAL')",
            name="ck_documents_retrieval_method",
        ),
        sa.CheckConstraint("file_size IS NULL OR file_size >= 0", name="ck_documents_file_size"),
        sa.CheckConstraint(
            "sha256 IS NULL OR length(sha256) = 64", name="ck_documents_sha256_length"
        ),
        sa.ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_documents_article_tenant_review",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "uploaded_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_documents_uploader_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_documents_id_tenant"),
        sa.UniqueConstraint(
            "organization_id", "review_id", "article_id", "sha256", name="uq_documents_article_checksum"
        ),
    )
    op.create_table(
        "document_processing_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("parser_name", sa.String(length=120), nullable=False),
        sa.Column("parser_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')", name="ck_document_runs_status"
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_document_runs_document_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "requested_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_document_runs_requester_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_document_runs_id_tenant"),
    )
    op.create_table(
        "document_blocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("block_id", sa.String(length=160), nullable=False),
        sa.Column("block_type", sa.String(length=30), nullable=False),
        sa.Column("block_order", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_path", sa.JSON(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("table_id", sa.String(length=160), nullable=True),
        sa.Column("figure_id", sa.String(length=160), nullable=True),
        sa.Column("coordinates", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_document_blocks_document_tenant",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "block_id", name="uq_document_blocks_document_block"),
        sa.UniqueConstraint(
            "id", "document_id", "organization_id", "review_id", name="uq_document_blocks_id_tenant"
        ),
    )
    op.create_table(
        "document_evidence_locations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("block_id", sa.Uuid(), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=500), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("table_id", sa.String(length=160), nullable=True),
        sa.Column("figure_id", sa.String(length=160), nullable=True),
        sa.Column("coordinates", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_document_locations_document_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["block_id", "document_id", "organization_id", "review_id"],
            [
                "document_blocks.id",
                "document_blocks.document_id",
                "document_blocks.organization_id",
                "document_blocks.review_id",
            ],
            name="fk_document_locations_block_tenant",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_document_locations_id_tenant"),
        sa.UniqueConstraint(
            "id", "document_id", "organization_id", "review_id",
            name="uq_document_locations_id_document_tenant",
        ),
    )
    op.create_table(
        "document_warnings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('RETRACTION', 'CORRECTION', 'EXPRESSION_OF_CONCERN', 'INVALID_FULL_TEXT')",
            name="ck_document_warnings_kind",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_document_warnings_document_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_document_warnings_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "full_text_screenings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("protocol_version_id", sa.Uuid(), nullable=False),
        sa.Column("final_decision", sa.String(length=20), nullable=False),
        sa.Column("primary_reason", sa.Text(), nullable=True),
        sa.Column("decided_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "final_decision IN ('INCLUDE', 'EXCLUDE', 'MAYBE')",
            name="ck_full_text_screenings_decision",
        ),
        sa.ForeignKeyConstraint(
            ["document_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_full_text_screenings_document_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["protocol_version_id", "organization_id", "review_id"],
            ["protocol_versions.id", "protocol_versions.organization_id", "protocol_versions.review_id"],
            name="fk_full_text_screenings_protocol_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "decided_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_full_text_screenings_decider_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "protocol_version_id", name="uq_full_text_screenings_document_protocol"
        ),
        sa.UniqueConstraint("id", "organization_id", "review_id", name="uq_full_text_screenings_id_tenant"),
    )
    op.create_table(
        "full_text_criterion_judgments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("screening_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("review_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_key", sa.String(length=200), nullable=False),
        sa.Column("decision", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence_location_id", sa.Uuid(), nullable=True),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("decided_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "decision IN ('PASS', 'FAIL', 'UNCLEAR', 'NOT_APPLICABLE')",
            name="ck_full_text_judgments_decision",
        ),
        sa.ForeignKeyConstraint(
            ["screening_id", "organization_id", "review_id"],
            ["full_text_screenings.id", "full_text_screenings.organization_id", "full_text_screenings.review_id"],
            name="fk_full_text_judgments_screening_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_location_id", "document_id", "organization_id", "review_id"],
            [
                "document_evidence_locations.id",
                "document_evidence_locations.document_id",
                "document_evidence_locations.organization_id",
                "document_evidence_locations.review_id",
            ],
            name="fk_full_text_judgments_location_tenant",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "decided_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_full_text_judgments_decider_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "screening_id", "criterion_key", name="uq_full_text_judgments_screening_criterion"
        ),
    )


def downgrade() -> None:
    op.drop_table("full_text_criterion_judgments")
    op.drop_table("full_text_screenings")
    op.drop_table("document_warnings")
    op.drop_table("document_evidence_locations")
    op.drop_table("document_blocks")
    op.drop_table("document_processing_runs")
    op.drop_table("documents")
