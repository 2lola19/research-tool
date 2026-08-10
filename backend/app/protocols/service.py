from __future__ import annotations

from typing import Any
from uuid import UUID

from backend.app.core.errors import AuthorizationError, ConflictError, ResourceNotFoundError
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.protocols.contracts import ProtocolRepository
from backend.app.protocols.domain import (
    ProtocolDecision,
    ProtocolDecisionKind,
    ProtocolVersion,
    protocol_content_hash,
)
from backend.app.provenance.contracts import ProvenanceRepository
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.domain import ReviewProject
from backend.app.reviews.service import ReviewService


class ProtocolService:
    def __init__(
        self,
        repository: ProtocolRepository,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
        provenance_repository: ProvenanceRepository,
    ) -> None:
        self._repository = repository
        self._review_service = ReviewService(review_repository, identity_repository)
        self._provenance_service = ProvenanceService(
            provenance_repository, review_repository, identity_repository
        )

    async def create_version(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        content: dict[str, Any],
    ) -> ProtocolVersion:
        review = await self._review_service.get(actor, review_id)
        self._require_manager(actor, review)
        version = await self._repository.create_version(
            organization_id=actor.organization_id,
            review_id=review.id,
            content=content,
            content_hash=protocol_content_hash(content),
            created_by_user_id=actor.user_id,
        )
        await self._provenance_service.record_audit_event(
            actor,
            review_id=review.id,
            entity_type="protocol_version",
            entity_id=version.id,
            action="created",
            before_snapshot=None,
            after_snapshot={
                "version": version.version,
                "content_hash": version.content_hash,
            },
            reason=None,
        )
        return version

    async def list_versions(
        self, actor: ActorContext, review_id: UUID
    ) -> list[tuple[ProtocolVersion, ProtocolDecision | None]]:
        review = await self._review_service.get(actor, review_id)
        return await self._repository.list_versions(actor.organization_id, review.id)

    async def decide(
        self,
        actor: ActorContext,
        *,
        protocol_version_id: UUID,
        decision: ProtocolDecisionKind,
        reason: str | None,
    ) -> ProtocolDecision:
        version = await self._repository.get_version(actor.organization_id, protocol_version_id)
        if version is None:
            raise ResourceNotFoundError("protocol version was not found")
        review = await self._review_service.get(actor, version.review_id)
        self._require_manager(actor, review)
        if await self._repository.get_decision(actor.organization_id, version.id) is not None:
            raise ConflictError("protocol version already has a final decision")
        if decision == ProtocolDecisionKind.REJECTED and not reason:
            raise ConflictError("a rejection reason is required")
        record = await self._repository.append_decision(
            organization_id=actor.organization_id,
            review_id=review.id,
            protocol_version_id=version.id,
            decision=decision,
            decided_by_user_id=actor.user_id,
            reason=reason,
        )
        await self._provenance_service.record_provenance(
            actor,
            review_id=review.id,
            subject_type="protocol_version",
            subject_id=version.id,
            source_type=None,
            source_id=None,
            source_locator={"content_hash": version.content_hash},
            method_name="human-protocol-decision",
            method_version="1",
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=None,
            verification_state=(
                VerificationState.HUMAN_VERIFIED
                if decision == ProtocolDecisionKind.APPROVED
                else VerificationState.REJECTED
            ),
        )
        await self._provenance_service.record_audit_event(
            actor,
            review_id=review.id,
            entity_type="protocol_decision",
            entity_id=record.id,
            action=decision.value.casefold(),
            before_snapshot=None,
            after_snapshot={"protocol_version_id": str(version.id)},
            reason=reason,
        )
        return record

    @staticmethod
    def _require_manager(actor: ActorContext, review: ReviewProject) -> None:
        if not actor.has_permission(Permission.MANAGE_PROTOCOL):
            raise AuthorizationError("the current role cannot manage protocols")
        if (
            not actor.has_permission(Permission.VIEW_ALL_REVIEWS)
            and review.owner_user_id != actor.user_id
        ):
            raise AuthorizationError("only the review owner may manage protocols")
