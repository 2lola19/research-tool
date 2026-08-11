from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Response, status
from pydantic import BaseModel

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.exports.domain import ExportArtifact, ExportFormat
from backend.app.exports.persistence import SqlAlchemyExportRepository
from backend.app.exports.service import ExportService
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.prisma.persistence import SqlAlchemyPrismaRepository
from backend.app.prisma.service import PrismaService
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository

router = APIRouter(prefix="/exports", tags=["exports"])


class CreateExportRequest(BaseModel):
    format: ExportFormat


class ExportArtifactResponse(BaseModel):
    id: UUID
    review_id: UUID
    prisma_snapshot_id: UUID
    created_by_user_id: UUID
    format: ExportFormat
    schema_version: str
    filename: str
    media_type: str
    sha256: str
    byte_size: int
    manifest: dict[str, object]
    created_at: datetime

    @classmethod
    def from_domain(cls, artifact: ExportArtifact) -> ExportArtifactResponse:
        return cls(
            id=artifact.id,
            review_id=artifact.review_id,
            prisma_snapshot_id=artifact.prisma_snapshot_id,
            created_by_user_id=artifact.created_by_user_id,
            format=artifact.export_format,
            schema_version=artifact.schema_version,
            filename=artifact.filename,
            media_type=artifact.media_type,
            sha256=artifact.sha256,
            byte_size=artifact.byte_size,
            manifest=artifact.manifest,
            created_at=artifact.created_at,
        )


def _service(session: DbSessionDependency) -> ExportService:
    reviews = SqlAlchemyReviewRepository(session)
    identity = SqlAlchemyIdentityRepository(session)
    provenance = SqlAlchemyProvenanceRepository(session)
    prisma = PrismaService(
        SqlAlchemyPrismaRepository(session),
        reviews,
        identity,
        provenance,
    )
    return ExportService(
        SqlAlchemyExportRepository(session),
        prisma,
        reviews,
        identity,
        provenance,
    )


@router.post(
    "/reviews/{review_id}",
    response_model=ExportArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_export(
    payload: CreateExportRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> ExportArtifactResponse:
    artifact = await _service(session).create(
        actor,
        review_id=review_id,
        export_format=payload.format,
    )
    await session.commit()
    return ExportArtifactResponse.from_domain(artifact)


@router.get("/reviews/{review_id}", response_model=list[ExportArtifactResponse])
async def list_exports(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[ExportArtifactResponse]:
    artifacts = await _service(session).list(actor, review_id=review_id)
    return [ExportArtifactResponse.from_domain(artifact) for artifact in artifacts]


@router.get("/{artifact_id}", response_model=ExportArtifactResponse)
async def get_export(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    artifact_id: Annotated[UUID, Path()],
    review_id: UUID,
) -> ExportArtifactResponse:
    artifact = await _service(session).get(actor, review_id=review_id, artifact_id=artifact_id)
    return ExportArtifactResponse.from_domain(artifact)


@router.get("/{artifact_id}/download", response_class=Response)
async def download_export(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    artifact_id: Annotated[UUID, Path()],
    review_id: UUID,
) -> Response:
    artifact = await _service(session).get(
        actor,
        review_id=review_id,
        artifact_id=artifact_id,
        include_content=True,
    )
    assert artifact.content is not None
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "X-Content-SHA256": artifact.sha256,
        },
    )
