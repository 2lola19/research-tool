from __future__ import annotations

from typing import Any
from uuid import UUID

from backend.app.core.errors import AuthorizationError, ConflictError, ResourceNotFoundError
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.protocols.contracts import ProtocolRepository
from backend.app.protocols.domain import ProtocolDecisionKind
from backend.app.provenance.contracts import ProvenanceRepository
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.domain import ReviewProject
from backend.app.reviews.service import ReviewService
from backend.app.search.contracts import SearchRepository
from backend.app.search.domain import (
    SearchStrategyVersion,
    SearchTranslation,
    search_content_hash,
)
from backend.app.search.translators import get_translator


class SearchStrategyService:
    def __init__(
        self,
        repository: SearchRepository,
        protocol_repository: ProtocolRepository,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
        provenance_repository: ProvenanceRepository,
    ) -> None:
        self._repository = repository
        self._protocol_repository = protocol_repository
        self._review_service = ReviewService(review_repository, identity_repository)
        self._provenance_service = ProvenanceService(
            provenance_repository, review_repository, identity_repository
        )

    async def create_version(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        protocol_version_id: UUID,
        content: dict[str, Any],
    ) -> SearchStrategyVersion:
        review = await self._review_service.get(actor, review_id)
        self._require_manager(actor, review)
        protocol = await self._protocol_repository.get_version(
            actor.organization_id, protocol_version_id
        )
        if protocol is None or protocol.review_id != review.id:
            raise ResourceNotFoundError("approved protocol version was not found")
        decision = await self._protocol_repository.get_decision(actor.organization_id, protocol.id)
        if decision is None or decision.decision != ProtocolDecisionKind.APPROVED:
            raise ConflictError("search strategies require an approved protocol version")
        strategy = await self._repository.create_version(
            organization_id=actor.organization_id,
            review_id=review.id,
            protocol_version_id=protocol.id,
            content=content,
            content_hash=search_content_hash(content),
            created_by_user_id=actor.user_id,
        )
        await self._provenance_service.record_provenance(
            actor,
            review_id=review.id,
            subject_type="search_strategy_version",
            subject_id=strategy.id,
            source_type="protocol_version",
            source_id=protocol.id,
            source_locator={"protocol_content_hash": protocol.content_hash},
            method_name="human-search-strategy-authoring",
            method_version="1",
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=None,
            verification_state=VerificationState.HUMAN_VERIFIED,
        )
        await self._provenance_service.record_audit_event(
            actor,
            review_id=review.id,
            entity_type="search_strategy_version",
            entity_id=strategy.id,
            action="created",
            before_snapshot=None,
            after_snapshot={
                "protocol_version_id": str(protocol.id),
                "content_hash": strategy.content_hash,
            },
            reason=None,
        )
        return strategy

    async def list_versions(
        self, actor: ActorContext, review_id: UUID
    ) -> list[SearchStrategyVersion]:
        review = await self._review_service.get(actor, review_id)
        return await self._repository.list_versions(actor.organization_id, review.id)

    async def translate(
        self,
        actor: ActorContext,
        *,
        strategy_version_id: UUID,
        provider: str,
    ) -> SearchTranslation:
        strategy = await self._repository.get_version(actor.organization_id, strategy_version_id)
        if strategy is None:
            raise ResourceNotFoundError("search strategy version was not found")
        review = await self._review_service.get(actor, strategy.review_id)
        self._require_manager(actor, review)
        translator = get_translator(provider)
        if translator is None:
            raise ConflictError("search provider translator is not supported")
        existing = await self._repository.get_translation(
            actor.organization_id,
            strategy.id,
            translator.provider,
            translator.version,
        )
        if existing is not None:
            return existing
        translation = await self._repository.append_translation(
            organization_id=actor.organization_id,
            review_id=review.id,
            strategy_version_id=strategy.id,
            provider=translator.provider,
            translator_version=translator.version,
            query=translator.translate(strategy.content),
            created_by_user_id=actor.user_id,
        )
        await self._provenance_service.record_provenance(
            actor,
            review_id=review.id,
            subject_type="search_translation",
            subject_id=translation.id,
            source_type="search_strategy_version",
            source_id=strategy.id,
            source_locator={"strategy_content_hash": strategy.content_hash},
            method_name=f"{translator.provider}-translator",
            method_version=translator.version,
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=None,
            verification_state=VerificationState.UNVERIFIED,
        )
        await self._provenance_service.record_audit_event(
            actor,
            review_id=review.id,
            entity_type="search_translation",
            entity_id=translation.id,
            action="translated",
            before_snapshot=None,
            after_snapshot={
                "strategy_version_id": str(strategy.id),
                "provider": translation.provider,
                "translator_version": translation.translator_version,
            },
            reason=None,
        )
        return translation

    @staticmethod
    def _require_manager(actor: ActorContext, review: ReviewProject) -> None:
        if not actor.has_permission(Permission.MANAGE_SEARCH):
            raise AuthorizationError("the current role cannot manage search strategies")
        if (
            not actor.has_permission(Permission.VIEW_ALL_REVIEWS)
            and review.owner_user_id != actor.user_id
        ):
            raise AuthorizationError("only the review owner may manage search strategies")
