"""Enforce workflow job payload and retry bounds.

Revision ID: 20260819_0036
Revises: 20260819_0035
Create Date: 2026-08-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260819_0036"
down_revision: str | None = "20260819_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.create_check_constraint(
            "ck_workflow_jobs_payload_version",
            "workflow_jobs",
            "payload_version > 0",
        )
        op.create_check_constraint(
            "ck_workflow_jobs_max_attempts",
            "workflow_jobs",
            "max_attempts > 0 AND max_attempts <= 100",
        )
    else:
        with op.batch_alter_table("workflow_jobs", recreate="always") as batch_op:
            batch_op.create_check_constraint(
                "ck_workflow_jobs_payload_version",
                "payload_version > 0",
            )
            batch_op.create_check_constraint(
                "ck_workflow_jobs_max_attempts",
                "max_attempts > 0 AND max_attempts <= 100",
            )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("ck_workflow_jobs_max_attempts", "workflow_jobs", type_="check")
        op.drop_constraint("ck_workflow_jobs_payload_version", "workflow_jobs", type_="check")
    else:
        with op.batch_alter_table("workflow_jobs", recreate="always") as batch_op:
            batch_op.drop_constraint("ck_workflow_jobs_max_attempts", type_="check")
            batch_op.drop_constraint("ck_workflow_jobs_payload_version", type_="check")
