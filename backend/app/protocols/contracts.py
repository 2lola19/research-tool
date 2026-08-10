from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from backend.app.protocols.domain import (
    ProtocolDecision,
    ProtocolDecisionKind,
    ProtocolVersion,
)


class ProtocolRepository(Protocol):
    async def create_version(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        content: dict[str, Any],
        content_hash: str,
        created_by_user_id: UUID,
    ) -> ProtocolVersion: ...

    async def get_version(
        self, organization_id: UUID, protocol_version_id: UUID
    ) -> ProtocolVersion | None: ...

    async def list_versions(
        self, organization_id: UUID, review_id: UUID
    ) -> list[tuple[ProtocolVersion, ProtocolDecision | None]]: ...

    async def get_decision(
        self, organization_id: UUID, protocol_version_id: UUID
    ) -> ProtocolDecision | None: ...

    async def append_decision(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        protocol_version_id: UUID,
        decision: ProtocolDecisionKind,
        decided_by_user_id: UUID,
        reason: str | None,
    ) -> ProtocolDecision: ...
