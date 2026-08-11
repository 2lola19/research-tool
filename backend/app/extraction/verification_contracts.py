from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from backend.app.extraction.domain import (
    ExtractionConflict,
    ExtractionVerification,
)


class ExtractionVerificationRepository(Protocol):
    async def create_comparison(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        study_id: UUID,
        schema_version_id: UUID,
        run_a_id: UUID,
        run_b_id: UUID,
        comparisons: list[dict[str, Any]],
    ) -> list[ExtractionVerification]: ...
    async def get_conflict(
        self, organization_id: UUID, review_id: UUID, conflict_id: UUID
    ) -> ExtractionConflict | None: ...
    async def resolve_conflict(
        self,
        *,
        conflict: ExtractionConflict,
        resolution: str,
        adjudicated_value: dict[str, Any] | None,
        adjudicated_by_user_id: UUID,
        reason: str,
    ) -> ExtractionConflict: ...
