from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.app.reviews.domain import ReviewProject


class ReviewRepository(Protocol):
    async def create(
        self,
        organization_id: UUID,
        title: str,
        owner_user_id: UUID,
        created_by_user_id: UUID,
    ) -> ReviewProject: ...

    async def get(self, organization_id: UUID, review_id: UUID) -> ReviewProject | None: ...

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

    async def update_title(
        self,
        organization_id: UUID,
        review_id: UUID,
        title: str,
    ) -> ReviewProject: ...

    async def assign_user(
        self,
        organization_id: UUID,
        review_id: UUID,
        user_id: UUID,
        assigned_by_user_id: UUID,
    ) -> None: ...
