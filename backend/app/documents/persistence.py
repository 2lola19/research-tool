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
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.db.base import Base
from backend.app.documents.domain import (
    CanonicalDocument,
    CanonicalDocumentBlock,
    CriterionDecision,
    Document,
    DocumentBlock,
    DocumentBlockType,
    DocumentEvidenceLocation,
    DocumentProcessingRun,
    DocumentRetrievalMethod,
    DocumentStatus,
    DocumentWarning,
    DocumentWarningKind,
    FullTextCriterionJudgment,
    FullTextDecision,
    FullTextScreening,
    ProcessingRunStatus,
)


class DocumentRecord(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_documents_id_tenant"),
        UniqueConstraint(
            "organization_id",
            "review_id",
            "article_id",
            "sha256",
            name="uq_documents_article_checksum",
        ),
        CheckConstraint(
            "status IN ('NOT_REQUESTED', 'RETRIEVAL_PENDING', 'RETRIEVED', 'OPEN_ACCESS', "
            "'USER_UPLOADED', 'EXTERNAL_LINK_ONLY', 'PAYWALLED', 'NOT_FOUND', 'INVALID_FILE', "
            "'PROCESSING', 'PROCESSED', 'PROCESSING_FAILED', 'RETRACTION_WARNING', "
            "'SUPPLEMENT_AVAILABLE')",
            name="ck_documents_status",
        ),
        CheckConstraint(
            "retrieval_method IN ("
            "'PUBLISHER', 'REPOSITORY', 'USER_UPLOAD', 'EXTERNAL_LINK', 'MANUAL')",
            name="ck_documents_retrieval_method",
        ),
        CheckConstraint("file_size IS NULL OR file_size >= 0", name="ck_documents_file_size"),
        CheckConstraint("sha256 IS NULL OR length(sha256) = 64", name="ck_documents_sha256_length"),
        ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_documents_article_tenant_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "uploaded_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_documents_uploader_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    article_id: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(30))
    retrieval_method: Mapped[str] = mapped_column(String(30))
    source_name: Mapped[str] = mapped_column(String(300))
    source_identifier: Mapped[str | None] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(2000))
    license: Mapped[str | None] = mapped_column(String(300))
    access_classification: Mapped[str | None] = mapped_column(String(80))
    storage_key: Mapped[str | None] = mapped_column(String(500))
    original_filename: Mapped[str | None] = mapped_column(String(500))
    media_type: Mapped[str | None] = mapped_column(String(120))
    file_size: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    uploaded_by_user_id: Mapped[UUID | None] = mapped_column()
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DocumentProcessingRunRecord(Base):
    __tablename__ = "document_processing_runs"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_document_runs_id_tenant"),
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')",
            name="ck_document_runs_status",
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_document_runs_document_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "requested_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_document_runs_requester_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    parser_name: Mapped[str] = mapped_column(String(120))
    parser_version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20))
    error_message: Mapped[str | None] = mapped_column(Text)
    requested_by_user_id: Mapped[UUID] = mapped_column()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentBlockRecord(Base):
    __tablename__ = "document_blocks"
    __table_args__ = (
        UniqueConstraint("document_id", "block_id", name="uq_document_blocks_document_block"),
        UniqueConstraint(
            "id", "document_id", "organization_id", "review_id", name="uq_document_blocks_id_tenant"
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_document_blocks_document_tenant",
            ondelete="CASCADE",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    block_id: Mapped[str] = mapped_column(String(160))
    block_type: Mapped[str] = mapped_column(String(30))
    block_order: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_path: Mapped[list[str]] = mapped_column(JSON)
    text: Mapped[str] = mapped_column(Text)
    table_id: Mapped[str | None] = mapped_column(String(160))
    figure_id: Mapped[str | None] = mapped_column(String(160))
    coordinates: Mapped[dict[str, float] | None] = mapped_column(JSON)


class DocumentEvidenceLocationRecord(Base):
    __tablename__ = "document_evidence_locations"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_document_locations_id_tenant"
        ),
        UniqueConstraint(
            "id",
            "document_id",
            "organization_id",
            "review_id",
            name="uq_document_locations_id_document_tenant",
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_document_locations_document_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
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
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    block_id: Mapped[UUID | None] = mapped_column()
    page_number: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(500))
    source_text: Mapped[str | None] = mapped_column(Text)
    table_id: Mapped[str | None] = mapped_column(String(160))
    figure_id: Mapped[str | None] = mapped_column(String(160))
    coordinates: Mapped[dict[str, float] | None] = mapped_column(JSON)


class DocumentWarningRecord(Base):
    __tablename__ = "document_warnings"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('RETRACTION', 'CORRECTION', 'EXPRESSION_OF_CONCERN', 'INVALID_FULL_TEXT')",
            name="ck_document_warnings_kind",
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_document_warnings_document_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_document_warnings_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    kind: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FullTextScreeningRecord(Base):
    __tablename__ = "full_text_screenings"
    __table_args__ = (
        UniqueConstraint(
            "document_id", "protocol_version_id", name="uq_full_text_screenings_document_protocol"
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_full_text_screenings_id_tenant"
        ),
        CheckConstraint(
            "final_decision IN ('INCLUDE', 'EXCLUDE', 'MAYBE')",
            name="ck_full_text_screenings_decision",
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_full_text_screenings_document_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["protocol_version_id", "organization_id", "review_id"],
            [
                "protocol_versions.id",
                "protocol_versions.organization_id",
                "protocol_versions.review_id",
            ],
            name="fk_full_text_screenings_protocol_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "decided_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_full_text_screenings_decider_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    protocol_version_id: Mapped[UUID] = mapped_column()
    final_decision: Mapped[str] = mapped_column(String(20))
    primary_reason: Mapped[str | None] = mapped_column(Text)
    decided_by_user_id: Mapped[UUID] = mapped_column()
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FullTextCriterionJudgmentRecord(Base):
    __tablename__ = "full_text_criterion_judgments"
    __table_args__ = (
        UniqueConstraint(
            "screening_id", "criterion_key", name="uq_full_text_judgments_screening_criterion"
        ),
        CheckConstraint(
            "decision IN ('PASS', 'FAIL', 'UNCLEAR', 'NOT_APPLICABLE')",
            name="ck_full_text_judgments_decision",
        ),
        ForeignKeyConstraint(
            ["screening_id", "organization_id", "review_id"],
            [
                "full_text_screenings.id",
                "full_text_screenings.organization_id",
                "full_text_screenings.review_id",
            ],
            name="fk_full_text_judgments_screening_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
            ["organization_id", "decided_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_full_text_judgments_decider_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    screening_id: Mapped[UUID] = mapped_column()
    document_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    criterion_key: Mapped[str] = mapped_column(String(200))
    decision: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text)
    evidence_location_id: Mapped[UUID | None] = mapped_column()
    evidence_text: Mapped[str | None] = mapped_column(Text)
    decided_by_user_id: Mapped[UUID] = mapped_column()
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _document(row: DocumentRecord) -> Document:
    now = datetime.now(UTC)
    return Document(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        article_id=row.article_id,
        status=DocumentStatus(row.status),
        retrieval_method=DocumentRetrievalMethod(row.retrieval_method),
        source_name=row.source_name,
        source_identifier=row.source_identifier,
        source_url=row.source_url,
        license=row.license,
        access_classification=row.access_classification,
        storage_key=row.storage_key,
        original_filename=row.original_filename,
        media_type=row.media_type,
        file_size=row.file_size,
        sha256=row.sha256,
        uploaded_by_user_id=row.uploaded_by_user_id,
        retrieved_at=row.retrieved_at,
        created_at=row.created_at or now,
        updated_at=row.updated_at or now,
    )


def _run(row: DocumentProcessingRunRecord) -> DocumentProcessingRun:
    now = datetime.now(UTC)
    return DocumentProcessingRun(
        id=row.id,
        document_id=row.document_id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        parser_name=row.parser_name,
        parser_version=row.parser_version,
        status=ProcessingRunStatus(row.status),
        error_message=row.error_message,
        requested_by_user_id=row.requested_by_user_id,
        started_at=row.started_at,
        finished_at=row.finished_at,
        created_at=row.created_at or now,
    )


def _block(row: DocumentBlockRecord) -> DocumentBlock:
    return DocumentBlock(
        id=row.id,
        document_id=row.document_id,
        block_id=row.block_id,
        block_type=DocumentBlockType(row.block_type),
        block_order=row.block_order,
        page_number=row.page_number,
        section_path=row.section_path,
        text=row.text,
        table_id=row.table_id,
        figure_id=row.figure_id,
        coordinates=row.coordinates,
    )


def _location(row: DocumentEvidenceLocationRecord) -> DocumentEvidenceLocation:
    return DocumentEvidenceLocation(
        id=row.id,
        document_id=row.document_id,
        block_id=row.block_id,
        page_number=row.page_number,
        section=row.section,
        source_text=row.source_text,
        table_id=row.table_id,
        figure_id=row.figure_id,
        coordinates=row.coordinates,
    )


def _warning(row: DocumentWarningRecord) -> DocumentWarning:
    return DocumentWarning(
        id=row.id,
        document_id=row.document_id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        kind=DocumentWarningKind(row.kind),
        message=row.message,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at or datetime.now(UTC),
    )


def _screening(row: FullTextScreeningRecord) -> FullTextScreening:
    return FullTextScreening(
        id=row.id,
        document_id=row.document_id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        protocol_version_id=row.protocol_version_id,
        final_decision=FullTextDecision(row.final_decision),
        primary_reason=row.primary_reason,
        decided_by_user_id=row.decided_by_user_id,
        decided_at=row.decided_at or datetime.now(UTC),
    )


def _judgment(row: FullTextCriterionJudgmentRecord) -> FullTextCriterionJudgment:
    return FullTextCriterionJudgment(
        id=row.id,
        screening_id=row.screening_id,
        document_id=row.document_id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        criterion_key=row.criterion_key,
        decision=CriterionDecision(row.decision),
        reason=row.reason,
        evidence_location_id=row.evidence_location_id,
        evidence_text=row.evidence_text,
        decided_by_user_id=row.decided_by_user_id,
        decided_at=row.decided_at or datetime.now(UTC),
    )


class SqlAlchemyDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_document(self, **values: Any) -> Document:
        row = DocumentRecord(**values)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _document(row)

    async def get_document(self, organization_id: UUID, document_id: UUID) -> Document | None:
        row = (
            await self._session.execute(
                select(DocumentRecord).where(
                    DocumentRecord.organization_id == organization_id,
                    DocumentRecord.id == document_id,
                )
            )
        ).scalar_one_or_none()
        return _document(row) if row is not None else None

    async def get_document_for_article_checksum(
        self, organization_id: UUID, review_id: UUID, article_id: UUID, sha256: str
    ) -> Document | None:
        row = (
            await self._session.execute(
                select(DocumentRecord).where(
                    DocumentRecord.organization_id == organization_id,
                    DocumentRecord.review_id == review_id,
                    DocumentRecord.article_id == article_id,
                    DocumentRecord.sha256 == sha256,
                )
            )
        ).scalar_one_or_none()
        return _document(row) if row is not None else None

    async def update_document_status(
        self, organization_id: UUID, document_id: UUID, status: DocumentStatus
    ) -> Document:
        await self._session.execute(
            update(DocumentRecord)
            .where(
                DocumentRecord.organization_id == organization_id,
                DocumentRecord.id == document_id,
            )
            .values(status=status.value, updated_at=func.now())
        )
        document = await self.get_document(organization_id, document_id)
        if document is None:
            raise ResourceNotFoundError("document was not found")
        return document

    async def create_processing_run(
        self, *, document: Document, **values: Any
    ) -> DocumentProcessingRun:
        row = DocumentProcessingRunRecord(
            document_id=document.id,
            organization_id=document.organization_id,
            review_id=document.review_id,
            **values,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _run(row)

    async def finish_processing_run(
        self, *, organization_id: UUID, run_id: UUID, **values: Any
    ) -> DocumentProcessingRun:
        await self._session.execute(
            update(DocumentProcessingRunRecord)
            .where(
                DocumentProcessingRunRecord.organization_id == organization_id,
                DocumentProcessingRunRecord.id == run_id,
            )
            .values(**values)
        )
        row = (
            await self._session.execute(
                select(DocumentProcessingRunRecord).where(
                    DocumentProcessingRunRecord.organization_id == organization_id,
                    DocumentProcessingRunRecord.id == run_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise ResourceNotFoundError("document processing run was not found")
        return _run(row)

    async def replace_document_blocks(
        self, document: Document, canonical: CanonicalDocument
    ) -> list[DocumentBlock]:
        existing = (
            await self._session.scalars(
                select(DocumentBlockRecord).where(DocumentBlockRecord.document_id == document.id)
            )
        ).all()
        if existing:
            raise ConflictError("document already has a canonical processing result")
        canonical_blocks = list(canonical.blocks)
        if canonical.title:
            canonical_blocks.insert(
                0,
                CanonicalDocumentBlock(
                    block_id="title",
                    block_type=DocumentBlockType.TITLE,
                    block_order=0,
                    page_number=1,
                    section_path=[],
                    text=canonical.title,
                ),
            )
        rows = [
            DocumentBlockRecord(
                document_id=document.id,
                organization_id=document.organization_id,
                review_id=document.review_id,
                block_id=item.block_id,
                block_type=item.block_type.value,
                block_order=item.block_order,
                page_number=item.page_number,
                section_path=item.section_path,
                text=item.text,
                table_id=item.table_id,
                figure_id=item.figure_id,
                coordinates=item.coordinates,
            )
            for item in canonical_blocks
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return [_block(row) for row in rows]

    async def create_evidence_location(
        self, *, document: Document, **values: Any
    ) -> DocumentEvidenceLocation:
        row = DocumentEvidenceLocationRecord(
            document_id=document.id,
            organization_id=document.organization_id,
            review_id=document.review_id,
            **values,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _location(row)

    async def get_evidence_location(
        self, organization_id: UUID, document_id: UUID, location_id: UUID
    ) -> DocumentEvidenceLocation | None:
        row = (
            await self._session.execute(
                select(DocumentEvidenceLocationRecord).where(
                    DocumentEvidenceLocationRecord.organization_id == organization_id,
                    DocumentEvidenceLocationRecord.document_id == document_id,
                    DocumentEvidenceLocationRecord.id == location_id,
                )
            )
        ).scalar_one_or_none()
        return _location(row) if row is not None else None

    async def create_warning(self, *, document: Document, **values: Any) -> DocumentWarning:
        row = DocumentWarningRecord(
            document_id=document.id,
            organization_id=document.organization_id,
            review_id=document.review_id,
            **values,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _warning(row)

    async def list_warnings(
        self, organization_id: UUID, document_id: UUID
    ) -> list[DocumentWarning]:
        rows = await self._session.scalars(
            select(DocumentWarningRecord)
            .where(
                DocumentWarningRecord.organization_id == organization_id,
                DocumentWarningRecord.document_id == document_id,
            )
            .order_by(DocumentWarningRecord.created_at, DocumentWarningRecord.id)
        )
        return [_warning(row) for row in rows]

    async def create_full_text_screening(
        self, *, document: Document, **values: Any
    ) -> FullTextScreening:
        row = FullTextScreeningRecord(
            document_id=document.id,
            organization_id=document.organization_id,
            review_id=document.review_id,
            **values,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _screening(row)

    async def create_criterion_judgment(
        self, *, screening: FullTextScreening, **values: Any
    ) -> FullTextCriterionJudgment:
        row = FullTextCriterionJudgmentRecord(
            screening_id=screening.id,
            document_id=screening.document_id,
            organization_id=screening.organization_id,
            review_id=screening.review_id,
            **values,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _judgment(row)
