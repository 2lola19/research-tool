from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.app.search.provider_domain import (
    ProviderAttemptSnapshot,
    SearchProviderAttempt,
)


class SearchProviderAttemptRepository(Protocol):
    async def append_attempt(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        search_execution_id: UUID,
        snapshot: ProviderAttemptSnapshot,
        created_by_user_id: UUID,
    ) -> SearchProviderAttempt: ...

    async def list_attempts(
        self, organization_id: UUID, review_id: UUID, search_execution_id: UUID
    ) -> list[SearchProviderAttempt]: ...
