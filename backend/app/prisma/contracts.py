from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from backend.app.prisma.domain import PrismaReadiness, PrismaSnapshot, PrismaSummary


class PrismaRepository(Protocol):
    async def summarize(
        self, organization_id: UUID, review_id: UUID
    ) -> tuple[PrismaSummary, PrismaReadiness, dict[str, Any]]: ...

    async def create_snapshot(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        created_by_user_id: UUID,
        algorithm_version: str,
        summary: PrismaSummary,
        readiness: PrismaReadiness,
        source_references: dict[str, Any],
    ) -> PrismaSnapshot: ...

    async def get_snapshot(
        self, organization_id: UUID, review_id: UUID, snapshot_id: UUID
    ) -> PrismaSnapshot | None: ...

    async def list_snapshots(
        self, organization_id: UUID, review_id: UUID
    ) -> list[PrismaSnapshot]: ...
