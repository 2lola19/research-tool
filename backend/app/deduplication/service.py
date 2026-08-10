from __future__ import annotations

from uuid import UUID

from backend.app.citations.contracts import CitationRepository
from backend.app.core.errors import AuthorizationError, ConflictError, ResourceNotFoundError
from backend.app.deduplication.contracts import DeduplicationRepository
from backend.app.deduplication.domain import (
    DedupDecisionKind,
    DeduplicationDecision,
    DeduplicationRun,
    DuplicateCandidate,
    deduplication_input_hash,
    find_duplicate_candidates,
)
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.provenance.contracts import ProvenanceRepository
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.service import ReviewService

ALGORITHM_VERSION = "deterministic-v1"


class DeduplicationService:
    def __init__(
        self,
        repository: DeduplicationRepository,
        citation_repository: CitationRepository,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
        provenance_repository: ProvenanceRepository,
    ) -> None:
        self._repository = repository
        self._citation_repository = citation_repository
        self._review_service = ReviewService(review_repository, identity_repository)
        self._provenance_repository = provenance_repository
        self._provenance_service = ProvenanceService(
            provenance_repository, review_repository, identity_repository
        )

    async def scan(self, actor: ActorContext, review_id: UUID) -> DeduplicationRun:
        review = await self._review_service.get(actor, review_id)
        self._require_manager(actor)
        articles = await self._citation_repository.list_articles(actor.organization_id, review.id)
        input_hash = deduplication_input_hash(articles)
        existing = await self._repository.get_run_by_input(
            actor.organization_id,
            review.id,
            ALGORITHM_VERSION,
            input_hash,
        )
        if existing is not None:
            return existing
        run, candidates = await self._repository.create_run(
            organization_id=actor.organization_id,
            review_id=review.id,
            algorithm_version=ALGORITHM_VERSION,
            input_hash=input_hash,
            article_count=len(articles),
            matches=find_duplicate_candidates(articles),
            created_by_user_id=actor.user_id,
        )
        for candidate in candidates:
            await self._provenance_repository.append_provenance(
                organization_id=actor.organization_id,
                review_id=review.id,
                subject_type="duplicate_candidate",
                subject_id=candidate.id,
                source_type=None,
                source_id=None,
                source_locator={
                    "left_article_id": str(candidate.left_article_id),
                    "right_article_id": str(candidate.right_article_id),
                },
                method_name="deterministic-deduplication",
                method_version=ALGORITHM_VERSION,
                actor_kind=ProvenanceActorKind.SYSTEM,
                actor_user_id=None,
                ai_run_id=None,
                confidence=candidate.score,
                verification_state=VerificationState.UNVERIFIED,
            )
        await self._provenance_service.record_audit_event(
            actor,
            review_id=review.id,
            entity_type="deduplication_run",
            entity_id=run.id,
            action="completed",
            before_snapshot=None,
            after_snapshot={
                "algorithm_version": run.algorithm_version,
                "article_count": run.article_count,
                "candidate_count": run.candidate_count,
            },
            reason=None,
        )
        return run

    async def list_candidates(
        self, actor: ActorContext, review_id: UUID
    ) -> list[tuple[DuplicateCandidate, DeduplicationDecision | None]]:
        review = await self._review_service.get(actor, review_id)
        return await self._repository.list_candidates(actor.organization_id, review.id)

    async def decide(
        self,
        actor: ActorContext,
        *,
        candidate_id: UUID,
        decision: DedupDecisionKind,
        retained_article_id: UUID | None,
        reason: str | None,
    ) -> DeduplicationDecision:
        self._require_manager(actor)
        candidate = await self._repository.get_candidate(actor.organization_id, candidate_id)
        if candidate is None:
            raise ResourceNotFoundError("duplicate candidate was not found")
        await self._review_service.get(actor, candidate.review_id)
        if await self._repository.get_decision(actor.organization_id, candidate.id) is not None:
            raise ConflictError("duplicate candidate already has a final decision")
        pair = {candidate.left_article_id, candidate.right_article_id}
        if decision == DedupDecisionKind.CONFIRMED_DUPLICATE:
            if retained_article_id not in pair:
                raise ConflictError(
                    "confirmed duplicates require one retained Article from the pair"
                )
        elif retained_article_id is not None:
            raise ConflictError("rejected candidates cannot select a retained Article")
        record = await self._repository.append_decision(
            organization_id=actor.organization_id,
            review_id=candidate.review_id,
            candidate_id=candidate.id,
            decision=decision,
            retained_article_id=retained_article_id,
            decided_by_user_id=actor.user_id,
            reason=reason,
        )
        await self._provenance_service.record_provenance(
            actor,
            review_id=candidate.review_id,
            subject_type="duplicate_candidate",
            subject_id=candidate.id,
            source_type=None,
            source_id=None,
            source_locator={"decision_id": str(record.id)},
            method_name="human-deduplication-decision",
            method_version="1",
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=None,
            verification_state=VerificationState.HUMAN_VERIFIED,
        )
        await self._provenance_service.record_audit_event(
            actor,
            review_id=candidate.review_id,
            entity_type="deduplication_decision",
            entity_id=record.id,
            action=decision.value.casefold(),
            before_snapshot=None,
            after_snapshot={
                "candidate_id": str(candidate.id),
                "decision": record.decision.value,
                "retained_article_id": (
                    str(record.retained_article_id)
                    if record.retained_article_id is not None
                    else None
                ),
            },
            reason=reason,
        )
        return record

    @staticmethod
    def _require_manager(actor: ActorContext) -> None:
        if not actor.has_permission(Permission.MANAGE_DEDUPLICATION):
            raise AuthorizationError("the current role cannot manage deduplication")
