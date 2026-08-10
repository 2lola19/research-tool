from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from backend.app.provenance.domain import (
    AIRun,
    AIRunStatus,
    AuditEvent,
    PromptVersion,
    ProvenanceActorKind,
    ScientificProvenance,
    VerificationState,
)


class ProvenanceRepository(Protocol):
    async def create_prompt_version(
        self,
        *,
        organization_id: UUID,
        prompt_key: str,
        template: str,
        output_schema: dict[str, Any],
        created_by_user_id: UUID,
    ) -> PromptVersion: ...

    async def get_prompt_version(
        self, organization_id: UUID, prompt_version_id: UUID
    ) -> PromptVersion | None: ...

    async def append_ai_run(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        prompt_version_id: UUID,
        provider: str,
        model_name: str,
        model_version: str,
        parameters: dict[str, Any],
        input_snapshot: dict[str, Any],
        output_snapshot: dict[str, Any] | None,
        status: AIRunStatus,
        usage: dict[str, Any],
        created_by_user_id: UUID,
    ) -> AIRun: ...

    async def get_ai_run(
        self, organization_id: UUID, review_id: UUID, ai_run_id: UUID
    ) -> AIRun | None: ...

    async def append_provenance(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        subject_type: str,
        subject_id: UUID,
        source_type: str | None,
        source_id: UUID | None,
        source_locator: dict[str, Any],
        method_name: str,
        method_version: str,
        actor_kind: ProvenanceActorKind,
        actor_user_id: UUID | None,
        ai_run_id: UUID | None,
        confidence: float | None,
        verification_state: VerificationState,
    ) -> ScientificProvenance: ...

    async def list_provenance(
        self, organization_id: UUID, review_id: UUID
    ) -> list[ScientificProvenance]: ...

    async def append_audit_event(
        self,
        *,
        organization_id: UUID,
        review_id: UUID | None,
        entity_type: str,
        entity_id: UUID,
        action: str,
        actor_user_id: UUID,
        before_snapshot: dict[str, Any] | None,
        after_snapshot: dict[str, Any] | None,
        reason: str | None,
    ) -> AuditEvent: ...

    async def list_audit_events(
        self, organization_id: UUID, review_id: UUID | None
    ) -> list[AuditEvent]: ...
