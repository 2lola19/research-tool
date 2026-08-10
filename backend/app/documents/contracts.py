from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from backend.app.documents.domain import (
    CanonicalDocument,
    CriterionDecision,
    Document,
    DocumentBlock,
    DocumentEvidenceLocation,
    DocumentProcessingRun,
    DocumentRetrievalMethod,
    DocumentStatus,
    DocumentWarning,
    DocumentWarningKind,
    FullTextCriterionJudgment,
    FullTextScreening,
    ProcessingRunStatus,
)


class DocumentRepository(Protocol):
    async def create_document(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        article_id: UUID,
        status: DocumentStatus,
        retrieval_method: DocumentRetrievalMethod,
        source_name: str,
        source_identifier: str | None,
        source_url: str | None,
        license: str | None,
        access_classification: str | None,
        storage_key: str | None,
        original_filename: str | None,
        media_type: str | None,
        file_size: int | None,
        sha256: str | None,
        uploaded_by_user_id: UUID | None,
    ) -> Document: ...

    async def get_document(self, organization_id: UUID, document_id: UUID) -> Document | None: ...

    async def get_document_for_article_checksum(
        self, organization_id: UUID, review_id: UUID, article_id: UUID, sha256: str
    ) -> Document | None: ...

    async def update_document_status(
        self, organization_id: UUID, document_id: UUID, status: DocumentStatus
    ) -> Document: ...

    async def create_processing_run(
        self,
        *,
        document: Document,
        parser_name: str,
        parser_version: str,
        status: ProcessingRunStatus,
        error_message: str | None,
        requested_by_user_id: UUID,
        started_at: datetime | None,
        finished_at: datetime | None,
    ) -> DocumentProcessingRun: ...

    async def finish_processing_run(
        self,
        *,
        organization_id: UUID,
        run_id: UUID,
        status: ProcessingRunStatus,
        error_message: str | None,
        finished_at: datetime | None,
    ) -> DocumentProcessingRun: ...

    async def replace_document_blocks(
        self, document: Document, canonical: CanonicalDocument
    ) -> list[DocumentBlock]: ...

    async def create_evidence_location(
        self,
        *,
        document: Document,
        block_id: UUID | None,
        page_number: int | None,
        section: str | None,
        source_text: str | None,
        table_id: str | None,
        figure_id: str | None,
        coordinates: dict[str, float] | None,
    ) -> DocumentEvidenceLocation: ...

    async def get_evidence_location(
        self, organization_id: UUID, document_id: UUID, location_id: UUID
    ) -> DocumentEvidenceLocation | None: ...

    async def create_warning(
        self,
        *,
        document: Document,
        kind: DocumentWarningKind,
        message: str,
        created_by_user_id: UUID,
    ) -> DocumentWarning: ...

    async def list_warnings(
        self, organization_id: UUID, document_id: UUID
    ) -> list[DocumentWarning]: ...

    async def create_full_text_screening(
        self,
        *,
        document: Document,
        protocol_version_id: UUID,
        final_decision: str,
        primary_reason: str | None,
        decided_by_user_id: UUID,
    ) -> FullTextScreening: ...

    async def create_criterion_judgment(
        self,
        *,
        screening: FullTextScreening,
        criterion_key: str,
        decision: CriterionDecision,
        reason: str | None,
        evidence_location_id: UUID | None,
        evidence_text: str | None,
        decided_by_user_id: UUID,
    ) -> FullTextCriterionJudgment: ...


class DocumentParser(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    def parse(self, content: bytes) -> CanonicalDocument: ...
