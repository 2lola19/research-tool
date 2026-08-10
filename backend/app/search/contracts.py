from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from backend.app.search.domain import SearchStrategyVersion, SearchTranslation


class SearchRepository(Protocol):
    async def create_version(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        protocol_version_id: UUID,
        content: dict[str, Any],
        content_hash: str,
        created_by_user_id: UUID,
    ) -> SearchStrategyVersion: ...

    async def get_version(
        self, organization_id: UUID, strategy_version_id: UUID
    ) -> SearchStrategyVersion | None: ...

    async def list_versions(
        self, organization_id: UUID, review_id: UUID
    ) -> list[SearchStrategyVersion]: ...

    async def get_translation(
        self,
        organization_id: UUID,
        strategy_version_id: UUID,
        provider: str,
        translator_version: str,
    ) -> SearchTranslation | None: ...

    async def append_translation(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        strategy_version_id: UUID,
        provider: str,
        translator_version: str,
        query: str,
        created_by_user_id: UUID,
    ) -> SearchTranslation: ...
