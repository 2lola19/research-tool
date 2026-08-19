"""Add verified document processing metadata and chunk manifests.

Revision ID: 20260819_0035
Revises: 20260819_0034
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260819_0035"
down_revision: str | None = "20260819_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("document_processing_runs", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("failure_class", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("content_sha256", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("content_size", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("chunk_manifest_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("chunk_manifest", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("block_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("text_byte_size", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.create_check_constraint(
            "ck_document_runs_failure_class",
            "failure_class IS NULL OR failure_class IN "
            "('STORAGE_MISSING','STORAGE_INTEGRITY','PARSER_INVALID','PARSER_LIMIT',"
            "'PARSER_TIMEOUT','UNEXPECTED')",
        )
        batch_op.create_check_constraint(
            "ck_document_runs_content_size",
            "content_size IS NULL OR content_size >= 0",
        )
        batch_op.create_check_constraint("ck_document_runs_block_count", "block_count >= 0")
        batch_op.create_check_constraint("ck_document_runs_text_size", "text_byte_size >= 0")
        batch_op.create_check_constraint(
            "ck_document_runs_content_hash",
            "content_sha256 IS NULL OR length(content_sha256) = 64",
        )
        batch_op.create_check_constraint(
            "ck_document_runs_manifest_hash",
            "chunk_manifest_hash IS NULL OR length(chunk_manifest_hash) = 64",
        )


def downgrade() -> None:
    with op.batch_alter_table("document_processing_runs", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_document_runs_manifest_hash", type_="check")
        batch_op.drop_constraint("ck_document_runs_content_hash", type_="check")
        batch_op.drop_constraint("ck_document_runs_text_size", type_="check")
        batch_op.drop_constraint("ck_document_runs_block_count", type_="check")
        batch_op.drop_constraint("ck_document_runs_content_size", type_="check")
        batch_op.drop_constraint("ck_document_runs_failure_class", type_="check")
        batch_op.drop_column("text_byte_size")
        batch_op.drop_column("block_count")
        batch_op.drop_column("chunk_manifest")
        batch_op.drop_column("chunk_manifest_hash")
        batch_op.drop_column("content_size")
        batch_op.drop_column("content_sha256")
        batch_op.drop_column("failure_class")
