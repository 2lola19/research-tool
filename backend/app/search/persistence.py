from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from backend.app.db.base import Base
from backend.app.db.sequence import insert_next_unique_integer
from backend.app.search.domain import SearchStrategyVersion, SearchTranslation


class SearchStrategyVersionRecord(Base):
    __tablename__ = "search_strategy_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "review_id",
            "version",
            name="uq_search_strategy_versions_review_version",
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_search_strategy_versions_id_tenant"
        ),
        CheckConstraint("version > 0", name="ck_search_strategy_versions_positive_version"),
        CheckConstraint(
            "length(content_hash) = 64", name="ck_search_strategy_versions_hash_length"
        ),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_search_strategy_versions_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["protocol_version_id", "organization_id", "review_id"],
            [
                "protocol_versions.id",
                "protocol_versions.organization_id",
                "protocol_versions.review_id",
            ],
            name="fk_search_strategy_versions_protocol_tenant_review",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_search_strategy_versions_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    protocol_version_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SearchTranslationRecord(Base):
    __tablename__ = "search_translations"
    __table_args__ = (
        UniqueConstraint(
            "search_strategy_version_id",
            "provider",
            "translator_version",
            name="uq_search_translations_strategy_provider_version",
        ),
        ForeignKeyConstraint(
            ["search_strategy_version_id", "organization_id", "review_id"],
            [
                "search_strategy_versions.id",
                "search_strategy_versions.organization_id",
                "search_strategy_versions.review_id",
            ],
            name="fk_search_translations_strategy_tenant_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_search_translations_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    search_strategy_version_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    provider: Mapped[str] = mapped_column(String(80))
    translator_version: Mapped[str] = mapped_column(String(50))
    query: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _reject_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("search strategy history is immutable; create a new version")


for _record_type in (SearchStrategyVersionRecord, SearchTranslationRecord):
    event.listen(_record_type, "before_update", _reject_mutation)
    event.listen(_record_type, "before_delete", _reject_mutation)


def _strategy_to_domain(record: SearchStrategyVersionRecord) -> SearchStrategyVersion:
    return SearchStrategyVersion(
        id=record.id,
        organization_id=record.organization_id,
        review_id=record.review_id,
        protocol_version_id=record.protocol_version_id,
        version=record.version,
        content=record.content,
        content_hash=record.content_hash,
        created_by_user_id=record.created_by_user_id,
        created_at=record.created_at or datetime.now(UTC),
    )


def _translation_to_domain(record: SearchTranslationRecord) -> SearchTranslation:
    return SearchTranslation(
        id=record.id,
        search_strategy_version_id=record.search_strategy_version_id,
        organization_id=record.organization_id,
        review_id=record.review_id,
        provider=record.provider,
        translator_version=record.translator_version,
        query=record.query,
        created_by_user_id=record.created_by_user_id,
        created_at=record.created_at or datetime.now(UTC),
    )


class SqlAlchemySearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_version(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        protocol_version_id: UUID,
        content: dict[str, Any],
        content_hash: str,
        created_by_user_id: UUID,
    ) -> SearchStrategyVersion:
        async def read_next_version() -> int:
            query = select(func.coalesce(func.max(SearchStrategyVersionRecord.version), 0)).where(
                SearchStrategyVersionRecord.organization_id == organization_id,
                SearchStrategyVersionRecord.review_id == review_id,
            )
            return int((await self._session.execute(query)).scalar_one()) + 1

        record = await insert_next_unique_integer(
            self._session,
            read_next_version,
            lambda version: SearchStrategyVersionRecord(
                organization_id=organization_id,
                review_id=review_id,
                protocol_version_id=protocol_version_id,
                version=version,
                content=content,
                content_hash=content_hash,
                created_by_user_id=created_by_user_id,
            ),
        )
        await self._session.refresh(record)
        return _strategy_to_domain(record)

    async def get_version(
        self, organization_id: UUID, strategy_version_id: UUID
    ) -> SearchStrategyVersion | None:
        query = select(SearchStrategyVersionRecord).where(
            SearchStrategyVersionRecord.organization_id == organization_id,
            SearchStrategyVersionRecord.id == strategy_version_id,
        )
        record = (await self._session.execute(query)).scalar_one_or_none()
        return _strategy_to_domain(record) if record is not None else None

    async def list_versions(
        self, organization_id: UUID, review_id: UUID
    ) -> list[SearchStrategyVersion]:
        query = (
            select(SearchStrategyVersionRecord)
            .where(
                SearchStrategyVersionRecord.organization_id == organization_id,
                SearchStrategyVersionRecord.review_id == review_id,
            )
            .order_by(SearchStrategyVersionRecord.version)
        )
        return [_strategy_to_domain(row) for row in await self._session.scalars(query)]

    async def get_translation(
        self,
        organization_id: UUID,
        strategy_version_id: UUID,
        provider: str,
        translator_version: str,
    ) -> SearchTranslation | None:
        query = select(SearchTranslationRecord).where(
            SearchTranslationRecord.organization_id == organization_id,
            SearchTranslationRecord.search_strategy_version_id == strategy_version_id,
            SearchTranslationRecord.provider == provider,
            SearchTranslationRecord.translator_version == translator_version,
        )
        record = (await self._session.execute(query)).scalar_one_or_none()
        return _translation_to_domain(record) if record is not None else None

    async def append_translation(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        strategy_version_id: UUID,
        provider: str,
        translator_version: str,
        query: str,
        created_by_user_id: UUID,
    ) -> SearchTranslation:
        record = SearchTranslationRecord(
            organization_id=organization_id,
            review_id=review_id,
            search_strategy_version_id=strategy_version_id,
            provider=provider,
            translator_version=translator_version,
            query=query,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _translation_to_domain(record)
