from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Path, Response, status
from pydantic import BaseModel, Field

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.prisma.persistence import SqlAlchemyPrismaRepository
from backend.app.prisma.service import PrismaService
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reporting.domain import (
    ReportArtifact,
    ReportSnapshot,
    ReportSpecification,
    ReportType,
)
from backend.app.reporting.persistence import SqlAlchemyReportingRepository
from backend.app.reporting.service import ReportingService
from backend.app.reviews.persistence import SqlAlchemyReviewRepository

router = APIRouter(prefix="/reporting", tags=["reporting"])


class SpecificationRequest(BaseModel):
    review_id: UUID
    logical_key: str = Field(min_length=1, max_length=120)
    report_type: ReportType
    definition: dict[str, Any] = Field(default_factory=dict)


class GenerateRequest(BaseModel):
    review_id: UUID


def _service(session: DbSessionDependency) -> ReportingService:
    reviews = SqlAlchemyReviewRepository(session)
    identity = SqlAlchemyIdentityRepository(session)
    provenance = SqlAlchemyProvenanceRepository(session)
    prisma = PrismaService(SqlAlchemyPrismaRepository(session), reviews, identity, provenance)
    return ReportingService(
        SqlAlchemyReportingRepository(session), prisma, reviews, identity, provenance
    )


@router.get("/reviews/{review_id}/readiness")
async def readiness(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
    report_type: ReportType,
) -> dict[str, Any]:
    item = await _service(session).readiness(actor, review_id=review_id, report_type=report_type)
    return {
        "report_type": item.report_type,
        "ready": item.ready,
        "blockers": item.blockers,
        "source_preview": item.source_preview,
        "included_components": item.included_components,
        "excluded_components": item.excluded_components,
    }


@router.post("/specifications", status_code=status.HTTP_201_CREATED)
async def create_specification(
    payload: SpecificationRequest, actor: ActorContextDependency, session: DbSessionDependency
) -> dict[str, Any]:
    item = await _service(session).create_specification(actor, **payload.model_dump())
    await session.commit()
    return _spec(item)


@router.post("/specifications/{specification_id}/generate", status_code=status.HTTP_201_CREATED)
async def generate(
    payload: GenerateRequest,
    actor: ActorContextDependency,
    session: DbSessionDependency,
    specification_id: Annotated[UUID, Path()],
) -> dict[str, Any]:
    snapshot, artifacts = await _service(session).generate(
        actor, review_id=payload.review_id, specification_id=specification_id
    )
    await session.commit()
    return {"snapshot": _snapshot(snapshot), "artifacts": [_artifact(item) for item in artifacts]}


@router.get("/reviews/{review_id}/snapshots")
async def list_snapshots(
    actor: ActorContextDependency, session: DbSessionDependency, review_id: Annotated[UUID, Path()]
) -> list[dict[str, Any]]:
    items = await _service(session).list(actor, review_id=review_id)
    return [
        {
            "snapshot": _snapshot(item["snapshot"]),
            "currency": item["currency"],
            "stale_reasons": item["stale_reasons"],
            "artifacts": [_artifact(a) for a in item["artifacts"]],
        }
        for item in items
    ]


@router.get("/artifacts/{artifact_id}/download", response_class=Response)
async def download(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    artifact_id: Annotated[UUID, Path()],
    review_id: UUID,
) -> Response:
    item = await _service(session).artifact(
        actor, review_id=review_id, artifact_id=artifact_id, include_content=True
    )
    assert item.content is not None
    return Response(
        content=item.content,
        media_type=item.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{item.filename}"',
            "X-Content-SHA256": item.sha256,
        },
    )


def _spec(item: ReportSpecification) -> dict[str, Any]:
    return {
        "id": item.id,
        "review_id": item.review_id,
        "logical_key": item.logical_key,
        "version": item.version,
        "report_type": item.report_type,
        "definition": item.definition,
        "content_hash": item.content_hash,
        "created_at": item.created_at,
    }


def _snapshot(item: ReportSnapshot) -> dict[str, Any]:
    return {
        "id": item.id,
        "review_id": item.review_id,
        "specification_id": item.specification_id,
        "status": item.status,
        "source_references": item.source_references,
        "scientific_content_hash": item.scientific_content_hash,
        "renderer_version": item.renderer_version,
        "created_at": item.created_at,
        "completed_at": item.completed_at,
    }


def _artifact(item: ReportArtifact) -> dict[str, Any]:
    return {
        "id": item.id,
        "report_snapshot_id": item.report_snapshot_id,
        "format": item.report_format,
        "filename": item.filename,
        "media_type": item.media_type,
        "sha256": item.sha256,
        "byte_size": item.byte_size,
        "manifest": item.manifest,
        "created_at": item.created_at,
    }
