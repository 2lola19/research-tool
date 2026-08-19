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
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.search.execution_domain import (
    IdentificationSource,
    IdentificationSourceClassification,
    SearchExecution,
    SearchExecutionArtifact,
    SearchExecutionMethod,
    SearchExecutionStatus,
)
from backend.app.search.execution_persistence import SqlAlchemySearchExecutionRepository
from backend.app.search.execution_service import MAX_RAW_ARTIFACT_BYTES, SearchExecutionService
from backend.app.search.persistence import SqlAlchemySearchRepository
from backend.app.search.provider_domain import (
    ProviderFailureClass,
    SearchProviderAttempt,
    SearchProviderCapability,
)
from backend.app.search.provider_persistence import SqlAlchemySearchProviderAttemptRepository
from backend.app.search.provider_service import (
    ProviderExecutionOutcome,
    SearchProviderExecutionService,
)

router = APIRouter(prefix="/search-executions", tags=["search executions"])


class IdentificationSourceRequest(BaseModel):
    review_id: UUID
    source_key: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=300)
    classification: IdentificationSourceClassification
    provider_name: str = Field(min_length=1, max_length=200)
    platform_name: str | None = Field(default=None, max_length=200)


class IdentificationSourceResponse(BaseModel):
    id: UUID
    review_id: UUID
    source_key: str
    display_name: str
    classification: IdentificationSourceClassification
    provider_name: str
    platform_name: str | None
    created_at: datetime

    @classmethod
    def from_domain(cls, item: IdentificationSource) -> IdentificationSourceResponse:
        return cls(
            id=item.id,
            review_id=item.review_id,
            source_key=item.source_key,
            display_name=item.display_name,
            classification=item.classification,
            provider_name=item.provider_name,
            platform_name=item.platform_name,
            created_at=item.created_at,
        )


class SearchExecutionRequest(BaseModel):
    review_id: UUID
    source_id: UUID
    search_strategy_version_id: UUID | None = None
    search_translation_id: UUID | None = None
    supersedes_execution_id: UUID | None = None
    method: SearchExecutionMethod
    exact_query: str | None = Field(default=None, max_length=100_000)
    filters: dict[str, str] = Field(default_factory=dict)
    executed_at: datetime
    software_version: str | None = Field(default=None, max_length=120)
    status: SearchExecutionStatus = SearchExecutionStatus.PLANNED
    provider_result_count: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=10_000)


class SearchExecutionEventRequest(BaseModel):
    review_id: UUID
    status: SearchExecutionStatus
    provider_result_count: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=10_000)


class LinkImportRequest(BaseModel):
    review_id: UUID
    import_batch_id: UUID


class ProviderExecutionRequest(BaseModel):
    review_id: UUID
    provider_key: str = Field(min_length=1, max_length=80)
    max_pages: int | None = Field(default=None, ge=1, le=100)
    page_size: int | None = Field(default=None, ge=1, le=1000)


class SearchExecutionEventResponse(BaseModel):
    sequence: int
    status: SearchExecutionStatus
    provider_result_count: int | None
    note: str | None
    occurred_at: datetime


class SearchExecutionResponse(BaseModel):
    id: UUID
    review_id: UUID
    source: IdentificationSourceResponse
    search_strategy_version_id: UUID | None
    search_translation_id: UUID | None
    supersedes_execution_id: UUID | None
    method: SearchExecutionMethod
    exact_query: str | None
    filters: dict[str, str]
    executed_at: datetime
    software_version: str | None
    status: SearchExecutionStatus
    provider_result_count: int | None
    imported_record_count: int
    created_at: datetime
    events: list[SearchExecutionEventResponse]

    @classmethod
    def from_domain(cls, item: SearchExecution) -> SearchExecutionResponse:
        return cls(
            id=item.id,
            review_id=item.review_id,
            source=IdentificationSourceResponse.from_domain(item.source),
            search_strategy_version_id=item.search_strategy_version_id,
            search_translation_id=item.search_translation_id,
            supersedes_execution_id=item.supersedes_execution_id,
            method=item.method,
            exact_query=item.exact_query,
            filters=item.filters,
            executed_at=item.executed_at,
            software_version=item.software_version,
            status=item.current_event.status,
            provider_result_count=item.current_event.provider_result_count,
            imported_record_count=item.imported_record_count,
            created_at=item.created_at,
            events=[
                SearchExecutionEventResponse(
                    sequence=event.sequence,
                    status=event.status,
                    provider_result_count=event.provider_result_count,
                    note=event.note,
                    occurred_at=event.occurred_at,
                )
                for event in item.events
            ],
        )


class ImportLinkResponse(BaseModel):
    linked_record_count: int


class SearchExecutionArtifactResponse(BaseModel):
    id: UUID
    search_execution_id: UUID
    original_filename: str
    media_type: str
    byte_size: int
    sha256: str
    created_at: datetime

    @classmethod
    def from_domain(cls, item: SearchExecutionArtifact) -> SearchExecutionArtifactResponse:
        return cls(
            id=item.id,
            search_execution_id=item.search_execution_id,
            original_filename=item.original_filename,
            media_type=item.media_type,
            byte_size=item.byte_size,
            sha256=item.sha256,
            created_at=item.created_at,
        )


class SearchProviderCapabilityResponse(BaseModel):
    key: str
    display_name: str
    version: str
    supports_pagination: bool
    max_page_size: int
    requires_api_key: bool

    @classmethod
    def from_domain(cls, item: SearchProviderCapability) -> SearchProviderCapabilityResponse:
        return cls(
            key=item.key,
            display_name=item.display_name,
            version=item.version,
            supports_pagination=item.supports_pagination,
            max_page_size=item.max_page_size,
            requires_api_key=item.requires_api_key,
        )


class SearchProviderAttemptResponse(BaseModel):
    id: UUID
    search_execution_id: UUID
    provider_key: str
    provider_version: str
    page_number: int
    attempt_number: int
    request_fingerprint: str
    started_at: datetime
    completed_at: datetime
    http_status: int | None
    failure_class: ProviderFailureClass | None
    response_byte_size: int
    response_sha256: str | None
    note: str | None

    @classmethod
    def from_domain(cls, item: SearchProviderAttempt) -> SearchProviderAttemptResponse:
        return cls(
            id=item.id,
            search_execution_id=item.search_execution_id,
            provider_key=item.provider_key,
            provider_version=item.provider_version,
            page_number=item.page_number,
            attempt_number=item.attempt_number,
            request_fingerprint=item.request_fingerprint,
            started_at=item.started_at,
            completed_at=item.completed_at,
            http_status=item.http_status,
            failure_class=item.failure_class,
            response_byte_size=item.response_byte_size,
            response_sha256=item.response_sha256,
            note=item.note,
        )


class ProviderExecutionResponse(BaseModel):
    execution: SearchExecutionResponse
    provider_key: str
    provider_version: str
    artifact_id: UUID | None
    import_batch_id: UUID | None
    normalized_record_count: int
    attempt_count: int
    failure_class: ProviderFailureClass | None

    @classmethod
    def from_domain(cls, outcome: ProviderExecutionOutcome) -> ProviderExecutionResponse:
        return cls(
            execution=SearchExecutionResponse.from_domain(outcome.execution),
            provider_key=outcome.provider_key,
            provider_version=outcome.provider_version,
            artifact_id=outcome.artifact.id if outcome.artifact else None,
            import_batch_id=outcome.import_batch.id if outcome.import_batch else None,
            normalized_record_count=outcome.execution.imported_record_count,
            attempt_count=len(outcome.attempts),
            failure_class=outcome.failure_class,
        )


def _service(
    session: DbSessionDependency, storage: ObjectStorageDependency
) -> SearchExecutionService:
    return SearchExecutionService(
        SqlAlchemySearchExecutionRepository(session),
        SqlAlchemySearchRepository(session),
        SqlAlchemyCitationRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyProvenanceRepository(session),
        storage,
    )


def _provider_service(
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    settings: SettingsDependency,
) -> SearchProviderExecutionService:
    execution_repository = SqlAlchemySearchExecutionRepository(session)
    return SearchProviderExecutionService(
        _service(session, storage),
        execution_repository,
        SqlAlchemySearchProviderAttemptRepository(session),
        SqlAlchemyCitationRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyProvenanceRepository(session),
        storage,
        settings,
    )


@router.post("/sources", response_model=IdentificationSourceResponse, status_code=201)
async def create_identification_source(
    payload: IdentificationSourceRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
) -> IdentificationSourceResponse:
    source = await _service(session, storage).create_source(actor, **payload.model_dump())
    await session.commit()
    return IdentificationSourceResponse.from_domain(source)


@router.get("/providers", response_model=list[SearchProviderCapabilityResponse])
async def list_search_provider_capabilities(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    settings: SettingsDependency,
) -> list[SearchProviderCapabilityResponse]:
    del actor
    return [
        SearchProviderCapabilityResponse.from_domain(item)
        for item in _provider_service(session, storage, settings).capabilities()
    ]


@router.get("/reviews/{review_id}/sources", response_model=list[IdentificationSourceResponse])
async def list_identification_sources(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    review_id: Annotated[UUID, Path()],
) -> list[IdentificationSourceResponse]:
    items = await _service(session, storage).list_sources(actor, review_id=review_id)
    return [IdentificationSourceResponse.from_domain(item) for item in items]


@router.post("", response_model=SearchExecutionResponse, status_code=status.HTTP_201_CREATED)
async def create_search_execution(
    payload: SearchExecutionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
) -> SearchExecutionResponse:
    execution = await _service(session, storage).create_execution(
        actor,
        review_id=payload.review_id,
        source_id=payload.source_id,
        strategy_version_id=payload.search_strategy_version_id,
        translation_id=payload.search_translation_id,
        supersedes_execution_id=payload.supersedes_execution_id,
        method=payload.method,
        exact_query=payload.exact_query,
        filters=payload.filters,
        executed_at=payload.executed_at,
        software_version=payload.software_version,
        initial_status=payload.status,
        provider_result_count=payload.provider_result_count,
        note=payload.note,
    )
    await session.commit()
    return SearchExecutionResponse.from_domain(execution)


@router.get("/reviews/{review_id}", response_model=list[SearchExecutionResponse])
async def list_search_executions(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    review_id: Annotated[UUID, Path()],
) -> list[SearchExecutionResponse]:
    items = await _service(session, storage).list_executions(actor, review_id=review_id)
    return [SearchExecutionResponse.from_domain(item) for item in items]


@router.get("/{execution_id}", response_model=SearchExecutionResponse)
async def get_search_execution(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    execution_id: Annotated[UUID, Path()],
    review_id: UUID,
) -> SearchExecutionResponse:
    item = await _service(session, storage).get_execution(
        actor, review_id=review_id, execution_id=execution_id
    )
    return SearchExecutionResponse.from_domain(item)


@router.post("/{execution_id}/events", response_model=SearchExecutionResponse)
async def transition_search_execution(
    payload: SearchExecutionEventRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    execution_id: Annotated[UUID, Path()],
) -> SearchExecutionResponse:
    item = await _service(session, storage).transition(
        actor, execution_id=execution_id, **payload.model_dump()
    )
    await session.commit()
    return SearchExecutionResponse.from_domain(item)


@router.post("/{execution_id}/imports", response_model=ImportLinkResponse)
async def link_search_import(
    payload: LinkImportRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    execution_id: Annotated[UUID, Path()],
) -> ImportLinkResponse:
    links = await _service(session, storage).link_import(
        actor, execution_id=execution_id, **payload.model_dump()
    )
    await session.commit()
    return ImportLinkResponse(linked_record_count=len(links))


@router.post("/{execution_id}/provider-runs", response_model=ProviderExecutionResponse)
async def execute_search_provider(
    payload: ProviderExecutionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    settings: SettingsDependency,
    execution_id: Annotated[UUID, Path()],
) -> ProviderExecutionResponse:
    outcome = await _provider_service(session, storage, settings).execute(
        actor,
        review_id=payload.review_id,
        execution_id=execution_id,
        provider_key=payload.provider_key,
        max_pages=payload.max_pages,
        page_size=payload.page_size,
    )
    await session.commit()
    return ProviderExecutionResponse.from_domain(outcome)


@router.get(
    "/{execution_id}/provider-attempts",
    response_model=list[SearchProviderAttemptResponse],
)
async def list_search_provider_attempts(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    settings: SettingsDependency,
    execution_id: Annotated[UUID, Path()],
    review_id: UUID,
) -> list[SearchProviderAttemptResponse]:
    attempts = await _provider_service(session, storage, settings).list_attempts(
        actor, review_id=review_id, execution_id=execution_id
    )
    return [SearchProviderAttemptResponse.from_domain(item) for item in attempts]


async def _read_artifact(request: Request) -> bytes:
    content_length = request.headers.get("content-length")
    try:
        declared_length = int(content_length) if content_length is not None else None
    except ValueError as exc:
        from backend.app.core.errors import ConflictError

        raise ConflictError("content length is invalid") from exc
    if declared_length is not None and declared_length > MAX_RAW_ARTIFACT_BYTES:
        from backend.app.core.errors import ConflictError

        raise ConflictError("raw search artifact exceeds the size limit")
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_RAW_ARTIFACT_BYTES:
            from backend.app.core.errors import ConflictError

            raise ConflictError("raw search artifact exceeds the size limit")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/{execution_id}/artifacts",
    response_model=SearchExecutionArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_search_execution_artifact(
    request: Request,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    execution_id: Annotated[UUID, Path()],
    review_id: UUID,
) -> SearchExecutionArtifactResponse:
    item = await _service(session, storage).upload_artifact(
        actor,
        review_id=review_id,
        execution_id=execution_id,
        filename=request.headers.get("X-Original-Filename", "search-results.raw"),
        media_type=request.headers.get("content-type", "application/octet-stream"),
        content=await _read_artifact(request),
    )
    await session.commit()
    return SearchExecutionArtifactResponse.from_domain(item)


@router.get("/{execution_id}/artifacts", response_model=list[SearchExecutionArtifactResponse])
async def list_search_execution_artifacts(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    execution_id: Annotated[UUID, Path()],
    review_id: UUID,
) -> list[SearchExecutionArtifactResponse]:
    items = await _service(session, storage).list_artifacts(
        actor, review_id=review_id, execution_id=execution_id
    )
    return [SearchExecutionArtifactResponse.from_domain(item) for item in items]


@router.get("/artifacts/{artifact_id}/content")
async def get_search_execution_artifact_content(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    storage: ObjectStorageDependency,
    artifact_id: Annotated[UUID, Path()],
    review_id: UUID,
) -> Response:
    artifact, content = await _service(session, storage).get_artifact_content(
        actor, review_id=review_id, artifact_id=artifact_id
    )
    safe_name = artifact.original_filename.replace('"', "")
    return Response(
        content=content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "X-Content-SHA256": artifact.sha256,
        },
    )
