from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from backend.app.reporting.domain import (
    ReportArtifact,
    ReportFormat,
    ReportSnapshot,
    ReportSpecification,
    ReportStatus,
    ReportType,
)


class ReportingRepository(Protocol):
    async def create_specification(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        logical_key: str,
        report_type: ReportType,
        definition: dict[str, Any],
        content_hash: str,
        created_by_user_id: UUID,
    ) -> ReportSpecification: ...

    async def get_specification(
        self, organization_id: UUID, review_id: UUID, specification_id: UUID
    ) -> ReportSpecification | None: ...

    async def build_source_payload(
        self, organization_id: UUID, review_id: UUID, prisma_snapshot_id: UUID
    ) -> dict[str, Any]: ...

    async def current_source_hashes(
        self, organization_id: UUID, review_id: UUID
    ) -> dict[str, Any]: ...

    async def create_snapshot(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        specification_id: UUID,
        status: ReportStatus,
        source_references: dict[str, Any],
        source_hashes: dict[str, Any],
        structured_content: dict[str, Any],
        scientific_content_hash: str,
        renderer_version: str,
        created_by_user_id: UUID,
    ) -> ReportSnapshot: ...

    async def create_artifact(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        report_snapshot_id: UUID,
        report_format: ReportFormat,
        filename: str,
        media_type: str,
        sha256: str,
        content: bytes,
        manifest: dict[str, Any],
    ) -> ReportArtifact: ...

    async def list_snapshots(
        self, organization_id: UUID, review_id: UUID
    ) -> list[ReportSnapshot]: ...

    async def get_snapshot(
        self, organization_id: UUID, review_id: UUID, snapshot_id: UUID
    ) -> ReportSnapshot | None: ...

    async def get_artifact(
        self,
        organization_id: UUID,
        review_id: UUID,
        artifact_id: UUID,
        *,
        include_content: bool,
    ) -> ReportArtifact | None: ...

    async def list_artifacts(
        self, organization_id: UUID, review_id: UUID
    ) -> list[ReportArtifact]: ...
