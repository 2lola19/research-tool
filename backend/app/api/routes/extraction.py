from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.extraction.domain import (
    ExtractionSchema,
    ExtractionSchemaVersion,
)
from backend.app.extraction.schema_persistence import SqlAlchemyExtractionSchemaRepository
from backend.app.extraction.schema_service import ExtractionSchemaService
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository

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


def _service(session: DbSessionDependency) -> ExtractionSchemaService:
    return ExtractionSchemaService(
        SqlAlchemyExtractionSchemaRepository(session),
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
