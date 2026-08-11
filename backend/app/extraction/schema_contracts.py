from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from backend.app.extraction.domain import ExtractionSchema, ExtractionSchemaVersion


class ExtractionSchemaRepository(Protocol):
    async def create_schema(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        name: str,
        description: str | None,
        created_by_user_id: UUID,
    ) -> ExtractionSchema: ...
    async def get_schema(
        self, organization_id: UUID, review_id: UUID, schema_id: UUID
    ) -> ExtractionSchema | None: ...
    async def create_version(
        self,
        *,
        schema: ExtractionSchema,
        fields: list[dict[str, Any]],
        content_hash: str,
        created_by_user_id: UUID,
    ) -> ExtractionSchemaVersion: ...
    async def list_versions(
        self, organization_id: UUID, review_id: UUID, schema_id: UUID
    ) -> list[ExtractionSchemaVersion]: ...
    async def get_version(
        self, organization_id: UUID, review_id: UUID, version_id: UUID
    ) -> ExtractionSchemaVersion | None: ...
