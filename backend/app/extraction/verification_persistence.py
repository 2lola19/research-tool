from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.extraction.domain import (
    ConflictResolution,
    ConflictStatus,
    ExtractionConflict,
    ExtractionVerification,
    VerificationStatus,
)


class ExtractionVerificationRecord(Base):
    __tablename__ = "extraction_verifications"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_extraction_verifications_id_tenant"
        ),
        UniqueConstraint(
            "run_a_id", "run_b_id", "field_key", name="uq_extraction_verifications_pair_field"
        ),
        ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_extraction_verifications_study_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["run_a_id", "organization_id", "review_id"],
            ["extraction_runs.id", "extraction_runs.organization_id", "extraction_runs.review_id"],
            name="fk_extraction_verifications_run_a_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["run_b_id", "organization_id", "review_id"],
            ["extraction_runs.id", "extraction_runs.organization_id", "extraction_runs.review_id"],
            name="fk_extraction_verifications_run_b_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["conflict_id", "organization_id", "review_id"],
            [
                "extraction_conflicts.id",
                "extraction_conflicts.organization_id",
                "extraction_conflicts.review_id",
            ],
            name="fk_extraction_verifications_conflict_tenant",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    study_id: Mapped[UUID] = mapped_column()
    schema_version_id: Mapped[UUID] = mapped_column()
    field_key: Mapped[str] = mapped_column(String(200))
    run_a_id: Mapped[UUID] = mapped_column()
    run_b_id: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(30))
    conflict_id: Mapped[UUID | None] = mapped_column()


class ExtractionConflictRecord(Base):
    __tablename__ = "extraction_conflicts"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_extraction_conflicts_id_tenant"
        ),
        ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_extraction_conflicts_study_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["run_a_id", "organization_id", "review_id"],
            ["extraction_runs.id", "extraction_runs.organization_id", "extraction_runs.review_id"],
            name="fk_extraction_conflicts_run_a_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["run_b_id", "organization_id", "review_id"],
            ["extraction_runs.id", "extraction_runs.organization_id", "extraction_runs.review_id"],
            name="fk_extraction_conflicts_run_b_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "adjudicated_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_extraction_conflicts_adjudicator_membership",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    study_id: Mapped[UUID] = mapped_column()
    schema_version_id: Mapped[UUID] = mapped_column()
    field_key: Mapped[str] = mapped_column(String(200))
    run_a_id: Mapped[UUID] = mapped_column()
    run_b_id: Mapped[UUID] = mapped_column()
    value_a: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    value_b: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    evidence_a: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    evidence_b: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default=ConflictStatus.OPEN.value)
    resolution: Mapped[str | None] = mapped_column(String(50))
    adjudicated_value: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    adjudicated_by_user_id: Mapped[UUID | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def _conflict(record: ExtractionConflictRecord) -> ExtractionConflict:
    return ExtractionConflict(
        record.id,
        record.organization_id,
        record.review_id,
        record.study_id,
        record.schema_version_id,
        record.field_key,
        record.run_a_id,
        record.run_b_id,
        record.value_a,
        record.value_b,
        record.evidence_a,
        record.evidence_b,
        ConflictStatus(record.status),
        ConflictResolution(record.resolution) if record.resolution else None,
        record.adjudicated_value,
        record.adjudicated_by_user_id,
        record.reason,
        record.resolved_at,
    )


def _verification(record: ExtractionVerificationRecord) -> ExtractionVerification:
    return ExtractionVerification(
        record.id,
        record.organization_id,
        record.review_id,
        record.study_id,
        record.schema_version_id,
        record.field_key,
        record.run_a_id,
        record.run_b_id,
        VerificationStatus(record.status),
        record.conflict_id,
    )


class SqlAlchemyExtractionVerificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_comparison(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        study_id: UUID,
        schema_version_id: UUID,
        run_a_id: UUID,
        run_b_id: UUID,
        comparisons: list[dict[str, Any]],
    ) -> list[ExtractionVerification]:
        result: list[ExtractionVerification] = []
        for item in comparisons:
            conflict_id: UUID | None = None
            if item["status"] == VerificationStatus.NEEDS_ADJUDICATION.value:
                conflict = ExtractionConflictRecord(
                    organization_id=organization_id,
                    review_id=review_id,
                    study_id=study_id,
                    schema_version_id=schema_version_id,
                    field_key=item["field_key"],
                    run_a_id=run_a_id,
                    run_b_id=run_b_id,
                    value_a=item.get("value_a"),
                    value_b=item.get("value_b"),
                    evidence_a=item.get("evidence_a"),
                    evidence_b=item.get("evidence_b"),
                )
                self._session.add(conflict)
                await self._session.flush()
                conflict_id = conflict.id
                item["conflict_id"] = conflict_id
            verification = ExtractionVerificationRecord(
                organization_id=organization_id,
                review_id=review_id,
                study_id=study_id,
                schema_version_id=schema_version_id,
                field_key=item["field_key"],
                run_a_id=run_a_id,
                run_b_id=run_b_id,
                status=item["status"],
                conflict_id=conflict_id,
            )
            self._session.add(verification)
            await self._session.flush()
            result.append(_verification(verification))
        return result

    async def get_conflict(
        self, organization_id: UUID, review_id: UUID, conflict_id: UUID
    ) -> ExtractionConflict | None:
        record = (
            await self._session.execute(
                select(ExtractionConflictRecord).where(
                    ExtractionConflictRecord.organization_id == organization_id,
                    ExtractionConflictRecord.review_id == review_id,
                    ExtractionConflictRecord.id == conflict_id,
                )
            )
        ).scalar_one_or_none()
        return _conflict(record) if record else None

    async def resolve_conflict(
        self,
        *,
        conflict: ExtractionConflict,
        resolution: str,
        adjudicated_value: dict[str, Any] | None,
        adjudicated_by_user_id: UUID,
        reason: str,
    ) -> ExtractionConflict:
        record = (
            await self._session.execute(
                select(ExtractionConflictRecord).where(
                    ExtractionConflictRecord.id == conflict.id,
                    ExtractionConflictRecord.organization_id == conflict.organization_id,
                    ExtractionConflictRecord.review_id == conflict.review_id,
                )
            )
        ).scalar_one()
        record.status = ConflictStatus.RESOLVED.value
        record.resolution = resolution
        record.adjudicated_value = adjudicated_value
        record.adjudicated_by_user_id = adjudicated_by_user_id
        record.reason = reason
        from datetime import UTC, datetime

        record.resolved_at = datetime.now(UTC)
        verifications = (
            await self._session.execute(
                select(ExtractionVerificationRecord).where(
                    ExtractionVerificationRecord.conflict_id == conflict.id,
                    ExtractionVerificationRecord.organization_id == conflict.organization_id,
                    ExtractionVerificationRecord.review_id == conflict.review_id,
                )
            )
        ).scalars()
        for verification in verifications:
            verification.status = VerificationStatus.ADJUDICATED.value
        await self._session.flush()
        return _conflict(record)
