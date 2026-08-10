from __future__ import annotations

from uuid import UUID

from backend.app.core.errors import AuthorizationError, ResourceNotFoundError
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.domain import ReviewProject


class ReviewService:
    def __init__(
        self,
        repository: ReviewRepository,
        identity_repository: IdentityRepository,
    ) -> None:
        self._repository = repository
        self._identity_repository = identity_repository

    async def create(self, actor: ActorContext, title: str) -> ReviewProject:
        AuthorizationService.require(actor, Permission.CREATE_REVIEW)
        return await self._repository.create(
            organization_id=actor.organization_id,
            title=title.strip(),
            owner_user_id=actor.user_id,
            created_by_user_id=actor.user_id,
        )

    async def list(self, actor: ActorContext) -> list[ReviewProject]:
        if actor.has_permission(Permission.VIEW_ALL_REVIEWS):
            return await self._repository.list_all(actor.organization_id)
        return await self._repository.list_accessible(actor.organization_id, actor.user_id)

    async def get(self, actor: ActorContext, review_id: UUID) -> ReviewProject:
        review = await self._repository.get(actor.organization_id, review_id)
        if review is None or not await self._can_access(actor, review):
            raise ResourceNotFoundError("review was not found")
        return review

    async def update_title(
        self,
        actor: ActorContext,
        review_id: UUID,
        title: str,
    ) -> ReviewProject:
        review = await self.get(actor, review_id)
        if not actor.has_permission(Permission.UPDATE_ASSIGNED_REVIEW):
            raise AuthorizationError("the current role cannot modify reviews")
        if not (
            actor.has_permission(Permission.VIEW_ALL_REVIEWS)
            or review.owner_user_id == actor.user_id
            or await self._repository.is_assigned(
                actor.organization_id,
                review.id,
                actor.user_id,
            )
        ):
            raise ResourceNotFoundError("review was not found")
        return await self._repository.update_title(actor.organization_id, review.id, title.strip())

    async def assign_user(
        self,
        actor: ActorContext,
        review_id: UUID,
        user_id: UUID,
    ) -> None:
        review = await self.get(actor, review_id)
        AuthorizationService.require(actor, Permission.MANAGE_REVIEW_ACCESS)
        if (
            not actor.has_permission(Permission.VIEW_ALL_REVIEWS)
            and review.owner_user_id != actor.user_id
        ):
            raise AuthorizationError("only the review owner may manage access")
        if not await self._identity_repository.user_has_active_membership(
            actor.organization_id,
            user_id,
        ):
            raise AuthorizationError("target membership is unavailable")
        await self._repository.assign_user(
            actor.organization_id,
            review.id,
            user_id,
            actor.user_id,
        )

    async def _can_access(self, actor: ActorContext, review: ReviewProject) -> bool:
        if actor.has_permission(Permission.VIEW_ALL_REVIEWS):
            return True
        if review.owner_user_id == actor.user_id:
            return True
        return await self._repository.is_assigned(
            actor.organization_id,
            review.id,
            actor.user_id,
        )
