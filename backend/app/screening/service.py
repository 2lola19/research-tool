from __future__ import annotations

from uuid import UUID

from backend.app.citations.contracts import CitationRepository
from backend.app.core.errors import AuthorizationError, ConflictError, ResourceNotFoundError
from backend.app.deduplication.contracts import DeduplicationRepository
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.provenance.contracts import ProvenanceRepository
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.domain import ReviewProject
from backend.app.reviews.service import ReviewService
from backend.app.screening.contracts import ScreeningRepository
from backend.app.screening.domain import (
    ScreeningAdjudication,
    ScreeningAssignment,
    ScreeningDecision,
    ScreeningDecisionKind,
    ScreeningOutcome,
    ScreeningOutcomeKind,
    ScreeningProgression,
    ScreeningQueueItem,
    ScreeningRound,
    ScreeningRoundState,
    ScreeningStage,
    compute_outcome,
)


class ScreeningService:
    def __init__(
        self,
        repository: ScreeningRepository,
        citation_repository: CitationRepository,
        deduplication_repository: DeduplicationRepository,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
        provenance_repository: ProvenanceRepository,
    ) -> None:
        self._repository = repository
        self._citation_repository = citation_repository
        self._deduplication_repository = deduplication_repository
        self._review_repository = review_repository
        self._identity_repository = identity_repository
        self._review_service = ReviewService(review_repository, identity_repository)
        self._provenance_repository = provenance_repository
        self._provenance_service = ProvenanceService(
            provenance_repository, review_repository, identity_repository
        )

    async def create_round(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        name: str,
        stage: ScreeningStage,
        required_decisions: int,
        blinded: bool,
    ) -> ScreeningRound:
        review = await self._review_service.get(actor, review_id)
        self._require_manager(actor, review)
        if not blinded:
            raise ConflictError(
                "unblinded screening is deferred until an explicit reveal policy is implemented"
            )
        round_record = await self._repository.create_round(
            organization_id=actor.organization_id,
            review_id=review.id,
            name=name.strip(),
            stage=stage,
            required_decisions=required_decisions,
            blinded=blinded,
            created_by_user_id=actor.user_id,
        )
        await self._provenance_service.record_audit_event(
            actor,
            review_id=review.id,
            entity_type="screening_round",
            entity_id=round_record.id,
            action="created",
            before_snapshot=None,
            after_snapshot={
                "stage": round_record.stage.value,
                "required_decisions": round_record.required_decisions,
                "blinded": round_record.blinded,
            },
            reason=None,
        )
        return round_record

    async def assign(
        self,
        actor: ActorContext,
        *,
        round_id: UUID,
        article_id: UUID,
        reviewer_user_id: UUID,
    ) -> ScreeningAssignment:
        round_record, review = await self._managed_round(actor, round_id)
        self._require_open(round_record)
        article = await self._citation_repository.get_article(
            actor.organization_id, review.id, article_id
        )
        if article is None:
            raise ResourceNotFoundError("article was not found")
        if await self._deduplication_repository.is_confirmed_duplicate(
            actor.organization_id, review.id, article.id
        ):
            raise ConflictError("a suppressed duplicate cannot enter a screening queue")
        reviewer = await self._identity_repository.get_actor_context(
            reviewer_user_id, actor.organization_id
        )
        if reviewer is None or not reviewer.has_permission(Permission.SCREEN_ARTICLES):
            raise AuthorizationError("target reviewer is unavailable")
        has_review_access = (
            reviewer.has_permission(Permission.VIEW_ALL_REVIEWS)
            or review.owner_user_id == reviewer.user_id
            or await self._review_repository.is_assigned(
                actor.organization_id, review.id, reviewer.user_id
            )
        )
        if not has_review_access:
            raise AuthorizationError("target reviewer has no review access")
        existing = await self._repository.get_assignment_for(
            actor.organization_id, round_record.id, article.id, reviewer.user_id
        )
        if existing is not None:
            return existing
        assigned_count = await self._repository.count_article_assignments(
            actor.organization_id, round_record.id, article.id
        )
        if assigned_count >= round_record.required_decisions:
            raise ConflictError("article already has the required reviewer assignments")
        assignment = await self._repository.create_assignment(
            organization_id=actor.organization_id,
            review_id=review.id,
            round_id=round_record.id,
            article_id=article.id,
            reviewer_user_id=reviewer.user_id,
            assigned_by_user_id=actor.user_id,
        )
        await self._provenance_service.record_audit_event(
            actor,
            review_id=review.id,
            entity_type="screening_assignment",
            entity_id=assignment.id,
            action="assigned",
            before_snapshot=None,
            after_snapshot={
                "round_id": str(round_record.id),
                "article_id": str(article.id),
                "reviewer_user_id": str(reviewer.user_id),
            },
            reason=None,
        )
        return assignment

    async def queue(self, actor: ActorContext, round_id: UUID) -> list[ScreeningQueueItem]:
        round_record = await self._get_round(actor, round_id)
        await self._review_service.get(actor, round_record.review_id)
        if not actor.has_permission(Permission.SCREEN_ARTICLES):
            raise AuthorizationError("the current role cannot screen articles")
        assignments = await self._repository.list_reviewer_assignments(
            actor.organization_id, round_record.id, actor.user_id
        )
        result = []
        for assignment in assignments:
            article = await self._citation_repository.get_article(
                actor.organization_id, assignment.review_id, assignment.article_id
            )
            if article is None:
                continue
            decision = await self._repository.get_decision_for_assignment(
                actor.organization_id, assignment.id
            )
            outcome = None
            if decision is not None:
                outcome = await self._repository.get_outcome(
                    actor.organization_id, assignment.round_id, assignment.article_id
                )
            result.append(ScreeningQueueItem(assignment, article, decision, outcome))
        return result

    async def decide(
        self,
        actor: ActorContext,
        *,
        assignment_id: UUID,
        decision: ScreeningDecisionKind,
        exclusion_reason: str | None,
    ) -> ScreeningDecision:
        if not actor.has_permission(Permission.SCREEN_ARTICLES):
            raise AuthorizationError("the current role cannot screen articles")
        assignment = await self._repository.get_assignment(actor.organization_id, assignment_id)
        if assignment is None or assignment.reviewer_user_id != actor.user_id:
            raise ResourceNotFoundError("screening assignment was not found")
        round_record = await self._get_round(actor, assignment.round_id)
        await self._review_service.get(actor, assignment.review_id)
        self._require_open(round_record)
        if (
            await self._repository.get_decision_for_assignment(actor.organization_id, assignment.id)
            is not None
        ):
            raise ConflictError("screening assignment already has a final decision")
        normalized_reason = exclusion_reason.strip() if exclusion_reason else None
        if decision == ScreeningDecisionKind.EXCLUDE and normalized_reason is None:
            raise ConflictError("an exclusion reason is required")
        if decision == ScreeningDecisionKind.INCLUDE and normalized_reason is not None:
            raise ConflictError("include decisions cannot have an exclusion reason")
        record = await self._repository.append_decision(
            assignment=assignment,
            decision=decision,
            exclusion_reason=normalized_reason,
        )
        await self._provenance_service.record_provenance(
            actor,
            review_id=assignment.review_id,
            subject_type="screening_decision",
            subject_id=record.id,
            source_type="article",
            source_id=assignment.article_id,
            source_locator={"round_id": str(assignment.round_id)},
            method_name="human-screening",
            method_version="1",
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=None,
            verification_state=VerificationState.HUMAN_VERIFIED,
        )
        await self._provenance_service.record_audit_event(
            actor,
            review_id=assignment.review_id,
            entity_type="screening_decision",
            entity_id=record.id,
            action="recorded",
            before_snapshot=None,
            after_snapshot={
                "assignment_id": str(assignment.id),
                "article_id": str(assignment.article_id),
                "decision": record.decision.value,
            },
            reason=record.exclusion_reason,
        )
        await self._compute_outcome(actor, round_record, assignment.article_id)
        return record

    async def list_outcomes(
        self, actor: ActorContext, round_id: UUID
    ) -> list[tuple[ScreeningOutcome, ScreeningAdjudication | None]]:
        round_record, _ = await self._managed_round(actor, round_id)
        outcomes = await self._repository.list_outcomes(actor.organization_id, round_record.id)
        return [
            (
                outcome,
                await self._repository.get_adjudication(actor.organization_id, outcome.id),
            )
            for outcome in outcomes
        ]

    async def adjudicate(
        self,
        actor: ActorContext,
        *,
        outcome_id: UUID,
        decision: ScreeningDecisionKind,
        reason: str | None,
    ) -> ScreeningAdjudication:
        outcome = await self._repository.get_outcome_by_id(actor.organization_id, outcome_id)
        if outcome is None:
            raise ResourceNotFoundError("screening outcome was not found")
        round_record, _ = await self._managed_round(actor, outcome.round_id)
        self._require_open(round_record)
        if outcome.outcome != ScreeningOutcomeKind.CONFLICT:
            raise ConflictError("only conflict outcomes require adjudication")
        if await self._repository.get_adjudication(actor.organization_id, outcome.id):
            raise ConflictError("screening conflict already has a final adjudication")
        normalized_reason = reason.strip() if reason else None
        if normalized_reason is None:
            raise ConflictError("an adjudication reason is required")
        record = await self._repository.append_adjudication(
            outcome=outcome,
            decision=decision,
            decided_by_user_id=actor.user_id,
            reason=normalized_reason,
        )
        await self._provenance_service.record_provenance(
            actor,
            review_id=outcome.review_id,
            subject_type="screening_adjudication",
            subject_id=record.id,
            source_type="screening_outcome",
            source_id=outcome.id,
            source_locator={"article_id": str(outcome.article_id)},
            method_name="human-screening-adjudication",
            method_version="1",
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=None,
            verification_state=VerificationState.HUMAN_VERIFIED,
        )
        await self._provenance_service.record_audit_event(
            actor,
            review_id=outcome.review_id,
            entity_type="screening_adjudication",
            entity_id=record.id,
            action="recorded",
            before_snapshot=None,
            after_snapshot={
                "outcome_id": str(outcome.id),
                "decision": record.decision.value,
            },
            reason=record.reason,
        )
        return record

    async def close(self, actor: ActorContext, round_id: UUID) -> ScreeningRound:
        round_record, review = await self._managed_round(actor, round_id)
        self._require_open(round_record)
        if not await self._repository.round_is_complete(actor.organization_id, round_record.id):
            raise ConflictError("screening round has pending decisions or conflicts")
        closed = await self._repository.close_round(
            actor.organization_id, round_record.id, actor.user_id
        )
        await self._provenance_service.record_audit_event(
            actor,
            review_id=review.id,
            entity_type="screening_round",
            entity_id=closed.id,
            action="closed",
            before_snapshot={"state": round_record.state.value},
            after_snapshot={"state": closed.state.value},
            reason=None,
        )
        return closed

    async def progress(
        self,
        actor: ActorContext,
        *,
        source_round_id: UUID,
        target_round_id: UUID,
    ) -> list[ScreeningProgression]:
        source, review = await self._managed_round(actor, source_round_id)
        target = await self._get_round(actor, target_round_id)
        if target.review_id != review.id:
            raise ResourceNotFoundError("target screening round was not found")
        if (
            source.stage != ScreeningStage.TITLE_ABSTRACT
            or target.stage != ScreeningStage.FULL_TEXT
            or source.state != ScreeningRoundState.CLOSED
            or target.state != ScreeningRoundState.OPEN
            or target.sequence <= source.sequence
        ):
            raise ConflictError("invalid full-text progression path")
        result = []
        for outcome in await self._repository.list_outcomes(actor.organization_id, source.id):
            final_decision = None
            if outcome.outcome == ScreeningOutcomeKind.INCLUDE:
                final_decision = ScreeningDecisionKind.INCLUDE
            elif outcome.outcome == ScreeningOutcomeKind.CONFLICT:
                adjudication = await self._repository.get_adjudication(
                    actor.organization_id, outcome.id
                )
                final_decision = adjudication.decision if adjudication else None
            if final_decision != ScreeningDecisionKind.INCLUDE:
                continue
            existing = await self._repository.get_progression(
                actor.organization_id, source.id, target.id, outcome.article_id
            )
            if existing is not None:
                result.append(existing)
                continue
            progression = await self._repository.create_progression(
                organization_id=actor.organization_id,
                review_id=review.id,
                article_id=outcome.article_id,
                source_round_id=source.id,
                target_round_id=target.id,
                created_by_user_id=actor.user_id,
            )
            await self._provenance_repository.append_provenance(
                organization_id=actor.organization_id,
                review_id=review.id,
                subject_type="screening_progression",
                subject_id=progression.id,
                source_type="screening_outcome",
                source_id=outcome.id,
                source_locator={
                    "source_round_id": str(source.id),
                    "target_round_id": str(target.id),
                },
                method_name="deterministic-screening-progression",
                method_version="1",
                actor_kind=ProvenanceActorKind.SYSTEM,
                actor_user_id=None,
                ai_run_id=None,
                confidence=None,
                verification_state=VerificationState.UNVERIFIED,
            )
            await self._provenance_service.record_audit_event(
                actor,
                review_id=review.id,
                entity_type="screening_progression",
                entity_id=progression.id,
                action="created",
                before_snapshot=None,
                after_snapshot={
                    "article_id": str(progression.article_id),
                    "source_round_id": str(progression.source_round_id),
                    "target_round_id": str(progression.target_round_id),
                },
                reason=None,
            )
            result.append(progression)
        return result

    async def _compute_outcome(
        self, actor: ActorContext, round_record: ScreeningRound, article_id: UUID
    ) -> ScreeningOutcome | None:
        existing = await self._repository.get_outcome(
            round_record.organization_id, round_record.id, article_id
        )
        if existing is not None:
            return existing
        decisions = await self._repository.list_article_decisions(
            round_record.organization_id, round_record.id, article_id
        )
        kind = compute_outcome(
            [item.decision for item in decisions], round_record.required_decisions
        )
        if kind is None:
            return None
        outcome = await self._repository.append_outcome(
            organization_id=round_record.organization_id,
            review_id=round_record.review_id,
            round_id=round_record.id,
            article_id=article_id,
            outcome=kind,
        )
        await self._provenance_repository.append_provenance(
            organization_id=round_record.organization_id,
            review_id=round_record.review_id,
            subject_type="screening_outcome",
            subject_id=outcome.id,
            source_type="article",
            source_id=article_id,
            source_locator={"round_id": str(round_record.id)},
            method_name="deterministic-screening-consensus",
            method_version="1",
            actor_kind=ProvenanceActorKind.SYSTEM,
            actor_user_id=None,
            ai_run_id=None,
            confidence=None,
            verification_state=VerificationState.UNVERIFIED,
        )
        await self._provenance_service.record_audit_event(
            actor,
            review_id=round_record.review_id,
            entity_type="screening_outcome",
            entity_id=outcome.id,
            action="computed",
            before_snapshot=None,
            after_snapshot={
                "round_id": str(round_record.id),
                "article_id": str(article_id),
                "outcome": outcome.outcome.value,
            },
            reason=None,
        )
        return outcome

    async def _get_round(self, actor: ActorContext, round_id: UUID) -> ScreeningRound:
        round_record = await self._repository.get_round(actor.organization_id, round_id)
        if round_record is None:
            raise ResourceNotFoundError("screening round was not found")
        return round_record

    async def _managed_round(
        self, actor: ActorContext, round_id: UUID
    ) -> tuple[ScreeningRound, ReviewProject]:
        round_record = await self._get_round(actor, round_id)
        review = await self._review_service.get(actor, round_record.review_id)
        self._require_manager(actor, review)
        return round_record, review

    @staticmethod
    def _require_open(round_record: ScreeningRound) -> None:
        if round_record.state != ScreeningRoundState.OPEN:
            raise ConflictError("screening round is closed")

    @staticmethod
    def _require_manager(actor: ActorContext, review: ReviewProject) -> None:
        if not actor.has_permission(Permission.MANAGE_SCREENING):
            raise AuthorizationError("the current role cannot manage screening")
        if (
            not actor.has_permission(Permission.VIEW_ALL_REVIEWS)
            and review.owner_user_id != actor.user_id
        ):
            raise AuthorizationError("only the review owner may manage screening")
