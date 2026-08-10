from __future__ import annotations

from uuid import UUID

from backend.app.core.errors import AuthenticationError, AuthorizationError, ConflictError
from backend.app.identity.contracts import (
    AuthenticationProvider,
    IdentityRepository,
    MembershipOwnershipGuard,
    PasswordVerifier,
)
from backend.app.identity.domain import ActorContext, OrganizationRole, Permission


def normalize_email(email: str) -> str:
    return email.strip().casefold()


class AuthenticationService:
    def __init__(
        self,
        repository: IdentityRepository,
        password_verifier: PasswordVerifier,
        authentication_provider: AuthenticationProvider,
    ) -> None:
        self._repository = repository
        self._password_verifier = password_verifier
        self._authentication_provider = authentication_provider

    async def login(self, email: str, password: str) -> str:
        record = await self._repository.get_login_record(normalize_email(email))
        if (
            record is None
            or not record.is_active
            or not self._password_verifier.verify_password(password, record.password_hash)
        ):
            raise AuthenticationError("email or password is invalid")
        return self._authentication_provider.issue_token(record.user_id)


class ActorContextService:
    def __init__(self, repository: IdentityRepository) -> None:
        self._repository = repository

    async def resolve(self, user_id: UUID, organization_id: UUID) -> ActorContext:
        actor = await self._repository.get_actor_context(user_id, organization_id)
        if actor is None:
            raise AuthorizationError("organization context is unavailable")
        return actor


class AuthorizationService:
    @staticmethod
    def require(actor: ActorContext, permission: Permission) -> None:
        if not actor.has_permission(permission):
            raise AuthorizationError("the current role does not permit this action")


class MembershipService:
    def __init__(
        self,
        repository: IdentityRepository,
        ownership_guard: MembershipOwnershipGuard,
    ) -> None:
        self._repository = repository
        self._ownership_guard = ownership_guard

    async def remove_membership(self, actor: ActorContext, user_id: UUID) -> None:
        AuthorizationService.require(actor, Permission.MANAGE_ORGANIZATION)
        target = await self._repository.get_actor_context(user_id, actor.organization_id)
        if target is None:
            raise AuthorizationError("membership is unavailable")
        if target.role == OrganizationRole.OWNER and actor.role != OrganizationRole.OWNER:
            raise AuthorizationError("only an owner may remove another owner")
        if (
            target.role == OrganizationRole.OWNER
            and await self._repository.active_owner_count(actor.organization_id) <= 1
        ):
            raise ConflictError("the final organization owner cannot be removed")
        if await self._ownership_guard.user_owns_reviews(actor.organization_id, user_id):
            raise ConflictError("review ownership must be reassigned before membership removal")
        removed = await self._repository.remove_membership(
            actor.organization_id,
            user_id,
            actor.user_id,
        )
        if not removed:
            raise AuthorizationError("membership is unavailable")
