from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from backend.app.extraction.domain import (
    ExtractionRun,
    ExtractionRunStatus,
    ExtractionValue,
)


class ManualExtractionRepository(Protocol):
    async def create_run(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        study_id: UUID,
        schema_version_id: UUID,
        extractor_user_id: UUID,
    ) -> ExtractionRun: ...
    async def get_run(
        self, organization_id: UUID, review_id: UUID, run_id: UUID
    ) -> ExtractionRun | None: ...
    async def list_values(
        self, organization_id: UUID, review_id: UUID, run_id: UUID
    ) -> list[ExtractionValue]: ...
    async def save_values(
        self, *, run: ExtractionRun, values: list[dict[str, Any]], status: ExtractionRunStatus
    ) -> list[ExtractionValue]: ...
    async def get_evidence_source(
        self, organization_id: UUID, review_id: UUID, evidence_location_id: UUID
    ) -> tuple[UUID, UUID] | None: ...
