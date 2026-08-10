from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.reviews.domain import ReviewProject


class ReviewRecord(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_reviews_id_org"),
        CheckConstraint("length(trim(title)) > 0", name="ck_reviews_title_present"),
        ForeignKeyConstraint(
            ["organization_id", "owner_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_reviews_owner_membership",
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
        owner_user_id=record.owner_user_id,
        created_by_user_id=record.created_by_user_id,
        created_at=record.created_at or now,
        updated_at=record.updated_at or now,
    )


class SqlAlchemyReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        organization_id: UUID,
        title: str,
        owner_user_id: UUID,
        created_by_user_id: UUID,
    ) -> ReviewProject:
        record = ReviewRecord(
            organization_id=organization_id,
            title=title,
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

    async def update_title(
        self,
        organization_id: UUID,
        review_id: UUID,
        title: str,
    ) -> ReviewProject:
        statement = (
            update(ReviewRecord)
            .where(
                ReviewRecord.organization_id == organization_id,
                ReviewRecord.id == review_id,
            )
            .values(title=title, updated_at=func.now())
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
