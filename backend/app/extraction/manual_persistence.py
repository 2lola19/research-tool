from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.documents.persistence import DocumentEvidenceLocationRecord, DocumentRecord
from backend.app.extraction.domain import (
    ExtractionRun,
    ExtractionRunStatus,
    ExtractionValue,
    MissingnessState,
)


class ExtractionRunRecord(Base):
    __tablename__ = "extraction_runs"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_extraction_runs_id_tenant"),
        CheckConstraint(
            "status IN ('NOT_STARTED','IN_PROGRESS','COMPLETED','NEEDS_REVIEW',"
            "'VERIFIED','CONFLICT')",
            name="ck_extraction_runs_status",
        ),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_extraction_runs_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_extraction_runs_study_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["schema_version_id", "organization_id", "review_id"],
            [
                "extraction_schema_versions.id",
                "extraction_schema_versions.organization_id",
                "extraction_schema_versions.review_id",
            ],
            name="fk_extraction_runs_schema_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "extractor_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_extraction_runs_extractor_membership",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    study_id: Mapped[UUID] = mapped_column()
    schema_version_id: Mapped[UUID] = mapped_column()
    extractor_user_id: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default=ExtractionRunStatus.NOT_STARTED.value)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExtractionValueRecord(Base):
    __tablename__ = "extraction_values"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_extraction_values_id_tenant"
        ),
        UniqueConstraint("run_id", "field_key", name="uq_extraction_values_run_field"),
        CheckConstraint(
            "missingness IN ('VALUE_REPORTED','NOT_REPORTED','UNCLEAR',"
            "'NOT_APPLICABLE','NEEDS_REVIEW')",
            name="ck_extraction_values_missingness",
        ),
        ForeignKeyConstraint(
            ["run_id", "organization_id", "review_id"],
            ["extraction_runs.id", "extraction_runs.organization_id", "extraction_runs.review_id"],
            name="fk_extraction_values_run_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["source_article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_extraction_values_article_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["evidence_location_id", "organization_id", "review_id"],
            [
                "document_evidence_locations.id",
                "document_evidence_locations.organization_id",
                "document_evidence_locations.review_id",
            ],
            name="fk_extraction_values_evidence_tenant",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    field_key: Mapped[str] = mapped_column(String(200))
    missingness: Mapped[str] = mapped_column(String(20))
    value_integer: Mapped[int | None] = mapped_column(Integer)
    value_decimal: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    value_text: Mapped[str | None] = mapped_column(Text)
    value_boolean: Mapped[bool | None] = mapped_column()
    value_date: Mapped[date | None] = mapped_column(Date)
    value_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(JSON)
    unit: Mapped[str | None] = mapped_column(String(100))
    source_article_id: Mapped[UUID | None] = mapped_column()
    evidence_location_id: Mapped[UUID | None] = mapped_column()
    evidence_text: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def _run(record: ExtractionRunRecord) -> ExtractionRun:
    return ExtractionRun(
        record.id,
        record.organization_id,
        record.review_id,
        record.study_id,
        record.schema_version_id,
        record.extractor_user_id,
        ExtractionRunStatus(record.status),
        record.started_at,
        record.completed_at,
        record.created_at or datetime.now(UTC),
    )


def _value(record: ExtractionValueRecord) -> ExtractionValue:
    return ExtractionValue(
        record.id,
        record.run_id,
        record.field_key,
        MissingnessState(record.missingness),
        record.value_integer,
        str(record.value_decimal) if record.value_decimal is not None else None,
        record.value_text,
        record.value_boolean,
        record.value_date.isoformat() if record.value_date else None,
        record.value_json,
        record.unit,
        record.source_article_id,
        record.evidence_location_id,
        record.evidence_text,
        record.updated_at or datetime.now(UTC),
    )


class SqlAlchemyManualExtractionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_run(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        study_id: UUID,
        schema_version_id: UUID,
        extractor_user_id: UUID,
    ) -> ExtractionRun:
        record = ExtractionRunRecord(
            organization_id=organization_id,
            review_id=review_id,
            study_id=study_id,
            schema_version_id=schema_version_id,
            extractor_user_id=extractor_user_id,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _run(record)

    async def get_run(
        self, organization_id: UUID, review_id: UUID, run_id: UUID
    ) -> ExtractionRun | None:
        record = (
            await self._session.execute(
                select(ExtractionRunRecord).where(
                    ExtractionRunRecord.organization_id == organization_id,
                    ExtractionRunRecord.review_id == review_id,
                    ExtractionRunRecord.id == run_id,
                )
            )
        ).scalar_one_or_none()
        return _run(record) if record else None

    async def list_values(
        self, organization_id: UUID, review_id: UUID, run_id: UUID
    ) -> list[ExtractionValue]:
        records = (
            await self._session.execute(
                select(ExtractionValueRecord)
                .where(
                    ExtractionValueRecord.organization_id == organization_id,
                    ExtractionValueRecord.review_id == review_id,
                    ExtractionValueRecord.run_id == run_id,
                )
                .order_by(ExtractionValueRecord.field_key)
            )
        ).scalars()
        return [_value(record) for record in records]

    async def save_values(
        self, *, run: ExtractionRun, values: list[dict[str, Any]], status: ExtractionRunStatus
    ) -> list[ExtractionValue]:
        record = (
            await self._session.execute(
                select(ExtractionRunRecord).where(
                    ExtractionRunRecord.id == run.id,
                    ExtractionRunRecord.organization_id == run.organization_id,
                    ExtractionRunRecord.review_id == run.review_id,
                )
            )
        ).scalar_one()
        record.status = status.value
        record.started_at = record.started_at or datetime.now(UTC)
        record.completed_at = datetime.now(UTC) if status == ExtractionRunStatus.COMPLETED else None
        for item in values:
            existing = (
                await self._session.execute(
                    select(ExtractionValueRecord).where(
                        ExtractionValueRecord.run_id == run.id,
                        ExtractionValueRecord.field_key == item["field_key"],
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                existing = ExtractionValueRecord(
                    run_id=run.id,
                    organization_id=run.organization_id,
                    review_id=run.review_id,
                    **item,
                )
                self._session.add(existing)
            else:
                for key, value in item.items():
                    setattr(existing, key, value)
        await self._session.flush()
        return await self.list_values(run.organization_id, run.review_id, run.id)

    async def get_evidence_source(
        self, organization_id: UUID, review_id: UUID, evidence_location_id: UUID
    ) -> tuple[UUID, UUID] | None:
        query = (
            select(DocumentEvidenceLocationRecord.id, DocumentRecord.article_id)
            .join(DocumentRecord, DocumentRecord.id == DocumentEvidenceLocationRecord.document_id)
            .where(
                DocumentEvidenceLocationRecord.id == evidence_location_id,
                DocumentEvidenceLocationRecord.organization_id == organization_id,
                DocumentEvidenceLocationRecord.review_id == review_id,
            )
        )
        row = (await self._session.execute(query)).one_or_none()
        return (row[0], row[1]) if row else None
