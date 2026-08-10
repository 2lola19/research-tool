from __future__ import annotations

import re
from collections.abc import Sequence
from uuid import UUID

from backend.app.core.errors import AuthorizationError, ConflictError, ResourceNotFoundError
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.domain import ReviewParticipant, ReviewProject


def normalize_project_slug(project_slug: str) -> str:
    normalized = project_slug.strip().casefold()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized):
        raise ValueError("project slug must use lowercase letters, numbers, and hyphens")
    return normalized


def normalize_description(description: str | None) -> str | None:
    if description is None:
        return None
    normalized = description.strip()
    return normalized or None


class ReviewService:
    def __init__(
        self,
        repository: ReviewRepository,
        identity_repository: IdentityRepository,
    ) -> None:
        self._repository = repository
        self._identity_repository = identity_repository

    async def create(
        self,
        actor: ActorContext,
        title: str,
        project_slug: str,
        description: str | None,
    ) -> ReviewProject:
        AuthorizationService.require(actor, Permission.CREATE_REVIEW)
        normalized_slug = normalize_project_slug(project_slug)
        if await self._repository.project_slug_exists(actor.organization_id, normalized_slug):
            raise ConflictError("project slug is already in use")
        return await self._repository.create(
            organization_id=actor.organization_id,
            title=title.strip(),
            project_slug=normalized_slug,
            description=normalize_description(description),
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

    async def update_metadata(
        self,
        actor: ActorContext,
        review_id: UUID,
        title: str,
        project_slug: str,
        description: str | None,
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
        normalized_slug = normalize_project_slug(project_slug)
        if await self._repository.project_slug_exists(
            actor.organization_id,
            normalized_slug,
            exclude_review_id=review.id,
        ):
            raise ConflictError("project slug is already in use")
        return await self._repository.update_metadata(
            actor.organization_id,
            review.id,
            title.strip(),
            normalized_slug,
            normalize_description(description),
        )

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

    async def list_participants(
        self,
        actor: ActorContext,
        review_id: UUID,
    ) -> Sequence[ReviewParticipant]:
        review = await self.get(actor, review_id)
        self._require_access_manager(actor, review)
        return await self._repository.list_participants(actor.organization_id, review.id)

    async def remove_user(
        self,
        actor: ActorContext,
        review_id: UUID,
        user_id: UUID,
    ) -> None:
        review = await self.get(actor, review_id)
        self._require_access_manager(actor, review)
        if user_id == review.owner_user_id:
            raise ConflictError("review ownership must be transferred before access removal")
        removed = await self._repository.remove_user(actor.organization_id, review.id, user_id)
        if not removed:
            raise ResourceNotFoundError("review membership was not found")

    async def transfer_ownership(
        self,
        actor: ActorContext,
        review_id: UUID,
        new_owner_user_id: UUID,
    ) -> ReviewProject:
        review = await self.get(actor, review_id)
        AuthorizationService.require(actor, Permission.TRANSFER_REVIEW_OWNERSHIP)
        if not await self._identity_repository.user_has_active_membership(
            actor.organization_id,
            new_owner_user_id,
        ):
            raise AuthorizationError("target membership is unavailable")
        return await self._repository.transfer_ownership(
            actor.organization_id,
            review.id,
            new_owner_user_id,
        )

    async def set_archived(
        self,
        actor: ActorContext,
        review_id: UUID,
        archived: bool,
    ) -> ReviewProject:
        review = await self.get(actor, review_id)
        self._require_access_manager(actor, review)
        return await self._repository.set_archived(
            actor.organization_id,
            review.id,
            actor.user_id if archived else None,
        )

    @staticmethod
    def _require_access_manager(actor: ActorContext, review: ReviewProject) -> None:
        AuthorizationService.require(actor, Permission.MANAGE_REVIEW_ACCESS)
        if (
            not actor.has_permission(Permission.VIEW_ALL_REVIEWS)
            and review.owner_user_id != actor.user_id
        ):
            raise AuthorizationError("only the review owner may manage access")

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
