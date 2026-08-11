from __future__ import annotations

from uuid import UUID

from backend.app.core.errors import ResourceNotFoundError
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.prisma.contracts import PrismaRepository
from backend.app.prisma.domain import PrismaReadiness, PrismaSnapshot, PrismaSummary
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.service import ReviewService


class PrismaService:
    def __init__(
        self,
        repository: PrismaRepository,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
        provenance_repository: SqlAlchemyProvenanceRepository,
    ) -> None:
        self._repository = repository
        self._review_service = ReviewService(review_repository, identity_repository)
        self._provenance = ProvenanceService(
            provenance_repository, review_repository, identity_repository
        )

    async def summary(
        self, actor: ActorContext, *, review_id: UUID
    ) -> tuple[PrismaSummary, PrismaReadiness, dict[str, object]]:
        review = await self._review_service.get(actor, review_id)
        return await self._repository.summarize(actor.organization_id, review.id)

    async def create_snapshot(self, actor: ActorContext, *, review_id: UUID) -> PrismaSnapshot:
        AuthorizationService.require(actor, Permission.EXPORT_REVIEW)
        summary, readiness, references = await self.summary(actor, review_id=review_id)
        snapshot = await self._repository.create_snapshot(
            organization_id=actor.organization_id,
            review_id=review_id,
            created_by_user_id=actor.user_id,
            algorithm_version="prisma-2020-deterministic-2",
            summary=summary,
            readiness=readiness,
            source_references=references,
        )
        await self._provenance.record_audit_event(
            actor,
            review_id=review_id,
            entity_type="prisma_snapshot",
            entity_id=snapshot.id,
            action="created",
            before_snapshot=None,
            after_snapshot={
                "algorithm_version": snapshot.algorithm_version,
                "ready_for_final": readiness.ready_for_final,
            },
            reason=None,
        )
        await self._provenance.record_provenance(
            actor,
            review_id=review_id,
            subject_type="prisma_snapshot",
            subject_id=snapshot.id,
            source_type=None,
            source_id=None,
            source_locator={"source_references": references},
            method_name="deterministic_prisma_summary",
            method_version="prisma-2020-deterministic-2",
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=None,
            verification_state=VerificationState.HUMAN_VERIFIED,
        )
        return snapshot

    async def get_snapshot(
        self, actor: ActorContext, *, review_id: UUID, snapshot_id: UUID
    ) -> PrismaSnapshot:
        await self._review_service.get(actor, review_id)
        snapshot = await self._repository.get_snapshot(
            actor.organization_id, review_id, snapshot_id
        )
        if snapshot is None:
            raise ResourceNotFoundError("PRISMA snapshot was not found")
        return snapshot

    async def list_snapshots(self, actor: ActorContext, *, review_id: UUID) -> list[PrismaSnapshot]:
        await self._review_service.get(actor, review_id)
        return await self._repository.list_snapshots(actor.organization_id, review_id)
