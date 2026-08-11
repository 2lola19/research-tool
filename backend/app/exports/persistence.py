from __future__ import annotations

from collections import defaultdict
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

from backend.app.citations.persistence import ArticleRecord, CitationSourceRecordRow
from backend.app.db.base import Base
from backend.app.exports.domain import (
    ExportArticle,
    ExportArtifact,
    ExportDataset,
    ExportFormat,
    ExportSearchExecution,
    ExportStudy,
)
from backend.app.prisma.domain import PrismaSnapshot
from backend.app.reviews.persistence import ReviewRecord
from backend.app.search.execution_persistence import SqlAlchemySearchExecutionRepository
from backend.app.studies.persistence import StudyArticleLinkRecord, StudyRecord


class ExportArtifactRecord(Base):
    __tablename__ = "export_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_export_artifacts_id_tenant"
        ),
        CheckConstraint("export_format IN ('CSV','XLSX','JSON','RIS')", name="ck_export_format"),
        CheckConstraint("length(sha256) = 64", name="ck_export_sha256_length"),
        CheckConstraint("byte_size >= 0", name="ck_export_byte_size"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_export_artifacts_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["prisma_snapshot_id", "organization_id", "review_id"],
            [
                "prisma_snapshots.id",
                "prisma_snapshots.organization_id",
                "prisma_snapshots.review_id",
            ],
            name="fk_export_artifacts_prisma_snapshot",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_export_artifacts_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    prisma_snapshot_id: Mapped[UUID] = mapped_column()
    created_by_user_id: Mapped[UUID] = mapped_column()
    export_format: Mapped[str] = mapped_column(String(10))
    schema_version: Mapped[str] = mapped_column(String(80))
    filename: Mapped[str] = mapped_column(String(500))
    media_type: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _reject_artifact_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("export artifacts are immutable")


event.listen(ExportArtifactRecord, "before_update", _reject_artifact_mutation)
event.listen(ExportArtifactRecord, "before_delete", _reject_artifact_mutation)


def _artifact(row: ExportArtifactRecord, *, include_content: bool = False) -> ExportArtifact:
    return ExportArtifact(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        prisma_snapshot_id=row.prisma_snapshot_id,
        created_by_user_id=row.created_by_user_id,
        export_format=ExportFormat(row.export_format),
        schema_version=row.schema_version,
        filename=row.filename,
        media_type=row.media_type,
        sha256=row.sha256,
        byte_size=row.byte_size,
        manifest=row.manifest,
        created_at=row.created_at or datetime.now(UTC),
        content=row.content if include_content else None,
    )


class SqlAlchemyExportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def build_dataset(self, snapshot: PrismaSnapshot) -> ExportDataset:
        review = (
            await self._session.execute(
                select(ReviewRecord).where(
                    ReviewRecord.id == snapshot.review_id,
                    ReviewRecord.organization_id == snapshot.organization_id,
                )
            )
        ).scalar_one()
        articles = list(
            await self._session.scalars(
                select(ArticleRecord)
                .where(
                    ArticleRecord.organization_id == snapshot.organization_id,
                    ArticleRecord.review_id == snapshot.review_id,
                )
                .order_by(ArticleRecord.id)
            )
        )
        sources = list(
            await self._session.scalars(
                select(CitationSourceRecordRow)
                .where(
                    CitationSourceRecordRow.organization_id == snapshot.organization_id,
                    CitationSourceRecordRow.review_id == snapshot.review_id,
                )
                .order_by(
                    CitationSourceRecordRow.import_batch_id,
                    CitationSourceRecordRow.ordinal,
                    CitationSourceRecordRow.id,
                )
            )
        )
        studies = list(
            await self._session.scalars(
                select(StudyRecord)
                .where(
                    StudyRecord.organization_id == snapshot.organization_id,
                    StudyRecord.review_id == snapshot.review_id,
                )
                .order_by(StudyRecord.study_key, StudyRecord.id)
            )
        )
        links = list(
            await self._session.scalars(
                select(StudyArticleLinkRecord)
                .where(
                    StudyArticleLinkRecord.organization_id == snapshot.organization_id,
                    StudyArticleLinkRecord.review_id == snapshot.review_id,
                    StudyArticleLinkRecord.unlinked_at.is_(None),
                )
                .order_by(StudyArticleLinkRecord.id)
            )
        )
        executions = await SqlAlchemySearchExecutionRepository(self._session).list_executions(
            snapshot.organization_id, snapshot.review_id
        )
        source_ids: dict[UUID, list[UUID]] = defaultdict(list)
        for source in sources:
            source_ids[source.article_id].append(source.id)
        study_by_id = {study.id: study for study in studies}
        study_keys: dict[UUID, list[str]] = defaultdict(list)
        article_ids: dict[UUID, list[UUID]] = defaultdict(list)
        for link in links:
            study = study_by_id[link.study_id]
            study_keys[link.article_id].append(study.study_key)
            article_ids[link.study_id].append(link.article_id)
        return ExportDataset(
            organization_id=snapshot.organization_id,
            review_id=snapshot.review_id,
            review_title=review.title,
            prisma_snapshot_id=snapshot.id,
            prisma_algorithm_version=snapshot.algorithm_version,
            prisma_counts=snapshot.counts,
            prisma_readiness=snapshot.readiness,
            prisma_source_references=snapshot.source_references,
            articles=tuple(
                ExportArticle(
                    id=article.id,
                    title=article.title,
                    abstract=article.abstract,
                    publication_year=article.publication_year,
                    doi=article.doi,
                    pmid=article.pmid,
                    authors=tuple(article.authors),
                    journal=article.journal,
                    source_record_ids=tuple(sorted(source_ids[article.id], key=str)),
                    study_keys=tuple(sorted(study_keys[article.id])),
                )
                for article in articles
            ),
            studies=tuple(
                ExportStudy(
                    id=study.id,
                    study_key=study.study_key,
                    label=study.label,
                    article_ids=tuple(sorted(article_ids[study.id], key=str)),
                )
                for study in studies
            ),
            search_executions=tuple(
                ExportSearchExecution(
                    id=execution.id,
                    source_name=execution.source.display_name,
                    provider_name=execution.source.provider_name,
                    platform_name=execution.source.platform_name,
                    source_classification=execution.source.classification.value,
                    method=execution.method.value,
                    executed_at=execution.executed_at,
                    search_strategy_version_id=execution.search_strategy_version_id,
                    search_translation_id=execution.search_translation_id,
                    exact_query=execution.exact_query,
                    filters=tuple(sorted(execution.filters.items())),
                    software_version=execution.software_version,
                    status=execution.current_event.status.value,
                    provider_result_count=execution.current_event.provider_result_count,
                    imported_record_count=execution.imported_record_count,
                    status_history=tuple(
                        (
                            event.sequence,
                            event.status.value,
                            event.occurred_at,
                            event.provider_result_count,
                            event.note,
                        )
                        for event in execution.events
                    ),
                )
                for execution in executions
            ),
        )

    async def create_artifact(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        prisma_snapshot_id: UUID,
        created_by_user_id: UUID,
        export_format: ExportFormat,
        schema_version: str,
        filename: str,
        media_type: str,
        sha256: str,
        content: bytes,
        manifest: dict[str, Any],
    ) -> ExportArtifact:
        row = ExportArtifactRecord(
            organization_id=organization_id,
            review_id=review_id,
            prisma_snapshot_id=prisma_snapshot_id,
            created_by_user_id=created_by_user_id,
            export_format=export_format.value,
            schema_version=schema_version,
            filename=filename,
            media_type=media_type,
            sha256=sha256,
            byte_size=len(content),
            manifest=manifest,
            content=content,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _artifact(row)

    async def get_artifact(
        self,
        organization_id: UUID,
        review_id: UUID,
        artifact_id: UUID,
        *,
        include_content: bool,
    ) -> ExportArtifact | None:
        row = (
            await self._session.execute(
                select(ExportArtifactRecord).where(
                    ExportArtifactRecord.organization_id == organization_id,
                    ExportArtifactRecord.review_id == review_id,
                    ExportArtifactRecord.id == artifact_id,
                )
            )
        ).scalar_one_or_none()
        return _artifact(row, include_content=include_content) if row else None

    async def list_artifacts(self, organization_id: UUID, review_id: UUID) -> list[ExportArtifact]:
        rows = await self._session.scalars(
            select(ExportArtifactRecord)
            .where(
                ExportArtifactRecord.organization_id == organization_id,
                ExportArtifactRecord.review_id == review_id,
            )
            .order_by(ExportArtifactRecord.created_at, ExportArtifactRecord.id)
        )
        return [_artifact(row) for row in rows]
