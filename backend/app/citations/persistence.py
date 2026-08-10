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
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.citations.domain import (
    Article,
    CitationFormat,
    CitationImportBatch,
    CitationSourceRecord,
    ParsedCitation,
)
from backend.app.db.base import Base


class CitationImportBatchRecord(Base):
    __tablename__ = "citation_import_batches"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "review_id",
            "source_format",
            "content_hash",
            name="uq_citation_import_batches_content",
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_citation_import_batches_id_tenant"
        ),
        CheckConstraint("record_count > 0", name="ck_citation_import_batches_record_count"),
        CheckConstraint(
            "source_format IN ('RIS', 'BIBTEX', 'CSV')",
            name="ck_citation_import_batches_format",
        ),
        CheckConstraint("length(content_hash) = 64", name="ck_citation_import_batches_hash_length"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_citation_import_batches_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "imported_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_citation_import_batches_importer_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    source_format: Mapped[str] = mapped_column(String(20))
    source_name: Mapped[str] = mapped_column(String(500))
    source_content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    record_count: Mapped[int] = mapped_column(Integer)
    imported_by_user_id: Mapped[UUID] = mapped_column()
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ArticleRecord(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_articles_id_tenant"),
        CheckConstraint(
            "publication_year IS NULL OR publication_year BETWEEN 1000 AND 3000",
            name="ck_articles_publication_year",
        ),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_articles_review_tenant",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    title: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str | None] = mapped_column(Text)
    publication_year: Mapped[int | None] = mapped_column(Integer)
    doi: Mapped[str | None] = mapped_column(String(500))
    pmid: Mapped[str | None] = mapped_column(String(50))
    authors: Mapped[list[str]] = mapped_column(JSON)
    journal: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CitationSourceRecordRow(Base):
    __tablename__ = "citation_source_records"
    __table_args__ = (
        UniqueConstraint(
            "import_batch_id", "ordinal", name="uq_citation_source_records_batch_ordinal"
        ),
        ForeignKeyConstraint(
            ["import_batch_id", "organization_id", "review_id"],
            [
                "citation_import_batches.id",
                "citation_import_batches.organization_id",
                "citation_import_batches.review_id",
            ],
            name="fk_citation_source_records_batch_tenant_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_citation_source_records_article_tenant_review",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    import_batch_id: Mapped[UUID] = mapped_column()
    article_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    ordinal: Mapped[int] = mapped_column(Integer)
    source_key: Mapped[str | None] = mapped_column(String(500))
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSON)


def _batch_to_domain(record: CitationImportBatchRecord) -> CitationImportBatch:
    return CitationImportBatch(
        id=record.id,
        organization_id=record.organization_id,
        review_id=record.review_id,
        source_format=CitationFormat(record.source_format),
        source_name=record.source_name,
        content_hash=record.content_hash,
        record_count=record.record_count,
        imported_by_user_id=record.imported_by_user_id,
        imported_at=record.imported_at or datetime.now(UTC),
    )


def _article_to_domain(record: ArticleRecord) -> Article:
    return Article(
        id=record.id,
        organization_id=record.organization_id,
        review_id=record.review_id,
        title=record.title,
        abstract=record.abstract,
        publication_year=record.publication_year,
        doi=record.doi,
        pmid=record.pmid,
        authors=record.authors,
        journal=record.journal,
        created_at=record.created_at or datetime.now(UTC),
    )


def _source_to_domain(record: CitationSourceRecordRow) -> CitationSourceRecord:
    return CitationSourceRecord(
        id=record.id,
        import_batch_id=record.import_batch_id,
        article_id=record.article_id,
        organization_id=record.organization_id,
        review_id=record.review_id,
        ordinal=record.ordinal,
        source_key=record.source_key,
        raw_metadata=record.raw_metadata,
    )


class SqlAlchemyCitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_batch_by_hash(
        self,
        organization_id: UUID,
        review_id: UUID,
        source_format: CitationFormat,
        content_hash: str,
    ) -> CitationImportBatch | None:
        query = select(CitationImportBatchRecord).where(
            CitationImportBatchRecord.organization_id == organization_id,
            CitationImportBatchRecord.review_id == review_id,
            CitationImportBatchRecord.source_format == source_format.value,
            CitationImportBatchRecord.content_hash == content_hash,
        )
        record = (await self._session.execute(query)).scalar_one_or_none()
        return _batch_to_domain(record) if record is not None else None

    async def create_import(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        source_format: CitationFormat,
        source_name: str,
        source_content: str,
        content_hash: str,
        records: list[ParsedCitation],
        imported_by_user_id: UUID,
    ) -> tuple[CitationImportBatch, list[tuple[Article, CitationSourceRecord]]]:
        batch = CitationImportBatchRecord(
            organization_id=organization_id,
            review_id=review_id,
            source_format=source_format.value,
            source_name=source_name,
            source_content=source_content,
            content_hash=content_hash,
            record_count=len(records),
            imported_by_user_id=imported_by_user_id,
        )
        self._session.add(batch)
        await self._session.flush()
        created: list[tuple[Article, CitationSourceRecord]] = []
        for ordinal, citation in enumerate(records, start=1):
            article = ArticleRecord(
                organization_id=organization_id,
                review_id=review_id,
                title=citation.title,
                abstract=citation.abstract,
                publication_year=citation.publication_year,
                doi=citation.doi,
                pmid=citation.pmid,
                authors=citation.authors,
                journal=citation.journal,
            )
            self._session.add(article)
            await self._session.flush()
            source = CitationSourceRecordRow(
                import_batch_id=batch.id,
                article_id=article.id,
                organization_id=organization_id,
                review_id=review_id,
                ordinal=ordinal,
                source_key=citation.source_key,
                raw_metadata=citation.raw_metadata,
            )
            self._session.add(source)
            await self._session.flush()
            created.append((_article_to_domain(article), _source_to_domain(source)))
        await self._session.refresh(batch)
        return _batch_to_domain(batch), created

    async def get_batch(self, organization_id: UUID, batch_id: UUID) -> CitationImportBatch | None:
        query = select(CitationImportBatchRecord).where(
            CitationImportBatchRecord.organization_id == organization_id,
            CitationImportBatchRecord.id == batch_id,
        )
        record = (await self._session.execute(query)).scalar_one_or_none()
        return _batch_to_domain(record) if record is not None else None

    async def list_articles(self, organization_id: UUID, review_id: UUID) -> list[Article]:
        query = (
            select(ArticleRecord)
            .where(
                ArticleRecord.organization_id == organization_id,
                ArticleRecord.review_id == review_id,
            )
            .order_by(ArticleRecord.created_at, ArticleRecord.id)
        )
        return [_article_to_domain(row) for row in await self._session.scalars(query)]

    async def get_article(
        self, organization_id: UUID, review_id: UUID, article_id: UUID
    ) -> Article | None:
        query = select(ArticleRecord).where(
            ArticleRecord.organization_id == organization_id,
            ArticleRecord.review_id == review_id,
            ArticleRecord.id == article_id,
        )
        row = (await self._session.execute(query)).scalar_one_or_none()
        return _article_to_domain(row) if row is not None else None
