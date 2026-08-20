"""Persist canonical parsed-content hashes and live-parser failure classes.

Revision ID: 20260820_0038
Revises: 20260820_0037
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0038"
down_revision: str | None = "20260820_0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FAILURE_CLASS_CHECK = (
    "failure_class IS NULL OR failure_class IN "
    "('STORAGE_MISSING','STORAGE_INTEGRITY','PARSER_INVALID','PARSER_LIMIT',"
    "'PARSER_TIMEOUT','PARSER_UNAVAILABLE','PARSER_ERROR','PARSER_UNSUPPORTED','UNEXPECTED')"
)
_LEGACY_FAILURE_CLASS_CHECK = (
    "failure_class IS NULL OR failure_class IN "
    "('STORAGE_MISSING','STORAGE_INTEGRITY','PARSER_INVALID','PARSER_LIMIT',"
    "'PARSER_TIMEOUT','UNEXPECTED')"
)


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.add_column(
            "document_processing_runs",
            sa.Column("parsed_content_hash", sa.String(length=64), nullable=True),
        )
        op.drop_constraint(
            "ck_document_runs_failure_class", "document_processing_runs", type_="check"
        )
        op.create_check_constraint(
            "ck_document_runs_failure_class", "document_processing_runs", _FAILURE_CLASS_CHECK
        )
        op.create_check_constraint(
            "ck_document_runs_parsed_hash",
            "document_processing_runs",
            "parsed_content_hash IS NULL OR length(parsed_content_hash) = 64",
        )
    else:
        with op.batch_alter_table("document_processing_runs", recreate="always") as batch_op:
            batch_op.add_column(sa.Column("parsed_content_hash", sa.String(length=64)))
            batch_op.drop_constraint("ck_document_runs_failure_class", type_="check")
            batch_op.create_check_constraint("ck_document_runs_failure_class", _FAILURE_CLASS_CHECK)
            batch_op.create_check_constraint(
                "ck_document_runs_parsed_hash",
                "parsed_content_hash IS NULL OR length(parsed_content_hash) = 64",
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint(
            "ck_document_runs_parsed_hash", "document_processing_runs", type_="check"
        )
        op.drop_constraint(
            "ck_document_runs_failure_class", "document_processing_runs", type_="check"
        )
        op.create_check_constraint(
            "ck_document_runs_failure_class",
            "document_processing_runs",
            _LEGACY_FAILURE_CLASS_CHECK,
        )
        op.drop_column("document_processing_runs", "parsed_content_hash")
    else:
        with op.batch_alter_table("document_processing_runs", recreate="always") as batch_op:
            batch_op.drop_constraint("ck_document_runs_parsed_hash", type_="check")
            batch_op.drop_constraint("ck_document_runs_failure_class", type_="check")
            batch_op.create_check_constraint(
                "ck_document_runs_failure_class", _LEGACY_FAILURE_CLASS_CHECK
            )
            batch_op.drop_column("parsed_content_hash")
