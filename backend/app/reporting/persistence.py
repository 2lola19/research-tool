from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    event,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from backend.app.db.base import Base
from backend.app.exports.persistence import SqlAlchemyExportRepository
from backend.app.prisma.domain import PrismaSnapshot
from backend.app.reporting.domain import (
    ReportArtifact,
    ReportFormat,
    ReportSnapshot,
    ReportSpecification,
    ReportStatus,
    ReportType,
)


class ReportSpecificationRecord(Base):
    __tablename__ = "report_specifications"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_report_specifications_id_tenant"
        ),
        UniqueConstraint(
            "organization_id",
            "review_id",
            "logical_key",
            "version",
            name="uq_report_specifications_version",
        ),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_report_specifications_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_report_specifications_creator",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    logical_key: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer)
    report_type: Mapped[str] = mapped_column(String(50))
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportSnapshotRecord(Base):
    __tablename__ = "report_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_report_snapshots_id_tenant"
        ),
        CheckConstraint(
            "status IN ('QUEUED','RUNNING','COMPLETED','FAILED')", name="ck_report_snapshot_status"
        ),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_report_snapshots_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["specification_id", "organization_id", "review_id"],
            [
                "report_specifications.id",
                "report_specifications.organization_id",
                "report_specifications.review_id",
            ],
            name="fk_report_snapshots_specification",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_report_snapshots_creator",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    specification_id: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(20))
    source_references: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_hashes: Mapped[dict[str, Any]] = mapped_column(JSON)
    structured_content: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    scientific_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    renderer_version: Mapped[str] = mapped_column(String(120))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class ReportArtifactRecord(Base):
    __tablename__ = "report_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_report_artifacts_id_tenant"
        ),
        CheckConstraint(
            "report_format IN ('JSON','XLSX','HTML','ZIP')", name="ck_report_artifact_format"
        ),
        CheckConstraint("byte_size >= 0", name="ck_report_artifact_size"),
        ForeignKeyConstraint(
            ["report_snapshot_id", "organization_id", "review_id"],
            [
                "report_snapshots.id",
                "report_snapshots.organization_id",
                "report_snapshots.review_id",
            ],
            name="fk_report_artifacts_snapshot",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    report_snapshot_id: Mapped[UUID] = mapped_column()
    report_format: Mapped[str] = mapped_column(String(10))
    filename: Mapped[str] = mapped_column(String(500))
    media_type: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _immutable(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("reporting scientific records are immutable")


for _record in (ReportSpecificationRecord, ReportSnapshotRecord, ReportArtifactRecord):
    event.listen(_record, "before_update", _immutable)
    event.listen(_record, "before_delete", _immutable)


class SqlAlchemyReportingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_specification(self, **values: Any) -> ReportSpecification:
        latest = await self._session.scalar(
            select(func.max(ReportSpecificationRecord.version)).where(
                ReportSpecificationRecord.organization_id == values["organization_id"],
                ReportSpecificationRecord.review_id == values["review_id"],
                ReportSpecificationRecord.logical_key == values["logical_key"],
            )
        )
        row = ReportSpecificationRecord(**values, version=(latest or 0) + 1)
        self._session.add(row)
        await self._session.flush()
        return _specification(row)

    async def get_specification(
        self, organization_id: UUID, review_id: UUID, specification_id: UUID
    ) -> ReportSpecification | None:
        row = await self._session.scalar(
            select(ReportSpecificationRecord).where(
                ReportSpecificationRecord.organization_id == organization_id,
                ReportSpecificationRecord.review_id == review_id,
                ReportSpecificationRecord.id == specification_id,
            )
        )
        return _specification(row) if row else None

    async def build_source_payload(
        self, organization_id: UUID, review_id: UUID, prisma_snapshot_id: UUID
    ) -> dict[str, Any]:
        from backend.app.prisma.persistence import PrismaSnapshotRecord

        row = await self._session.scalar(
            select(PrismaSnapshotRecord).where(
                PrismaSnapshotRecord.organization_id == organization_id,
                PrismaSnapshotRecord.review_id == review_id,
                PrismaSnapshotRecord.id == prisma_snapshot_id,
            )
        )
        if row is None:
            raise ValueError("PRISMA snapshot was not found")
        snapshot = PrismaSnapshot(
            id=row.id,
            organization_id=row.organization_id,
            review_id=row.review_id,
            created_by_user_id=row.created_by_user_id,
            algorithm_version=row.algorithm_version,
            counts=row.counts,
            readiness=row.readiness,
            source_references=row.source_references,
            created_at=row.created_at,
        )
        dataset = await SqlAlchemyExportRepository(self._session).build_dataset(snapshot)
        payload = _dataset_payload(dataset)
        from backend.app.ai.reporting import accepted_ai_provenance

        payload["sections"]["provenance"] = await accepted_ai_provenance(
            self._session, organization_id, review_id
        )
        return payload

    async def current_source_hashes(self, organization_id: UUID, review_id: UUID) -> dict[str, Any]:
        from backend.app.reporting.source_reader import read_scientific_tables, table_hashes

        tables = await read_scientific_tables(self._session, organization_id, review_id)
        return table_hashes(tables)

    async def create_snapshot(self, **values: Any) -> ReportSnapshot:
        row = ReportSnapshotRecord(**values, completed_at=datetime.now(UTC))
        self._session.add(row)
        await self._session.flush()
        return _snapshot(row)

    async def create_artifact(self, **values: Any) -> ReportArtifact:
        content = values["content"]
        row = ReportArtifactRecord(**values, byte_size=len(content))
        self._session.add(row)
        await self._session.flush()
        return _artifact(row)

    async def list_snapshots(self, organization_id: UUID, review_id: UUID) -> list[ReportSnapshot]:
        rows = await self._session.scalars(
            select(ReportSnapshotRecord)
            .where(
                ReportSnapshotRecord.organization_id == organization_id,
                ReportSnapshotRecord.review_id == review_id,
            )
            .order_by(ReportSnapshotRecord.created_at, ReportSnapshotRecord.id)
        )
        return [_snapshot(row) for row in rows]

    async def get_snapshot(
        self, organization_id: UUID, review_id: UUID, snapshot_id: UUID
    ) -> ReportSnapshot | None:
        row = await self._session.scalar(
            select(ReportSnapshotRecord).where(
                ReportSnapshotRecord.organization_id == organization_id,
                ReportSnapshotRecord.review_id == review_id,
                ReportSnapshotRecord.id == snapshot_id,
            )
        )
        return _snapshot(row) if row else None

    async def get_artifact(
        self, organization_id: UUID, review_id: UUID, artifact_id: UUID, *, include_content: bool
    ) -> ReportArtifact | None:
        row = await self._session.scalar(
            select(ReportArtifactRecord).where(
                ReportArtifactRecord.organization_id == organization_id,
                ReportArtifactRecord.review_id == review_id,
                ReportArtifactRecord.id == artifact_id,
            )
        )
        return _artifact(row, include_content=include_content) if row else None

    async def list_artifacts(self, organization_id: UUID, review_id: UUID) -> list[ReportArtifact]:
        rows = await self._session.scalars(
            select(ReportArtifactRecord)
            .where(
                ReportArtifactRecord.organization_id == organization_id,
                ReportArtifactRecord.review_id == review_id,
            )
            .order_by(ReportArtifactRecord.created_at, ReportArtifactRecord.id)
        )
        return [_artifact(row) for row in rows]


def _specification(row: ReportSpecificationRecord) -> ReportSpecification:
    return ReportSpecification(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        logical_key=row.logical_key,
        version=row.version,
        report_type=ReportType(row.report_type),
        definition=row.definition,
        content_hash=row.content_hash,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
    )


def _snapshot(row: ReportSnapshotRecord) -> ReportSnapshot:
    return ReportSnapshot(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        specification_id=row.specification_id,
        status=ReportStatus(row.status),
        source_references=row.source_references,
        source_hashes=row.source_hashes,
        structured_content=row.structured_content,
        scientific_content_hash=row.scientific_content_hash,
        renderer_version=row.renderer_version,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        completed_at=row.completed_at,
        failure_reason=row.failure_reason,
    )


def _artifact(row: ReportArtifactRecord, *, include_content: bool = False) -> ReportArtifact:
    return ReportArtifact(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        report_snapshot_id=row.report_snapshot_id,
        report_format=ReportFormat(row.report_format),
        filename=row.filename,
        media_type=row.media_type,
        sha256=row.sha256,
        byte_size=row.byte_size,
        manifest=row.manifest,
        created_at=row.created_at,
        content=row.content if include_content else None,
    )


def _table_names(connection: Any) -> list[str]:
    from sqlalchemy import inspect

    return list(inspect(connection).get_table_names())


def _column_names(connection: Any, table: str) -> list[str]:
    from sqlalchemy import inspect

    return [str(item["name"]) for item in inspect(connection).get_columns(table)]


def _hash_rows(rows: Any) -> str:
    from backend.app.reporting.domain import content_hash

    return content_hash(
        [
            {
                key: str(value) if isinstance(value, (UUID, datetime, bytes)) else value
                for key, value in sorted(row.items())
            }
            for row in rows
        ]
    )


def _dataset_payload(dataset: Any) -> dict[str, Any]:
    from dataclasses import asdict

    return {
        "review": {"id": str(dataset.review_id), "title": dataset.review_title},
        "source_references": {
            "prisma_snapshot_id": str(dataset.prisma_snapshot_id),
            **dataset.prisma_source_references,
        },
        "sections": {
            "prisma": {
                "counts": dataset.prisma_counts,
                "readiness": dataset.prisma_readiness,
                "algorithm_version": dataset.prisma_algorithm_version,
            },
            "search": [asdict(item) for item in dataset.search_executions],
            "citations": [asdict(item) for item in dataset.articles],
            "studies": [asdict(item) for item in dataset.studies],
            "risk_of_bias": {
                "assessments": [asdict(item) for item in dataset.risk_of_bias_assessments],
                "comparisons": [asdict(item) for item in dataset.risk_of_bias_comparisons],
            },
            "outcomes": {
                "definitions": list(dataset.outcome_versions),
                "mappings": list(dataset.outcome_mappings),
                "effect_estimates": list(dataset.effect_estimates),
            },
            "analysis": {
                "specifications": list(dataset.analysis_specification_versions),
                "sets": list(dataset.analysis_sets),
                "runs": list(dataset.meta_analysis_runs),
                "weights": list(dataset.analysis_study_weights),
                "sensitivity": list(dataset.analysis_sensitivities),
                "artifacts": list(dataset.analysis_artifacts),
            },
            "certainty": {
                "frameworks": list(dataset.certainty_framework_versions),
                "assessments": list(dataset.certainty_assessments),
                "comparisons": list(dataset.certainty_comparisons),
                "summary_of_findings": list(dataset.summary_of_findings),
            },
            "protocol": [],
            "screening": {},
            "extraction": {},
            "provenance": [],
        },
    }
