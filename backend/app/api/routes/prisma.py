from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel

from backend.app.api.dependencies import ActorContextDependency, DbSessionDependency
from backend.app.identity.persistence import SqlAlchemyIdentityRepository
from backend.app.prisma.domain import PrismaReadiness, PrismaSnapshot, PrismaSummary
from backend.app.prisma.persistence import SqlAlchemyPrismaRepository
from backend.app.prisma.service import PrismaService
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.persistence import SqlAlchemyReviewRepository

router = APIRouter(prefix="/prisma", tags=["prisma"])


class PrismaSummaryResponse(BaseModel):
    counts: dict[str, int | dict[str, int] | None]
    readiness: dict[str, object]
    source_references: dict[str, object]

    @classmethod
    def from_values(
        cls,
        summary: PrismaSummary,
        readiness: PrismaReadiness,
        references: dict[str, object],
    ) -> PrismaSummaryResponse:
        return cls(
            counts=summary.as_dict(),
            readiness=readiness.as_dict(),
            source_references=references,
        )


class PrismaSnapshotResponse(BaseModel):
    id: UUID
    review_id: UUID
    created_by_user_id: UUID
    algorithm_version: str
    counts: dict[str, object]
    readiness: dict[str, object]
    source_references: dict[str, object]
    created_at: datetime

    @classmethod
    def from_domain(cls, item: PrismaSnapshot) -> PrismaSnapshotResponse:
        return cls(
            id=item.id,
            review_id=item.review_id,
            created_by_user_id=item.created_by_user_id,
            algorithm_version=item.algorithm_version,
            counts=item.counts,
            readiness=item.readiness,
            source_references=item.source_references,
            created_at=item.created_at,
        )


def _service(session: DbSessionDependency) -> PrismaService:
    return PrismaService(
        SqlAlchemyPrismaRepository(session),
        SqlAlchemyReviewRepository(session),
        SqlAlchemyIdentityRepository(session),
        SqlAlchemyProvenanceRepository(session),
    )


@router.get("/reviews/{review_id}/summary", response_model=PrismaSummaryResponse)
async def get_prisma_summary(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> PrismaSummaryResponse:
    summary, readiness, references = await _service(session).summary(actor, review_id=review_id)
    return PrismaSummaryResponse.from_values(summary, readiness, references)


@router.post(
    "/reviews/{review_id}/snapshots",
    response_model=PrismaSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_prisma_snapshot(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> PrismaSnapshotResponse:
    snapshot = await _service(session).create_snapshot(actor, review_id=review_id)
    await session.commit()
    return PrismaSnapshotResponse.from_domain(snapshot)


@router.get("/reviews/{review_id}/snapshots", response_model=list[PrismaSnapshotResponse])
async def list_prisma_snapshots(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    review_id: Annotated[UUID, Path()],
) -> list[PrismaSnapshotResponse]:
    snapshots = await _service(session).list_snapshots(actor, review_id=review_id)
    return [PrismaSnapshotResponse.from_domain(item) for item in snapshots]


@router.get("/snapshots/{snapshot_id}", response_model=PrismaSnapshotResponse)
async def get_prisma_snapshot(
    actor: ActorContextDependency,
    session: DbSessionDependency,
    snapshot_id: Annotated[UUID, Path()],
    review_id: UUID,
) -> PrismaSnapshotResponse:
    snapshot = await _service(session).get_snapshot(
        actor, review_id=review_id, snapshot_id=snapshot_id
    )
    return PrismaSnapshotResponse.from_domain(snapshot)
