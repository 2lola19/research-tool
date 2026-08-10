from __future__ import annotations

import argparse
import asyncio
import os
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.errors import ConflictError
from backend.app.db.session import session_factory
from backend.app.identity.domain import OrganizationRole
from backend.app.identity.persistence import (
    LocalCredentialRecord,
    MembershipRecord,
    OrganizationRecord,
    UserRecord,
)
from backend.app.identity.security import ScryptPasswordHasher
from backend.app.identity.service import normalize_email


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    user_id: UUID
    organization_id: UUID


async def bootstrap_local_identity(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str,
    organization_name: str,
    organization_slug: str,
) -> BootstrapResult:
    normalized_email = normalize_email(email)
    normalized_slug = organization_slug.strip().casefold()
    normalized_display_name = display_name.strip()
    normalized_organization_name = organization_name.strip()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", normalized_slug):
        raise ValueError("organization slug must use lowercase letters, numbers, and hyphens")
    if not normalized_display_name or not normalized_organization_name:
        raise ValueError("display name and organization name are required")

    conflict_statement = select(UserRecord.id).where(UserRecord.email == normalized_email)
    organization_conflict = select(OrganizationRecord.id).where(
        or_(
            OrganizationRecord.slug == normalized_slug,
            OrganizationRecord.name == normalized_organization_name,
        )
    )
    if (
        await session.scalar(conflict_statement) is not None
        or await session.scalar(organization_conflict) is not None
    ):
        raise ConflictError("local identity bootstrap already exists")

    user = UserRecord(email=normalized_email, display_name=normalized_display_name)
    organization = OrganizationRecord(
        name=normalized_organization_name,
        slug=normalized_slug,
    )
    session.add_all([user, organization])
    await session.flush()
    session.add_all(
        [
            MembershipRecord(
                organization_id=organization.id,
                user_id=user.id,
                role=OrganizationRole.OWNER,
            ),
            LocalCredentialRecord(
                user_id=user.id,
                password_hash=ScryptPasswordHasher().hash_password(password),
            ),
        ]
    )
    await session.commit()
    return BootstrapResult(user_id=user.id, organization_id=organization.id)


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required for local identity bootstrap")
    return value


async def _run() -> None:
    parser = argparse.ArgumentParser(description="Create the first local organization owner")
    parser.parse_args()
    async with session_factory() as session:
        result = await bootstrap_local_identity(
            session,
            email=_required_environment("LOCAL_ADMIN_EMAIL"),
            password=_required_environment("LOCAL_ADMIN_PASSWORD"),
            display_name=_required_environment("LOCAL_ADMIN_DISPLAY_NAME"),
            organization_name=_required_environment("LOCAL_ORGANIZATION_NAME"),
            organization_slug=_required_environment("LOCAL_ORGANIZATION_SLUG"),
        )
    print(f"local identity created: user={result.user_id} organization={result.organization_id}")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
