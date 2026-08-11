from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base
from backend.app.studies.domain import Study, StudyArticleLink, StudyArticleRole, StudyLinkMethod


class StudyRecord(Base):
    __tablename__ = "studies"
    __table_args__ = (
        UniqueConstraint("organization_id", "review_id", "study_key", name="uq_studies_review_key"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_studies_id_tenant"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_studies_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_studies_creator_membership",
            ondelete="RESTRICT",
        ),
        CheckConstraint("length(trim(study_key)) > 0", name="ck_studies_key_present"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    study_key: Mapped[str] = mapped_column(String(100))
    label: Mapped[str | None] = mapped_column(String(500))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudyArticleLinkRecord(Base):
    __tablename__ = "study_article_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_study_links_study_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_study_links_article_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "linked_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_study_links_creator_membership",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "unlinked_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_study_links_remover_membership",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_study_links_id_tenant"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_study_links_confidence",
        ),
        CheckConstraint(
            "role IN ('PRIMARY','PROTOCOL','FOLLOW_UP','SUBGROUP',"
            "'SECONDARY_ANALYSIS','CONFERENCE_ABSTRACT','CORRECTION',"
            "'SUPPLEMENT','OTHER')",
            name="ck_study_links_role",
        ),
        CheckConstraint(
            "method IN ('MANUAL','EXACT_REGISTRY_MATCH','METADATA_MATCH',"
            "'AI_SUGGESTED','IMPORTED')",
            name="ck_study_links_method",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    study_id: Mapped[UUID] = mapped_column()
    article_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    role: Mapped[str] = mapped_column(String(30))
    method: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column()
    source_evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    linked_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unlinked_by_user_id: Mapped[UUID | None] = mapped_column()


def _study(record: StudyRecord) -> Study:
    return Study(
        record.id,
        record.organization_id,
        record.review_id,
        record.study_key,
        record.label,
        record.created_by_user_id,
        record.created_at or datetime.now(UTC),
    )


def _link(record: StudyArticleLinkRecord) -> StudyArticleLink:
    return StudyArticleLink(
        record.id,
        record.study_id,
        record.article_id,
        record.organization_id,
        record.review_id,
        StudyArticleRole(record.role),
        StudyLinkMethod(record.method),
        record.reason,
        record.confidence,
        record.source_evidence,
        record.linked_by_user_id,
        record.created_at or datetime.now(UTC),
        record.unlinked_at,
        record.unlinked_by_user_id,
    )


class SqlAlchemyStudyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_study(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        study_key: str,
        label: str | None,
        created_by_user_id: UUID,
    ) -> Study:
        record = StudyRecord(
            organization_id=organization_id,
            review_id=review_id,
            study_key=study_key,
            label=label,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _study(record)

    async def get_study(
        self, organization_id: UUID, review_id: UUID, study_id: UUID
    ) -> Study | None:
        record = (
            await self._session.execute(
                select(StudyRecord).where(
                    StudyRecord.organization_id == organization_id,
                    StudyRecord.review_id == review_id,
                    StudyRecord.id == study_id,
                )
            )
        ).scalar_one_or_none()
        return _study(record) if record else None

    async def list_studies(self, organization_id: UUID, review_id: UUID) -> list[Study]:
        records = (
            await self._session.execute(
                select(StudyRecord)
                .where(
                    StudyRecord.organization_id == organization_id,
                    StudyRecord.review_id == review_id,
                )
                .order_by(StudyRecord.study_key)
            )
        ).scalars()
        return [_study(record) for record in records]

    async def get_article_link(
        self, organization_id: UUID, review_id: UUID, link_id: UUID
    ) -> StudyArticleLink | None:
        record = (
            await self._session.execute(
                select(StudyArticleLinkRecord).where(
                    StudyArticleLinkRecord.organization_id == organization_id,
                    StudyArticleLinkRecord.review_id == review_id,
                    StudyArticleLinkRecord.id == link_id,
                )
            )
        ).scalar_one_or_none()
        return _link(record) if record else None

    async def list_links(
        self, organization_id: UUID, review_id: UUID, study_id: UUID, *, active_only: bool = False
    ) -> list[StudyArticleLink]:
        query = select(StudyArticleLinkRecord).where(
            StudyArticleLinkRecord.organization_id == organization_id,
            StudyArticleLinkRecord.review_id == review_id,
            StudyArticleLinkRecord.study_id == study_id,
        )
        if active_only:
            query = query.where(StudyArticleLinkRecord.unlinked_at.is_(None))
        records = (
            await self._session.execute(query.order_by(StudyArticleLinkRecord.created_at))
        ).scalars()
        return [_link(record) for record in records]

    async def active_link_exists(
        self,
        organization_id: UUID,
        review_id: UUID,
        study_id: UUID,
        article_id: UUID,
        role: StudyArticleRole,
    ) -> bool:
        result = await self._session.execute(
            select(StudyArticleLinkRecord.id)
            .where(
                StudyArticleLinkRecord.organization_id == organization_id,
                StudyArticleLinkRecord.review_id == review_id,
                StudyArticleLinkRecord.study_id == study_id,
                StudyArticleLinkRecord.article_id == article_id,
                StudyArticleLinkRecord.role == role.value,
                StudyArticleLinkRecord.unlinked_at.is_(None),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def article_linked(
        self, organization_id: UUID, review_id: UUID, study_id: UUID, article_id: UUID
    ) -> bool:
        result = await self._session.execute(
            select(StudyArticleLinkRecord.id)
            .where(
                StudyArticleLinkRecord.organization_id == organization_id,
                StudyArticleLinkRecord.review_id == review_id,
                StudyArticleLinkRecord.study_id == study_id,
                StudyArticleLinkRecord.article_id == article_id,
                StudyArticleLinkRecord.unlinked_at.is_(None),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def link_article(
        self,
        *,
        study: Study,
        article_id: UUID,
        role: StudyArticleRole,
        method: StudyLinkMethod,
        reason: str | None,
        confidence: float | None,
        source_evidence: dict[str, object] | None,
        linked_by_user_id: UUID,
    ) -> StudyArticleLink:
        record = StudyArticleLinkRecord(
            study_id=study.id,
            article_id=article_id,
            organization_id=study.organization_id,
            review_id=study.review_id,
            role=role.value,
            method=method.value,
            reason=reason,
            confidence=confidence,
            source_evidence=source_evidence,
            linked_by_user_id=linked_by_user_id,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _link(record)

    async def unlink_article(
        self, *, organization_id: UUID, review_id: UUID, link_id: UUID, unlinked_by_user_id: UUID
    ) -> StudyArticleLink | None:
        record = (
            await self._session.execute(
                select(StudyArticleLinkRecord).where(
                    StudyArticleLinkRecord.organization_id == organization_id,
                    StudyArticleLinkRecord.review_id == review_id,
                    StudyArticleLinkRecord.id == link_id,
                )
            )
        ).scalar_one_or_none()
        if record is None or record.unlinked_at is not None:
            return None
        record.unlinked_at = datetime.now(UTC)
        record.unlinked_by_user_id = unlinked_by_user_id
        await self._session.flush()
        return _link(record)
