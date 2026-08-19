from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    event,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from backend.app.db.base import Base
from backend.app.search.provider_domain import (
    ProviderAttemptSnapshot,
    ProviderFailureClass,
    SearchProviderAttempt,
)


class SearchProviderAttemptRecord(Base):
    __tablename__ = "search_provider_attempts"
    __table_args__ = (
        Index(
            "ix_search_provider_attempts_execution",
            "organization_id",
            "review_id",
            "search_execution_id",
            "page_number",
            "attempt_number",
        ),
        CheckConstraint("page_number > 0", name="ck_search_provider_attempt_page"),
        CheckConstraint("attempt_number > 0", name="ck_search_provider_attempt_number"),
        CheckConstraint("response_byte_size >= 0", name="ck_search_provider_attempt_size"),
        CheckConstraint(
            "failure_class IS NULL OR failure_class IN "
            "('TRANSIENT','RATE_LIMITED','TIMEOUT','PERMANENT','INVALID_RESPONSE','BLOCKED')",
            name="ck_search_provider_attempt_failure_class",
        ),
        CheckConstraint(
            "response_sha256 IS NULL OR length(response_sha256) = 64",
            name="ck_search_provider_attempt_hash",
        ),
        ForeignKeyConstraint(
            ["search_execution_id", "organization_id", "review_id"],
            [
                "search_executions.id",
                "search_executions.organization_id",
                "search_executions.review_id",
            ],
            name="fk_search_provider_attempt_execution_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_search_provider_attempt_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    search_execution_id: Mapped[UUID] = mapped_column()
    provider_key: Mapped[str] = mapped_column(String(80))
    provider_version: Mapped[str] = mapped_column(String(120))
    page_number: Mapped[int] = mapped_column(Integer)
    attempt_number: Mapped[int] = mapped_column(Integer)
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int | None] = mapped_column(Integer)
    failure_class: Mapped[str | None] = mapped_column(String(30))
    response_byte_size: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    response_sha256: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _reject_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("search provider attempt history is append-only")


event.listen(SearchProviderAttemptRecord, "before_update", _reject_mutation)
event.listen(SearchProviderAttemptRecord, "before_delete", _reject_mutation)


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _to_domain(row: SearchProviderAttemptRecord) -> SearchProviderAttempt:
    return SearchProviderAttempt(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        search_execution_id=row.search_execution_id,
        provider_key=row.provider_key,
        provider_version=row.provider_version,
        page_number=row.page_number,
        attempt_number=row.attempt_number,
        request_fingerprint=row.request_fingerprint,
        started_at=_as_utc(row.started_at),
        completed_at=_as_utc(row.completed_at),
        http_status=row.http_status,
        failure_class=(
            ProviderFailureClass(row.failure_class) if row.failure_class is not None else None
        ),
        response_byte_size=row.response_byte_size,
        response_sha256=row.response_sha256,
        note=row.note,
        created_by_user_id=row.created_by_user_id,
        created_at=_as_utc(row.created_at),
    )


class SqlAlchemySearchProviderAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append_attempt(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        search_execution_id: UUID,
        snapshot: ProviderAttemptSnapshot,
        created_by_user_id: UUID,
    ) -> SearchProviderAttempt:
        row = SearchProviderAttemptRecord(
            organization_id=organization_id,
            review_id=review_id,
            search_execution_id=search_execution_id,
            provider_key=snapshot.provider_key,
            provider_version=snapshot.provider_version,
            page_number=snapshot.page_number,
            attempt_number=snapshot.attempt_number,
            request_fingerprint=snapshot.request_fingerprint,
            started_at=snapshot.started_at,
            completed_at=snapshot.completed_at,
            http_status=snapshot.http_status,
            failure_class=snapshot.failure_class.value if snapshot.failure_class else None,
            response_byte_size=snapshot.response_byte_size,
            response_sha256=snapshot.response_sha256,
            note=snapshot.note,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_domain(row)

    async def list_attempts(
        self, organization_id: UUID, review_id: UUID, search_execution_id: UUID
    ) -> list[SearchProviderAttempt]:
        rows = await self._session.scalars(
            select(SearchProviderAttemptRecord)
            .where(
                SearchProviderAttemptRecord.organization_id == organization_id,
                SearchProviderAttemptRecord.review_id == review_id,
                SearchProviderAttemptRecord.search_execution_id == search_execution_id,
            )
            .order_by(
                SearchProviderAttemptRecord.page_number,
                SearchProviderAttemptRecord.attempt_number,
                SearchProviderAttemptRecord.id,
            )
        )
        return [_to_domain(row) for row in rows]
