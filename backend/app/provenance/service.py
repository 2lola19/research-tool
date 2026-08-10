from __future__ import annotations

from typing import Any
from uuid import UUID

from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.provenance.contracts import ProvenanceRepository
from backend.app.provenance.domain import (
    AIRun,
    AIRunStatus,
    AuditEvent,
    PromptVersion,
    ProvenanceActorKind,
    ScientificProvenance,
    VerificationState,
)
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.service import ReviewService


class ProvenanceService:
    def __init__(
        self,
        repository: ProvenanceRepository,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
    ) -> None:
        self._repository = repository
        self._review_service = ReviewService(review_repository, identity_repository)

    async def create_prompt_version(
        self,
        actor: ActorContext,
        *,
        prompt_key: str,
        template: str,
        output_schema: dict[str, Any],
    ) -> PromptVersion:
        AuthorizationService.require(actor, Permission.RECORD_PROVENANCE)
        prompt = await self._repository.create_prompt_version(
            organization_id=actor.organization_id,
            prompt_key=prompt_key.strip(),
            template=template,
            output_schema=output_schema,
            created_by_user_id=actor.user_id,
        )
        await self._repository.append_audit_event(
            organization_id=actor.organization_id,
            review_id=None,
            entity_type="prompt_version",
            entity_id=prompt.id,
            action="created",
            actor_user_id=actor.user_id,
            before_snapshot=None,
            after_snapshot={
                "prompt_key": prompt.prompt_key,
                "version": prompt.version,
            },
            reason=None,
        )
        return prompt

    async def record_ai_run(
        self,
        actor: ActorContext,
        *,
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
    ) -> AIRun:
        review = await self._review_service.get(actor, review_id)
        AuthorizationService.require(actor, Permission.RECORD_PROVENANCE)
        prompt = await self._repository.get_prompt_version(actor.organization_id, prompt_version_id)
        if prompt is None:
            raise ResourceNotFoundError("prompt version was not found")
        run = await self._repository.append_ai_run(
            organization_id=actor.organization_id,
            review_id=review.id,
            prompt_version_id=prompt.id,
            provider=provider.strip(),
            model_name=model_name.strip(),
            model_version=model_version.strip(),
            parameters=parameters,
            input_snapshot=input_snapshot,
            output_snapshot=output_snapshot,
            status=status,
            usage=usage,
            created_by_user_id=actor.user_id,
        )
        await self._repository.append_audit_event(
            organization_id=actor.organization_id,
            review_id=review.id,
            entity_type="ai_run",
            entity_id=run.id,
            action="recorded",
            actor_user_id=actor.user_id,
            before_snapshot=None,
            after_snapshot={"provider": run.provider, "status": run.status.value},
            reason=None,
        )
        return run

    async def record_provenance(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        subject_type: str,
        subject_id: UUID,
        source_type: str | None,
        source_id: UUID | None,
        source_locator: dict[str, Any],
        method_name: str,
        method_version: str,
        actor_kind: ProvenanceActorKind,
        ai_run_id: UUID | None,
        confidence: float | None,
        verification_state: VerificationState,
    ) -> ScientificProvenance:
        review = await self._review_service.get(actor, review_id)
        AuthorizationService.require(actor, Permission.RECORD_PROVENANCE)
        if (source_type is None) != (source_id is None):
            raise ConflictError("source type and source identifier must be supplied together")
        actor_user_id: UUID | None = None
        if actor_kind == ProvenanceActorKind.HUMAN:
            if ai_run_id is not None:
                raise ConflictError("human provenance cannot reference an AI run as its actor")
            actor_user_id = actor.user_id
        elif actor_kind == ProvenanceActorKind.AI:
            if ai_run_id is None:
                raise ConflictError("AI provenance requires an AI run")
            ai_run = await self._repository.get_ai_run(actor.organization_id, review.id, ai_run_id)
            if ai_run is None:
                raise ResourceNotFoundError("AI run was not found")
        else:
            raise ConflictError("system provenance is reserved for internal services")
        record = await self._repository.append_provenance(
            organization_id=actor.organization_id,
            review_id=review.id,
            subject_type=subject_type.strip(),
            subject_id=subject_id,
            source_type=source_type.strip() if source_type is not None else None,
            source_id=source_id,
            source_locator=source_locator,
            method_name=method_name.strip(),
            method_version=method_version.strip(),
            actor_kind=actor_kind,
            actor_user_id=actor_user_id,
            ai_run_id=ai_run_id,
            confidence=confidence,
            verification_state=verification_state,
        )
        await self._repository.append_audit_event(
            organization_id=actor.organization_id,
            review_id=review.id,
            entity_type="scientific_provenance",
            entity_id=record.id,
            action="recorded",
            actor_user_id=actor.user_id,
            before_snapshot=None,
            after_snapshot={
                "subject_type": record.subject_type,
                "subject_id": str(record.subject_id),
                "actor_kind": record.actor_kind.value,
            },
            reason=None,
        )
        return record

    async def list_provenance(
        self, actor: ActorContext, review_id: UUID
    ) -> list[ScientificProvenance]:
        review = await self._review_service.get(actor, review_id)
        return await self._repository.list_provenance(actor.organization_id, review.id)

    async def record_audit_event(
        self,
        actor: ActorContext,
        *,
        review_id: UUID | None,
        entity_type: str,
        entity_id: UUID,
        action: str,
        before_snapshot: dict[str, Any] | None,
        after_snapshot: dict[str, Any] | None,
        reason: str | None,
    ) -> AuditEvent:
        if review_id is not None:
            await self._review_service.get(actor, review_id)
        return await self._repository.append_audit_event(
            organization_id=actor.organization_id,
            review_id=review_id,
            entity_type=entity_type.strip(),
            entity_id=entity_id,
            action=action.strip(),
            actor_user_id=actor.user_id,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            reason=reason.strip() if reason else None,
        )

    async def list_audit_events(
        self, actor: ActorContext, review_id: UUID | None
    ) -> list[AuditEvent]:
        if review_id is not None:
            await self._review_service.get(actor, review_id)
        return await self._repository.list_audit_events(actor.organization_id, review_id)
