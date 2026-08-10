from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.app.reviews.domain import ReviewParticipant, ReviewProject


class ReviewRepository(Protocol):
    async def create(
        self,
        organization_id: UUID,
        title: str,
        project_slug: str,
        description: str | None,
        owner_user_id: UUID,
        created_by_user_id: UUID,
    ) -> ReviewProject: ...

    async def get(self, organization_id: UUID, review_id: UUID) -> ReviewProject | None: ...

    async def project_slug_exists(
        self,
        organization_id: UUID,
        project_slug: str,
        exclude_review_id: UUID | None = None,
    ) -> bool: ...

    async def list_all(self, organization_id: UUID) -> list[ReviewProject]: ...

    async def list_accessible(
        self,
        organization_id: UUID,
        user_id: UUID,
    ) -> list[ReviewProject]: ...

    async def is_assigned(
        self,
        organization_id: UUID,
        review_id: UUID,
        user_id: UUID,
    ) -> bool: ...

    async def user_owns_reviews(self, organization_id: UUID, user_id: UUID) -> bool: ...

    async def update_metadata(
        self,
        organization_id: UUID,
        review_id: UUID,
        title: str,
        project_slug: str,
        description: str | None,
    ) -> ReviewProject: ...

    async def assign_user(
        self,
        organization_id: UUID,
        review_id: UUID,
        user_id: UUID,
        assigned_by_user_id: UUID,
    ) -> None: ...

    async def list_participants(
        self,
        organization_id: UUID,
        review_id: UUID,
    ) -> list[ReviewParticipant]: ...

    async def remove_user(
        self,
        organization_id: UUID,
        review_id: UUID,
        user_id: UUID,
    ) -> bool: ...

    async def transfer_ownership(
        self,
        organization_id: UUID,
        review_id: UUID,
        new_owner_user_id: UUID,
    ) -> ReviewProject: ...

    async def set_archived(
        self,
        organization_id: UUID,
        review_id: UUID,
        archived_by_user_id: UUID | None,
    ) -> ReviewProject: ...
