from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.identity.domain import (
    ActorContext,
    LoginRecord,
    OrganizationRole,
    OrganizationSummary,
)


def _enum_values(enum_type: type[OrganizationRole]) -> list[str]:
    return [member.value for member in enum_type]


class UserRecord(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(email)", name="ck_users_email_normalized"),
        CheckConstraint("length(trim(display_name)) > 0", name="ck_users_display_name_present"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class OrganizationRecord(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("slug = lower(slug)", name="ck_organizations_slug_normalized"),
        CheckConstraint("length(trim(name)) > 0", name="ck_organizations_name_present"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class MembershipRecord(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
        Index("ix_memberships_user_org_active", "user_id", "organization_id", "removed_at"),
        CheckConstraint(
            "(removed_at IS NULL AND removed_by_user_id IS NULL) OR "
            "(removed_at IS NOT NULL AND removed_by_user_id IS NOT NULL)",
            name="ck_memberships_removal_metadata",
        ),
        CheckConstraint(
            "role IN ('owner', 'administrator', 'lead_reviewer', 'reviewer', "
            "'statistician', 'viewer')",
            name="ck_memberships_role",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[OrganizationRole] = mapped_column(
        Enum(
            OrganizationRole,
            name="organization_role",
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            values_callable=_enum_values,
            length=32,
        )
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )


class LocalCredentialRecord(Base):
    __tablename__ = "local_credentials"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class SqlAlchemyIdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_login_record(self, normalized_email: str) -> LoginRecord | None:
        statement = (
            select(UserRecord.id, UserRecord.is_active, LocalCredentialRecord.password_hash)
            .join(LocalCredentialRecord, LocalCredentialRecord.user_id == UserRecord.id)
            .where(UserRecord.email == normalized_email)
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        return LoginRecord(
            user_id=row.id,
            password_hash=row.password_hash,
            is_active=row.is_active,
        )

    async def get_actor_context(
        self,
        user_id: UUID,
        organization_id: UUID,
    ) -> ActorContext | None:
        statement = (
            select(MembershipRecord.id, MembershipRecord.role)
            .join(UserRecord, UserRecord.id == MembershipRecord.user_id)
            .where(
                MembershipRecord.user_id == user_id,
                MembershipRecord.organization_id == organization_id,
                MembershipRecord.removed_at.is_(None),
                UserRecord.is_active.is_(True),
            )
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        return ActorContext(
            user_id=user_id,
            organization_id=organization_id,
            membership_id=row.id,
            role=row.role,
        )

    async def get_organization(self, organization_id: UUID) -> OrganizationSummary | None:
        statement = select(OrganizationRecord).where(OrganizationRecord.id == organization_id)
        record = (await self._session.execute(statement)).scalar_one_or_none()
        if record is None:
            return None
        return OrganizationSummary(id=record.id, name=record.name, slug=record.slug)

    async def active_owner_count(self, organization_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(MembershipRecord)
            .where(
                MembershipRecord.organization_id == organization_id,
                MembershipRecord.role == OrganizationRole.OWNER,
                MembershipRecord.removed_at.is_(None),
            )
        )
        return int((await self._session.execute(statement)).scalar_one())

    async def remove_membership(
        self,
        organization_id: UUID,
        user_id: UUID,
        removed_by_user_id: UUID,
    ) -> bool:
        statement = (
            update(MembershipRecord)
            .where(
                MembershipRecord.organization_id == organization_id,
                MembershipRecord.user_id == user_id,
                MembershipRecord.removed_at.is_(None),
            )
            .values(removed_at=func.now(), removed_by_user_id=removed_by_user_id)
            .returning(MembershipRecord.id)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def user_has_active_membership(self, organization_id: UUID, user_id: UUID) -> bool:
        statement = select(MembershipRecord.id).where(
            MembershipRecord.organization_id == organization_id,
            MembershipRecord.user_id == user_id,
            MembershipRecord.removed_at.is_(None),
        )
        return (await self._session.execute(statement)).scalar_one_or_none() is not None
