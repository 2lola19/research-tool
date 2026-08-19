from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Request, Response, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import (
    ActorContextDependency,
    DbSessionDependency,
    ObjectStorageDependency,
    SettingsDependency,
)
from backend.app.citations.persistence import SqlAlchemyCitationRepository
from backend.app.documents.domain import (
    CriterionDecision,
    Document,
    DocumentEvidenceLocation,
    DocumentProcessingRun,
    DocumentRetrievalMethod,
    DocumentStatus,
    DocumentWarning,
    DocumentWarningKind,
    FullTextDecision,
    FullTextScreening,
)
from backend.app.documents.parsers import FixtureDocumentParser
from backend.app.documents.persistence import SqlAlchemyDocumentRepository
from backend.app.documents.service import DocumentService
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.protocols.persistence import SqlAlchemyProtocolRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    id: UUID
    review_id: UUID
    article_id: UUID
    status: DocumentStatus
    retrieval_method: str
    source_name: str
    source_identifier: str | None
    source_url: str | None
    license: str | None
    access_classification: str | None
    original_filename: str | None
    media_type: str | None
    file_size: int | None
    sha256: str | None
    retrieved_at: datetime | None

    @classmethod
    def from_domain(cls, item: Document) -> DocumentResponse:
        return cls(
            id=item.id,
            review_id=item.review_id,
            article_id=item.article_id,
            status=item.status,
            retrieval_method=item.retrieval_method.value,
            source_name=item.source_name,
            source_identifier=item.source_identifier,
            source_url=item.source_url,
            license=item.license,
            access_classification=item.access_classification,
            original_filename=item.original_filename,
            media_type=item.media_type,
            file_size=item.file_size,
            sha256=item.sha256,
            retrieved_at=item.retrieved_at,
        )


class EvidenceLocationRequest(BaseModel):
    block_id: UUID | None = None
    page_number: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, max_length=500)
    source_text: str | None = Field(default=None, max_length=20_000)
    table_id: str | None = Field(default=None, max_length=160)
    figure_id: str | None = Field(default=None, max_length=160)
    coordinates: dict[str, float] | None = None


class RetrievalRecordRequest(BaseModel):
    status: DocumentStatus
    retrieval_method: DocumentRetrievalMethod
    source_name: str = Field(min_length=1, max_length=300)
    source_identifier: str | None = Field(default=None, max_length=500)
    source_url: str | None = Field(default=None, max_length=2000)
    license: str | None = Field(default=None, max_length=300)
    access_classification: str | None = Field(default=None, max_length=80)


class EvidenceLocationResponse(BaseModel):
    id: UUID
    document_id: UUID
    block_id: UUID | None
    page_number: int | None
    section: str | None
    source_text: str | None

    @classmethod
    def from_domain(cls, item: DocumentEvidenceLocation) -> EvidenceLocationResponse:
        return cls(
            id=item.id,
            document_id=item.document_id,
            block_id=item.block_id,
            page_number=item.page_number,
            section=item.section,
            source_text=item.source_text,
        )


class WarningRequest(BaseModel):
    kind: DocumentWarningKind
    message: str = Field(min_length=1, max_length=4000)


class WarningResponse(BaseModel):
    id: UUID
    document_id: UUID
    kind: DocumentWarningKind
    message: str

    @classmethod
    def from_domain(cls, item: DocumentWarning) -> WarningResponse:
        return cls(id=item.id, document_id=item.document_id, kind=item.kind, message=item.message)


class CriterionJudgmentRequest(BaseModel):
    criterion_key: str = Field(min_length=1, max_length=200)
    decision: CriterionDecision
    reason: str | None = Field(default=None, max_length=4000)
    evidence_location_id: UUID | None = None
    evidence_text: str | None = Field(default=None, max_length=20_000)


class FullTextScreeningRequest(BaseModel):
    protocol_version_id: UUID
    judgments: list[CriterionJudgmentRequest] = Field(min_length=1, max_length=200)
    primary_reason: str | None = Field(default=None, max_length=4000)


class FullTextScreeningResponse(BaseModel):
    id: UUID
    document_id: UUID
    protocol_version_id: UUID
    final_decision: FullTextDecision
    primary_reason: str | None

    @classmethod
    def from_domain(cls, item: FullTextScreening) -> FullTextScreeningResponse:
        return cls(
            id=item.id,
            document_id=item.document_id,
            protocol_version_id=item.protocol_version_id,
            final_decision=item.final_decision,
            primary_reason=item.primary_reason,
        )


class ProcessingRunResponse(BaseModel):
    id: UUID
    document_id: UUID
    parser_name: str
    parser_version: str
    status: str
    failure_class: str | None
    error_message: str | None
    content_sha256: str | None
    content_size: int | None
    chunk_manifest_hash: str | None
    chunk_manifest: list[dict[str, object]] | None
    block_count: int
    text_byte_size: int

    @classmethod
    def from_domain(cls, item: DocumentProcessingRun) -> ProcessingRunResponse:
        return cls(
            id=item.id,
            document_id=item.document_id,
            parser_name=item.parser_name,
            parser_version=item.parser_version,
            status=item.status.value,
            failure_class=item.failure_class.value if item.failure_class else None,
            error_message=item.error_message,
            content_sha256=item.content_sha256,
            content_size=item.content_size,
            chunk_manifest_hash=item.chunk_manifest_hash,
            chunk_manifest=item.chunk_manifest,
            block_count=item.block_count,
            text_byte_size=item.text_byte_size,
        )


class StorageReconciliationResponse(BaseModel):
    review_id: UUID
    document_count: int
    expected_object_count: int
    actual_object_count: int
    missing_document_ids: list[str]
    orphan_object_count: int
    status: str


def _service(
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    settings: SettingsDependency,
) -> DocumentService:
    identity = SqlAlchemyIdentityRepository(session)
    return DocumentService(
        SqlAlchemyDocumentRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyCitationRepository(session),
        SqlAlchemyProtocolRepository(session),
        identity,
        SqlAlchemyProvenanceRepository(session),
        storage,
        settings,
    )


async def _read_upload(request: Request, limit: int) -> bytes:
    content_length = request.headers.get("content-length")
    try:
        declared_length = int(content_length) if content_length is not None else None
    except ValueError as exc:
        from backend.app.core.errors import ConflictError

        raise ConflictError("content length is invalid") from exc
    if declared_length is not None and declared_length > limit:
        from backend.app.core.errors import ConflictError

        raise ConflictError("document exceeds the configured size limit")
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            from backend.app.core.errors import ConflictError

            raise ConflictError("document exceeds the configured size limit")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/reviews/{review_id}/articles/{article_id}/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    request: Request,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    settings: SettingsDependency,
    review_id: Annotated[UUID, Path()],
    article_id: Annotated[UUID, Path()],
) -> DocumentResponse:
    document = await _service(session, storage, settings).upload_pdf(
        actor,
        review_id=review_id,
        article_id=article_id,
        filename=request.headers.get("X-Original-Filename", "document.pdf"),
        media_type=request.headers.get("content-type", ""),
        content=await _read_upload(request, settings.max_document_file_size_bytes),
    )
    await session.commit()
    return DocumentResponse.from_domain(document)


@router.post(
    "/reviews/{review_id}/articles/{article_id}/retrieval-record",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_retrieval_record(
    payload: RetrievalRecordRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    settings: SettingsDependency,
    review_id: Annotated[UUID, Path()],
    article_id: Annotated[UUID, Path()],
) -> DocumentResponse:
    document = await _service(session, storage, settings).create_retrieval_record(
        actor, review_id=review_id, article_id=article_id, **payload.model_dump()
    )
    await session.commit()
    return DocumentResponse.from_domain(document)


@router.get(
    "/reviews/{review_id}/storage-reconciliation",
    response_model=StorageReconciliationResponse,
)
async def reconcile_document_storage(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    settings: SettingsDependency,
    review_id: Annotated[UUID, Path()],
) -> StorageReconciliationResponse:
    report = await _service(session, storage, settings).reconcile_storage(
        actor, review_id=review_id
    )
    return StorageReconciliationResponse.model_validate(report)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    settings: SettingsDependency,
    document_id: Annotated[UUID, Path()],
) -> DocumentResponse:
    return DocumentResponse.from_domain(
        await _service(session, storage, settings).get(actor, document_id)
    )


@router.get("/{document_id}/content")
async def get_document_content(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    settings: SettingsDependency,
    document_id: Annotated[UUID, Path()],
) -> Response:
    service = _service(session, storage, settings)
    document, content = await service.content(actor, document_id)
    return Response(content=content, media_type=document.media_type or "application/pdf")


@router.post("/{document_id}/process", response_model=DocumentResponse)
async def process_document(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    settings: SettingsDependency,
    document_id: Annotated[UUID, Path()],
) -> DocumentResponse:
    document = await _service(session, storage, settings).process(
        actor, document_id=document_id, parser=FixtureDocumentParser()
    )
    await session.commit()
    return DocumentResponse.from_domain(document)


@router.get("/{document_id}/processing-runs", response_model=list[ProcessingRunResponse])
async def list_document_processing_runs(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    settings: SettingsDependency,
    document_id: Annotated[UUID, Path()],
) -> list[ProcessingRunResponse]:
    runs = await _service(session, storage, settings).list_processing_runs(
        actor, document_id=document_id
    )
    return [ProcessingRunResponse.from_domain(item) for item in runs]


@router.post("/{document_id}/evidence-locations", response_model=EvidenceLocationResponse)
async def create_evidence_location(
    payload: EvidenceLocationRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    settings: SettingsDependency,
    document_id: Annotated[UUID, Path()],
) -> EvidenceLocationResponse:
    location = await _service(session, storage, settings).create_evidence_location(
        actor, document_id=document_id, **payload.model_dump()
    )
    await session.commit()
    return EvidenceLocationResponse.from_domain(location)


@router.post("/{document_id}/warnings", response_model=WarningResponse)
async def add_document_warning(
    payload: WarningRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    settings: SettingsDependency,
    document_id: Annotated[UUID, Path()],
) -> WarningResponse:
    warning = await _service(session, storage, settings).add_warning(
        actor, document_id=document_id, kind=payload.kind, message=payload.message
    )
    await session.commit()
    return WarningResponse.from_domain(warning)


@router.get("/{document_id}/warnings", response_model=list[WarningResponse])
async def list_document_warnings(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    settings: SettingsDependency,
    document_id: Annotated[UUID, Path()],
) -> list[WarningResponse]:
    warnings = await _service(session, storage, settings).list_warnings(
        actor, document_id=document_id
    )
    return [WarningResponse.from_domain(item) for item in warnings]


@router.post("/{document_id}/full-text-screening", response_model=FullTextScreeningResponse)
async def screen_full_text(
    payload: FullTextScreeningRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    settings: SettingsDependency,
    document_id: Annotated[UUID, Path()],
) -> FullTextScreeningResponse:
    screening = await _service(session, storage, settings).screen_full_text(
        actor,
        document_id=document_id,
        protocol_version_id=payload.protocol_version_id,
        judgments=[item.model_dump() for item in payload.judgments],
        primary_reason=payload.primary_reason,
    )
    await session.commit()
    return FullTextScreeningResponse.from_domain(screening)
