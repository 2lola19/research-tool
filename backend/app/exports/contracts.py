from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from backend.app.exports.domain import ExportArtifact, ExportDataset, ExportFormat
from backend.app.prisma.domain import PrismaSnapshot


class ExportRepository(Protocol):
    async def build_dataset(self, snapshot: PrismaSnapshot) -> ExportDataset: ...

    async def create_artifact(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        prisma_snapshot_id: UUID,
        created_by_user_id: UUID,
        export_format: ExportFormat,
        schema_version: str,
        filename: str,
        media_type: str,
        sha256: str,
        content: bytes,
        manifest: dict[str, Any],
    ) -> ExportArtifact: ...

    async def get_artifact(
        self,
        organization_id: UUID,
        review_id: UUID,
        artifact_id: UUID,
        *,
        include_content: bool,
    ) -> ExportArtifact | None: ...

    async def list_artifacts(
        self, organization_id: UUID, review_id: UUID
    ) -> list[ExportArtifact]: ...
