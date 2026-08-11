from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.extraction.domain import (
    ConflictResolution,
    ExtractionConflict,
    ExtractionRun,
    ExtractionRunStatus,
    ExtractionSchema,
    ExtractionSchemaVersion,
    ExtractionValue,
    MissingnessState,
)
from backend.app.extraction.manual_persistence import SqlAlchemyManualExtractionRepository
from backend.app.extraction.manual_service import ManualExtractionService
from backend.app.extraction.schema_persistence import SqlAlchemyExtractionSchemaRepository
from backend.app.extraction.schema_service import ExtractionSchemaService
from backend.app.extraction.verification_persistence import (
    SqlAlchemyExtractionVerificationRepository,
)
from backend.app.extraction.verification_service import ExtractionVerificationService
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository
from backend.app.studies.persistence import SqlAlchemyStudyRepository

router = APIRouter(prefix="/extraction", tags=["extraction"])


class SchemaRequest(BaseModel):
    review_id: UUID
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)


class SchemaVersionRequest(BaseModel):
    review_id: UUID
    schema_id: UUID
    fields: list[dict[str, Any]] = Field(min_length=1, max_length=200)


class SchemaResponse(BaseModel):
    id: UUID
    review_id: UUID
    name: str
    description: str | None

    @classmethod
    def from_domain(cls, item: ExtractionSchema) -> SchemaResponse:
        return cls(
            id=item.id, review_id=item.review_id, name=item.name, description=item.description
        )


class SchemaVersionResponse(BaseModel):
    id: UUID
    schema_id: UUID
    review_id: UUID
    version: int
    content_hash: str
    fields: list[dict[str, Any]]

    @classmethod
    def from_domain(cls, item: ExtractionSchemaVersion) -> SchemaVersionResponse:
        return cls(
            id=item.id,
            schema_id=item.schema_id,
            review_id=item.review_id,
            version=item.version,
            content_hash=item.content_hash,
            fields=item.fields,
        )


class ExtractionRunRequest(BaseModel):
    review_id: UUID
    study_id: UUID
    schema_version_id: UUID


class ExtractionValueRequest(BaseModel):
    field_key: str = Field(min_length=1, max_length=200)
    value: Any = None
    missingness: MissingnessState
    unit: str | None = Field(default=None, max_length=100)
    source_article_id: UUID | None = None
    evidence_location_id: UUID | None = None
    evidence_text: str | None = Field(default=None, max_length=20_000)


class ExtractionValuesRequest(BaseModel):
    review_id: UUID
    status: ExtractionRunStatus = ExtractionRunStatus.IN_PROGRESS
    values: list[ExtractionValueRequest] = Field(max_length=200)


class ExtractionValueResponse(BaseModel):
    id: UUID
    field_key: str
    missingness: MissingnessState
    value: Any = None
    unit: str | None
    source_article_id: UUID | None
    evidence_location_id: UUID | None
    evidence_text: str | None

    @classmethod
    def from_domain(cls, item: ExtractionValue) -> ExtractionValueResponse:
        value: Any = item.value_integer
        if item.value_decimal is not None:
            value = item.value_decimal
        elif item.value_text is not None:
            value = item.value_text
        elif item.value_boolean is not None:
            value = item.value_boolean
        elif item.value_date is not None:
            value = item.value_date
        elif item.value_json is not None:
            value = item.value_json
        return cls(
            id=item.id,
            field_key=item.field_key,
            missingness=item.missingness,
            value=value,
            unit=item.unit,
            source_article_id=item.source_article_id,
            evidence_location_id=item.evidence_location_id,
            evidence_text=item.evidence_text,
        )


class ExtractionRunResponse(BaseModel):
    id: UUID
    review_id: UUID
    study_id: UUID
    schema_version_id: UUID
    status: ExtractionRunStatus
    values: list[ExtractionValueResponse]

    @classmethod
    def from_domain(
        cls, run: ExtractionRun, values: list[ExtractionValue]
    ) -> ExtractionRunResponse:
        return cls(
            id=run.id,
            review_id=run.review_id,
            study_id=run.study_id,
            schema_version_id=run.schema_version_id,
            status=run.status,
            values=[ExtractionValueResponse.from_domain(item) for item in values],
        )


class CompareRequest(BaseModel):
    review_id: UUID
    run_a_id: UUID
    run_b_id: UUID


class ConflictResolutionRequest(BaseModel):
    review_id: UUID
    resolution: ConflictResolution
    adjudicated_value: dict[str, Any] | None = None
    reason: str = Field(min_length=1, max_length=4000)


class ConflictResponse(BaseModel):
    id: UUID
    field_key: str
    status: str
    resolution: ConflictResolution | None
    value_a: dict[str, Any] | None
    value_b: dict[str, Any] | None
    adjudicated_value: dict[str, Any] | None
    reason: str | None

    @classmethod
    def from_domain(cls, item: ExtractionConflict) -> ConflictResponse:
        return cls(
            id=item.id,
            field_key=item.field_key,
            status=item.status.value,
            resolution=item.resolution,
            value_a=item.value_a,
            value_b=item.value_b,
            adjudicated_value=item.adjudicated_value,
            reason=item.reason,
        )


def _service(session: DbSessionDependency) -> ExtractionSchemaService:
    return ExtractionSchemaService(
        SqlAlchemyExtractionSchemaRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyProvenanceRepository(session),
    )


def _manual_service(session: DbSessionDependency) -> ManualExtractionService:
    return ManualExtractionService(
        SqlAlchemyManualExtractionRepository(session),
        SqlAlchemyExtractionSchemaRepository(session),
        SqlAlchemyStudyRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyProvenanceRepository(session),
    )


def _verification_service(session: DbSessionDependency) -> ExtractionVerificationService:
    return ExtractionVerificationService(
        SqlAlchemyExtractionVerificationRepository(session),
        SqlAlchemyManualExtractionRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyProvenanceRepository(session),
    )


@router.post("/schemas", response_model=SchemaResponse, status_code=status.HTTP_201_CREATED)
async def create_schema(
    payload: SchemaRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> SchemaResponse:
    schema = await _service(session).create_schema(
        actor, review_id=payload.review_id, name=payload.name, description=payload.description
    )
    await session.commit()
    return SchemaResponse.from_domain(schema)


@router.post(
    "/schema-versions", response_model=SchemaVersionResponse, status_code=status.HTTP_201_CREATED
)
async def create_schema_version(
    payload: SchemaVersionRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> SchemaVersionResponse:
    version = await _service(session).create_version(
        actor, review_id=payload.review_id, schema_id=payload.schema_id, fields=payload.fields
    )
    await session.commit()
    return SchemaVersionResponse.from_domain(version)


@router.get("/schemas/{schema_id}/versions", response_model=list[SchemaVersionResponse])
async def list_schema_versions(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    schema_id: Annotated[UUID, Path()],
    review_id: UUID,
) -> list[SchemaVersionResponse]:
    versions = await _service(session).list_versions(
        actor, review_id=review_id, schema_id=schema_id
    )
    return [SchemaVersionResponse.from_domain(item) for item in versions]


@router.post("/runs", response_model=ExtractionRunResponse, status_code=status.HTTP_201_CREATED)
async def create_extraction_run(
    payload: ExtractionRunRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> ExtractionRunResponse:
    run = await _manual_service(session).create_run(
        actor,
        review_id=payload.review_id,
        study_id=payload.study_id,
        schema_version_id=payload.schema_version_id,
    )
    await session.commit()
    return ExtractionRunResponse.from_domain(run, [])


@router.get("/runs/{run_id}", response_model=ExtractionRunResponse)
async def get_extraction_run(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    run_id: Annotated[UUID, Path()],
    review_id: UUID,
) -> ExtractionRunResponse:
    run, values = await _manual_service(session).get_run(actor, review_id=review_id, run_id=run_id)
    return ExtractionRunResponse.from_domain(run, values)


@router.put("/runs/{run_id}/values", response_model=ExtractionRunResponse)
async def save_extraction_values(
    payload: ExtractionValuesRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    run_id: Annotated[UUID, Path()],
) -> ExtractionRunResponse:
    run, values = await _manual_service(session).save_values(
        actor,
        review_id=payload.review_id,
        run_id=run_id,
        values=[item.model_dump(mode="json") for item in payload.values],
        status=payload.status,
    )
    await session.commit()
    return ExtractionRunResponse.from_domain(run, values)


@router.post("/verifications/compare")
async def compare_extractions(
    payload: CompareRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
) -> list[dict[str, Any]]:
    result = await _verification_service(session).compare(
        actor,
        review_id=payload.review_id,
        run_a_id=payload.run_a_id,
        run_b_id=payload.run_b_id,
    )
    await session.commit()
    return result


@router.post("/conflicts/{conflict_id}/resolve", response_model=ConflictResponse)
async def resolve_extraction_conflict(
    payload: ConflictResolutionRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    conflict_id: Annotated[UUID, Path()],
) -> ConflictResponse:
    conflict = await _verification_service(session).resolve(
        actor,
        review_id=payload.review_id,
        conflict_id=conflict_id,
        resolution=payload.resolution,
        adjudicated_value=payload.adjudicated_value,
        reason=payload.reason,
    )
    await session.commit()
    return ConflictResponse.from_domain(conflict)
