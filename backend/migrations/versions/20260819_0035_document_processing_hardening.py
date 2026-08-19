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


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _document_processing_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("failure_class", sa.String(length=30), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("content_size", sa.Integer(), nullable=True),
        sa.Column("chunk_manifest_hash", sa.String(length=64), nullable=True),
        sa.Column("chunk_manifest", sa.JSON(), nullable=True),
        sa.Column("block_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("text_byte_size", sa.Integer(), server_default="0", nullable=False),
    )


def _create_document_processing_checks() -> None:
    op.create_check_constraint(
        "ck_document_runs_failure_class",
        "document_processing_runs",
        "failure_class IS NULL OR failure_class IN "
        "('STORAGE_MISSING','STORAGE_INTEGRITY','PARSER_INVALID','PARSER_LIMIT',"
        "'PARSER_TIMEOUT','UNEXPECTED')",
    )
    op.create_check_constraint(
        "ck_document_runs_content_size",
        "document_processing_runs",
        "content_size IS NULL OR content_size >= 0",
    )
    op.create_check_constraint(
        "ck_document_runs_block_count",
        "document_processing_runs",
        "block_count >= 0",
    )
    op.create_check_constraint(
        "ck_document_runs_text_size",
        "document_processing_runs",
        "text_byte_size >= 0",
    )
    op.create_check_constraint(
        "ck_document_runs_content_hash",
        "document_processing_runs",
        "content_sha256 IS NULL OR length(content_sha256) = 64",
    )
    op.create_check_constraint(
        "ck_document_runs_manifest_hash",
        "document_processing_runs",
        "chunk_manifest_hash IS NULL OR length(chunk_manifest_hash) = 64",
    )


def _drop_document_processing_checks() -> None:
    for constraint in (
        "ck_document_runs_manifest_hash",
        "ck_document_runs_content_hash",
        "ck_document_runs_text_size",
        "ck_document_runs_block_count",
        "ck_document_runs_content_size",
        "ck_document_runs_failure_class",
    ):
        op.drop_constraint(constraint, "document_processing_runs", type_="check")


def upgrade() -> None:
    if _is_postgresql():
        for column in _document_processing_columns():
            op.add_column("document_processing_runs", column)
        _create_document_processing_checks()
    else:
        with op.batch_alter_table("document_processing_runs", recreate="always") as batch_op:
            for column in _document_processing_columns():
                batch_op.add_column(column)
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
    if _is_postgresql():
        _drop_document_processing_checks()
        for column in (
            "text_byte_size",
            "block_count",
            "chunk_manifest",
            "chunk_manifest_hash",
            "content_size",
            "content_sha256",
            "failure_class",
        ):
            op.drop_column("document_processing_runs", column)
    else:
        with op.batch_alter_table("document_processing_runs", recreate="always") as batch_op:
            batch_op.drop_constraint("ck_document_runs_manifest_hash", type_="check")
            batch_op.drop_constraint("ck_document_runs_content_hash", type_="check")
            batch_op.drop_constraint("ck_document_runs_text_size", type_="check")
            batch_op.drop_constraint("ck_document_runs_block_count", type_="check")
            batch_op.drop_constraint("ck_document_runs_content_size", type_="check")
            batch_op.drop_constraint("ck_document_runs_failure_class", type_="check")
            for column in (
                "text_byte_size",
                "block_count",
                "chunk_manifest",
                "chunk_manifest_hash",
                "content_size",
                "content_sha256",
                "failure_class",
            ):
                batch_op.drop_column(column)
