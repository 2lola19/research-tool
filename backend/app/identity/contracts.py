from __future__ import annotations

from typing import Protocol
from uuid import UUID

from backend.app.identity.domain import (
    ActorContext,
    AuthenticatedIdentity,
    LoginRecord,
    OrganizationSummary,
)


class AuthenticationProvider(Protocol):
    def authenticate(self, token: str) -> AuthenticatedIdentity: ...

    def issue_token(self, user_id: UUID) -> str: ...


class PasswordVerifier(Protocol):
    def hash_password(self, password: str) -> str: ...

    def verify_password(self, password: str, encoded_hash: str) -> bool: ...


class MembershipOwnershipGuard(Protocol):
    async def user_owns_reviews(self, organization_id: UUID, user_id: UUID) -> bool: ...


class IdentityRepository(Protocol):
    async def get_login_record(self, normalized_email: str) -> LoginRecord | None: ...

    async def get_actor_context(
        self,
        user_id: UUID,
        organization_id: UUID,
    ) -> ActorContext | None: ...

    async def get_organization(self, organization_id: UUID) -> OrganizationSummary | None: ...

    async def active_owner_count(self, organization_id: UUID) -> int: ...

    async def remove_membership(
        self,
        organization_id: UUID,
        user_id: UUID,
        removed_by_user_id: UUID,
    ) -> bool: ...

    async def user_has_active_membership(self, organization_id: UUID, user_id: UUID) -> bool: ...
