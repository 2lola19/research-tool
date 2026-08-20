from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from backend.app.malware.domain import MalwareScanErrorClass, MalwareScanOutcome


class DocumentStatus(StrEnum):
    NOT_REQUESTED = "NOT_REQUESTED"
    RETRIEVAL_PENDING = "RETRIEVAL_PENDING"
    RETRIEVED = "RETRIEVED"
    OPEN_ACCESS = "OPEN_ACCESS"
    USER_UPLOADED = "USER_UPLOADED"
    EXTERNAL_LINK_ONLY = "EXTERNAL_LINK_ONLY"
    PAYWALLED = "PAYWALLED"
    NOT_FOUND = "NOT_FOUND"
    INVALID_FILE = "INVALID_FILE"
    MALWARE_SCAN_PENDING = "MALWARE_SCAN_PENDING"
    MALWARE_CLEAN = "MALWARE_CLEAN"
    MALWARE_INFECTED = "MALWARE_INFECTED"
    MALWARE_SCAN_FAILED = "MALWARE_SCAN_FAILED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    RETRACTION_WARNING = "RETRACTION_WARNING"
    SUPPLEMENT_AVAILABLE = "SUPPLEMENT_AVAILABLE"


class DocumentRetrievalMethod(StrEnum):
    PUBLISHER = "PUBLISHER"
    REPOSITORY = "REPOSITORY"
    USER_UPLOAD = "USER_UPLOAD"
    EXTERNAL_LINK = "EXTERNAL_LINK"
    MANUAL = "MANUAL"


class ProcessingRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class ProcessingFailureClass(StrEnum):
    STORAGE_MISSING = "STORAGE_MISSING"
    STORAGE_INTEGRITY = "STORAGE_INTEGRITY"
    PARSER_INVALID = "PARSER_INVALID"
    PARSER_LIMIT = "PARSER_LIMIT"
    PARSER_TIMEOUT = "PARSER_TIMEOUT"
    UNEXPECTED = "UNEXPECTED"


class DocumentBlockType(StrEnum):
    TITLE = "TITLE"
    ABSTRACT = "ABSTRACT"
    SECTION = "SECTION"
    PARAGRAPH = "PARAGRAPH"
    TABLE = "TABLE"
    FIGURE_CAPTION = "FIGURE_CAPTION"
    REFERENCE = "REFERENCE"


class DocumentWarningKind(StrEnum):
    RETRACTION = "RETRACTION"
    CORRECTION = "CORRECTION"
    EXPRESSION_OF_CONCERN = "EXPRESSION_OF_CONCERN"
    INVALID_FULL_TEXT = "INVALID_FULL_TEXT"


class CriterionDecision(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCLEAR = "UNCLEAR"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FullTextDecision(StrEnum):
    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"
    MAYBE = "MAYBE"


@dataclass(frozen=True, slots=True)
class Document:
    id: UUID
    organization_id: UUID
    review_id: UUID
    article_id: UUID
    status: DocumentStatus
    retrieval_method: DocumentRetrievalMethod
    source_name: str
    source_identifier: str | None
    source_url: str | None
    license: str | None
    access_classification: str | None
    storage_key: str | None
    original_filename: str | None
    media_type: str | None
    file_size: int | None
    sha256: str | None
    uploaded_by_user_id: UUID | None
    retrieved_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class DocumentProcessingRun:
    id: UUID
    document_id: UUID
    organization_id: UUID
    review_id: UUID
    parser_name: str
    parser_version: str
    status: ProcessingRunStatus
    error_message: str | None
    requested_by_user_id: UUID
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    failure_class: ProcessingFailureClass | None = None
    content_sha256: str | None = None
    content_size: int | None = None
    chunk_manifest_hash: str | None = None
    chunk_manifest: list[dict[str, object]] | None = None
    block_count: int = 0
    text_byte_size: int = 0


@dataclass(frozen=True, slots=True)
class DocumentMalwareScanAttempt:
    id: UUID
    document_id: UUID
    organization_id: UUID
    review_id: UUID
    attempt_number: int
    provider_type: str
    scanner_version: str | None
    signature_database_version: str | None
    content_sha256: str
    content_size: int
    outcome: MalwareScanOutcome
    detection_name: str | None
    error_class: MalwareScanErrorClass | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DocumentBlock:
    id: UUID
    document_id: UUID
    block_id: str
    block_type: DocumentBlockType
    block_order: int
    page_number: int | None
    section_path: list[str]
    text: str
    table_id: str | None
    figure_id: str | None
    coordinates: dict[str, float] | None


@dataclass(frozen=True, slots=True)
class DocumentEvidenceLocation:
    id: UUID
    document_id: UUID
    block_id: UUID | None
    page_number: int | None
    section: str | None
    source_text: str | None
    table_id: str | None
    figure_id: str | None
    coordinates: dict[str, float] | None


@dataclass(frozen=True, slots=True)
class DocumentWarning:
    id: UUID
    document_id: UUID
    organization_id: UUID
    review_id: UUID
    kind: DocumentWarningKind
    message: str
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class FullTextScreening:
    id: UUID
    document_id: UUID
    organization_id: UUID
    review_id: UUID
    protocol_version_id: UUID
    final_decision: FullTextDecision
    primary_reason: str | None
    decided_by_user_id: UUID
    decided_at: datetime


@dataclass(frozen=True, slots=True)
class FullTextCriterionJudgment:
    id: UUID
    screening_id: UUID
    document_id: UUID
    organization_id: UUID
    review_id: UUID
    criterion_key: str
    decision: CriterionDecision
    reason: str | None
    evidence_location_id: UUID | None
    evidence_text: str | None
    decided_by_user_id: UUID
    decided_at: datetime


@dataclass(frozen=True, slots=True)
class CanonicalDocumentBlock:
    block_id: str
    block_type: DocumentBlockType
    block_order: int
    page_number: int | None
    section_path: list[str]
    text: str
    table_id: str | None = None
    figure_id: str | None = None
    coordinates: dict[str, float] | None = None


@dataclass(frozen=True, slots=True)
class CanonicalDocument:
    title: str | None
    abstract: str | None
    blocks: tuple[CanonicalDocumentBlock, ...]
