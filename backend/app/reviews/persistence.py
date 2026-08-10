from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    delete,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.identity.persistence import MembershipRecord, UserRecord
from backend.app.reviews.domain import ReviewParticipant, ReviewProject


class ReviewRecord(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_reviews_id_org"),
        CheckConstraint("length(trim(title)) > 0", name="ck_reviews_title_present"),
        CheckConstraint(
            "length(trim(project_slug)) > 0",
            name="ck_reviews_project_slug_present",
        ),
        CheckConstraint(
            "(archived_at IS NULL AND archived_by_user_id IS NULL) OR "
            "(archived_at IS NOT NULL AND archived_by_user_id IS NOT NULL)",
            name="ck_reviews_archive_metadata",
        ),
        UniqueConstraint(
            "organization_id",
            "project_slug",
            name="uq_reviews_org_project_slug",
        ),
        ForeignKeyConstraint(
            ["organization_id", "owner_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_reviews_owner_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "archived_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_reviews_archiver_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_reviews_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(300))
    project_slug: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[UUID] = mapped_column()
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by_user_id: Mapped[UUID | None] = mapped_column()


class ReviewMembershipRecord(Base):
    __tablename__ = "review_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_review_memberships_review_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_review_memberships_org_user",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "assigned_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_review_memberships_assigner",
            ondelete="RESTRICT",
        ),
    )

    review_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    organization_id: Mapped[UUID] = mapped_column()
    assigned_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


def _to_domain(record: ReviewRecord) -> ReviewProject:
    now = datetime.now(UTC)
    return ReviewProject(
        id=record.id,
        organization_id=record.organization_id,
        title=record.title,
        project_slug=record.project_slug,
        description=record.description,
        owner_user_id=record.owner_user_id,
        created_by_user_id=record.created_by_user_id,
        created_at=record.created_at or now,
        updated_at=record.updated_at or now,
        archived_at=record.archived_at,
        archived_by_user_id=record.archived_by_user_id,
    )


class SqlAlchemyReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        organization_id: UUID,
        title: str,
        project_slug: str,
        description: str | None,
        owner_user_id: UUID,
        created_by_user_id: UUID,
    ) -> ReviewProject:
        record = ReviewRecord(
            organization_id=organization_id,
            title=title,
            project_slug=project_slug,
            description=description,
            owner_user_id=owner_user_id,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _to_domain(record)

    async def get(self, organization_id: UUID, review_id: UUID) -> ReviewProject | None:
        statement = select(ReviewRecord).where(
            ReviewRecord.organization_id == organization_id,
            ReviewRecord.id == review_id,
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        return _to_domain(record) if record is not None else None

    async def project_slug_exists(
        self,
        organization_id: UUID,
        project_slug: str,
        exclude_review_id: UUID | None = None,
    ) -> bool:
        statement = select(ReviewRecord.id).where(
            ReviewRecord.organization_id == organization_id,
            ReviewRecord.project_slug == project_slug,
        )
        if exclude_review_id is not None:
            statement = statement.where(ReviewRecord.id != exclude_review_id)
        return (await self._session.execute(statement)).first() is not None

    async def list_all(self, organization_id: UUID) -> list[ReviewProject]:
        statement = (
            select(ReviewRecord)
            .where(ReviewRecord.organization_id == organization_id)
            .order_by(ReviewRecord.created_at, ReviewRecord.id)
        )
        records = (await self._session.scalars(statement)).all()
        return [_to_domain(record) for record in records]

    async def list_accessible(
        self,
        organization_id: UUID,
        user_id: UUID,
    ) -> list[ReviewProject]:
        statement = (
            select(ReviewRecord)
            .outerjoin(
                ReviewMembershipRecord,
                (ReviewMembershipRecord.review_id == ReviewRecord.id)
                & (ReviewMembershipRecord.organization_id == ReviewRecord.organization_id),
            )
            .where(
                ReviewRecord.organization_id == organization_id,
                or_(
                    ReviewRecord.owner_user_id == user_id,
                    ReviewMembershipRecord.user_id == user_id,
                ),
            )
            .distinct()
            .order_by(ReviewRecord.created_at, ReviewRecord.id)
        )
        records = (await self._session.scalars(statement)).all()
        return [_to_domain(record) for record in records]

    async def is_assigned(
        self,
        organization_id: UUID,
        review_id: UUID,
        user_id: UUID,
    ) -> bool:
        statement = select(ReviewMembershipRecord.review_id).where(
            ReviewMembershipRecord.organization_id == organization_id,
            ReviewMembershipRecord.review_id == review_id,
            ReviewMembershipRecord.user_id == user_id,
        )
        return (await self._session.execute(statement)).scalar_one_or_none() is not None

    async def user_owns_reviews(self, organization_id: UUID, user_id: UUID) -> bool:
        statement = select(ReviewRecord.id).where(
            ReviewRecord.organization_id == organization_id,
            ReviewRecord.owner_user_id == user_id,
        )
        return (await self._session.execute(statement)).first() is not None

    async def update_metadata(
        self,
        organization_id: UUID,
        review_id: UUID,
        title: str,
        project_slug: str,
        description: str | None,
    ) -> ReviewProject:
        statement = (
            update(ReviewRecord)
            .where(
                ReviewRecord.organization_id == organization_id,
                ReviewRecord.id == review_id,
            )
            .values(
                title=title,
                project_slug=project_slug,
                description=description,
                updated_at=func.now(),
            )
        )
        await self._session.execute(statement)
        record = await self.get(organization_id, review_id)
        if record is None:
            raise RuntimeError("tenant-scoped review disappeared during update")
        return record

    async def assign_user(
        self,
        organization_id: UUID,
        review_id: UUID,
        user_id: UUID,
        assigned_by_user_id: UUID,
    ) -> None:
        existing = await self.is_assigned(organization_id, review_id, user_id)
        if existing:
            return
        self._session.add(
            ReviewMembershipRecord(
                review_id=review_id,
                organization_id=organization_id,
                user_id=user_id,
                assigned_by_user_id=assigned_by_user_id,
            )
        )
        await self._session.flush()

    async def list_participants(
        self,
        organization_id: UUID,
        review_id: UUID,
    ) -> list[ReviewParticipant]:
        statement = (
            select(
                UserRecord.id,
                UserRecord.email,
                UserRecord.display_name,
                MembershipRecord.role,
            )
            .join(
                ReviewMembershipRecord,
                ReviewMembershipRecord.user_id == UserRecord.id,
            )
            .join(
                MembershipRecord,
                (MembershipRecord.user_id == UserRecord.id)
                & (MembershipRecord.organization_id == ReviewMembershipRecord.organization_id),
            )
            .where(
                ReviewMembershipRecord.organization_id == organization_id,
                ReviewMembershipRecord.review_id == review_id,
                MembershipRecord.removed_at.is_(None),
                UserRecord.is_active.is_(True),
            )
            .order_by(UserRecord.display_name, UserRecord.id)
        )
        rows = (await self._session.execute(statement)).all()
        return [
            ReviewParticipant(
                user_id=row.id,
                email=row.email,
                display_name=row.display_name,
                organization_role=row.role.value,
            )
            for row in rows
        ]

    async def remove_user(
        self,
        organization_id: UUID,
        review_id: UUID,
        user_id: UUID,
    ) -> bool:
        statement = (
            delete(ReviewMembershipRecord)
            .where(
                ReviewMembershipRecord.organization_id == organization_id,
                ReviewMembershipRecord.review_id == review_id,
                ReviewMembershipRecord.user_id == user_id,
            )
            .returning(ReviewMembershipRecord.user_id)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none() is not None

    async def transfer_ownership(
        self,
        organization_id: UUID,
        review_id: UUID,
        new_owner_user_id: UUID,
    ) -> ReviewProject:
        statement = (
            update(ReviewRecord)
            .where(
                ReviewRecord.organization_id == organization_id,
                ReviewRecord.id == review_id,
            )
            .values(owner_user_id=new_owner_user_id, updated_at=func.now())
        )
        await self._session.execute(statement)
        record = await self.get(organization_id, review_id)
        if record is None:
            raise RuntimeError("tenant-scoped review disappeared during ownership transfer")
        return record

    async def set_archived(
        self,
        organization_id: UUID,
        review_id: UUID,
        archived_by_user_id: UUID | None,
    ) -> ReviewProject:
        values = (
            {"archived_at": None, "archived_by_user_id": None, "updated_at": func.now()}
            if archived_by_user_id is None
            else {
                "archived_at": func.now(),
                "archived_by_user_id": archived_by_user_id,
                "updated_at": func.now(),
            }
        )
        statement = (
            update(ReviewRecord)
            .where(
                ReviewRecord.organization_id == organization_id,
                ReviewRecord.id == review_id,
            )
            .values(**values)
        )
        await self._session.execute(statement)
        record = await self.get(organization_id, review_id)
        if record is None:
            raise RuntimeError("tenant-scoped review disappeared during archive update")
        return record
