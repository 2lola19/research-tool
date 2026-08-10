from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class OrganizationRole(StrEnum):
    OWNER = "owner"
    ADMINISTRATOR = "administrator"
    LEAD_REVIEWER = "lead_reviewer"
    REVIEWER = "reviewer"
    STATISTICIAN = "statistician"
    VIEWER = "viewer"


class Permission(StrEnum):
    MANAGE_ORGANIZATION = "manage_organization"
    CREATE_REVIEW = "create_review"
    VIEW_ALL_REVIEWS = "view_all_reviews"
    UPDATE_ASSIGNED_REVIEW = "update_assigned_review"
    MANAGE_REVIEW_ACCESS = "manage_review_access"


ROLE_PERMISSIONS: dict[OrganizationRole, frozenset[Permission]] = {
    OrganizationRole.OWNER: frozenset(Permission),
    OrganizationRole.ADMINISTRATOR: frozenset(Permission),
    OrganizationRole.LEAD_REVIEWER: frozenset(
        {
            Permission.CREATE_REVIEW,
            Permission.UPDATE_ASSIGNED_REVIEW,
            Permission.MANAGE_REVIEW_ACCESS,
        }
    ),
    OrganizationRole.REVIEWER: frozenset({Permission.UPDATE_ASSIGNED_REVIEW}),
    OrganizationRole.STATISTICIAN: frozenset(),
    OrganizationRole.VIEWER: frozenset(),
}


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    user_id: UUID


@dataclass(frozen=True, slots=True)
class ActorContext:
    user_id: UUID
    organization_id: UUID
    membership_id: UUID
    role: OrganizationRole

    def has_permission(self, permission: Permission) -> bool:
        return permission in ROLE_PERMISSIONS[self.role]


@dataclass(frozen=True, slots=True)
class LoginRecord:
    user_id: UUID
    password_hash: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class OrganizationSummary:
    id: UUID
    name: str
    slug: str
