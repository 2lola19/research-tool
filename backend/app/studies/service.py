from __future__ import annotations

from uuid import UUID

from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.service import ReviewService
from backend.app.studies.contracts import StudyRepository
from backend.app.studies.domain import Study, StudyArticleLink, StudyArticleRole, StudyLinkMethod


class StudyService:
    def __init__(
        self,
        repository: StudyRepository,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
        provenance_repository: SqlAlchemyProvenanceRepository,
    ) -> None:
        self._repository = repository
        self._review_service = ReviewService(review_repository, identity_repository)
        self._provenance = ProvenanceService(
            provenance_repository, review_repository, identity_repository
        )

    async def create(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        study_key: str,
        label: str | None,
        study_design: str | None,
    ) -> Study:
        AuthorizationService.require(actor, Permission.MANAGE_STUDIES)
        review = await self._review_service.get(actor, review_id)
        study = await self._repository.create_study(
            organization_id=actor.organization_id,
            review_id=review.id,
            study_key=study_key.strip(),
            label=label.strip() if label else None,
            study_design=study_design.strip().upper() if study_design else None,
            created_by_user_id=actor.user_id,
        )
        await self._provenance.record_audit_event(
            actor,
            review_id=review.id,
            entity_type="study",
            entity_id=study.id,
            action="created",
            before_snapshot=None,
            after_snapshot={"study_key": study.study_key},
            reason=None,
        )
        return study

    async def get(self, actor: ActorContext, *, review_id: UUID, study_id: UUID) -> Study:
        review = await self._review_service.get(actor, review_id)
        study = await self._repository.get_study(actor.organization_id, review.id, study_id)
        if study is None:
            raise ResourceNotFoundError("study was not found")
        return study

    async def list_studies(self, actor: ActorContext, *, review_id: UUID) -> list[Study]:
        review = await self._review_service.get(actor, review_id)
        return await self._repository.list_studies(actor.organization_id, review.id)

    async def link(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        study_id: UUID,
        article_id: UUID,
        role: StudyArticleRole,
        method: StudyLinkMethod,
        reason: str | None,
        confidence: float | None,
        source_evidence: dict[str, object] | None,
    ) -> StudyArticleLink:
        AuthorizationService.require(actor, Permission.MANAGE_STUDIES)
        study = await self.get(actor, review_id=review_id, study_id=study_id)
        if await self._repository.active_link_exists(
            actor.organization_id, study.review_id, study.id, article_id, role
        ):
            raise ConflictError("the article is already linked with this role")
        link = await self._repository.link_article(
            study=study,
            article_id=article_id,
            role=role,
            method=method,
            reason=reason.strip() if reason else None,
            confidence=confidence,
            source_evidence=source_evidence,
            linked_by_user_id=actor.user_id,
        )
        await self._provenance.record_provenance(
            actor,
            review_id=study.review_id,
            subject_type="study_article_link",
            subject_id=link.id,
            source_type="article",
            source_id=article_id,
            source_locator=source_evidence or {},
            method_name=method.value,
            method_version="1",
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=confidence,
            verification_state=VerificationState.UNVERIFIED,
        )
        return link

    async def links(
        self, actor: ActorContext, *, review_id: UUID, study_id: UUID, active_only: bool = False
    ) -> list[StudyArticleLink]:
        study = await self.get(actor, review_id=review_id, study_id=study_id)
        return await self._repository.list_links(
            actor.organization_id, study.review_id, study.id, active_only=active_only
        )

    async def unlink(
        self, actor: ActorContext, *, review_id: UUID, link_id: UUID
    ) -> StudyArticleLink:
        AuthorizationService.require(actor, Permission.MANAGE_STUDIES)
        await self._review_service.get(actor, review_id)
        link = await self._repository.get_article_link(actor.organization_id, review_id, link_id)
        if link is None:
            raise ResourceNotFoundError("study article link was not found")
        updated = await self._repository.unlink_article(
            organization_id=actor.organization_id,
            review_id=review_id,
            link_id=link_id,
            unlinked_by_user_id=actor.user_id,
        )
        if updated is None:
            raise ConflictError("the study article link is already inactive")
        await self._provenance.record_audit_event(
            actor,
            review_id=review_id,
            entity_type="study_article_link",
            entity_id=link.id,
            action="unlinked",
            before_snapshot={"article_id": str(link.article_id), "role": link.role.value},
            after_snapshot={"unlinked": True},
            reason=None,
        )
        return updated
