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
from backend.app.protocols.domain import (
    ProtocolDecision,
    ProtocolDecisionKind,
    ProtocolVersion,
)


class ProtocolVersionRecord(Base):
    __tablename__ = "protocol_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "review_id", "version", name="uq_protocol_versions_review_version"
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_protocol_versions_id_tenant"
        ),
        CheckConstraint("version > 0", name="ck_protocol_versions_positive_version"),
        CheckConstraint("length(content_hash) = 64", name="ck_protocol_versions_hash_length"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_protocol_versions_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_protocol_versions_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProtocolDecisionRecord(Base):
    __tablename__ = "protocol_decisions"
    __table_args__ = (
        UniqueConstraint("protocol_version_id", name="uq_protocol_decisions_version"),
        CheckConstraint(
            "decision IN ('APPROVED', 'REJECTED')", name="ck_protocol_decisions_decision"
        ),
        ForeignKeyConstraint(
            ["protocol_version_id", "organization_id", "review_id"],
            [
                "protocol_versions.id",
                "protocol_versions.organization_id",
                "protocol_versions.review_id",
            ],
            name="fk_protocol_decisions_version_tenant_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "decided_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_protocol_decisions_actor_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    protocol_version_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    decision: Mapped[str] = mapped_column(String(20))
    decided_by_user_id: Mapped[UUID] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _reject_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("approved protocol history is immutable; create a new version")


for _record_type in (ProtocolVersionRecord, ProtocolDecisionRecord):
    event.listen(_record_type, "before_update", _reject_mutation)
    event.listen(_record_type, "before_delete", _reject_mutation)


def _version_to_domain(record: ProtocolVersionRecord) -> ProtocolVersion:
    return ProtocolVersion(
        id=record.id,
        organization_id=record.organization_id,
        review_id=record.review_id,
        version=record.version,
        content=record.content,
        content_hash=record.content_hash,
        created_by_user_id=record.created_by_user_id,
        created_at=record.created_at or datetime.now(UTC),
    )


def _decision_to_domain(record: ProtocolDecisionRecord) -> ProtocolDecision:
    return ProtocolDecision(
        id=record.id,
        protocol_version_id=record.protocol_version_id,
        organization_id=record.organization_id,
        review_id=record.review_id,
        decision=ProtocolDecisionKind(record.decision),
        decided_by_user_id=record.decided_by_user_id,
        reason=record.reason,
        decided_at=record.decided_at or datetime.now(UTC),
    )


class SqlAlchemyProtocolRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_version(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        content: dict[str, Any],
        content_hash: str,
        created_by_user_id: UUID,
    ) -> ProtocolVersion:
        async def read_next_version() -> int:
            query = select(func.coalesce(func.max(ProtocolVersionRecord.version), 0)).where(
                ProtocolVersionRecord.organization_id == organization_id,
                ProtocolVersionRecord.review_id == review_id,
            )
            return int((await self._session.execute(query)).scalar_one()) + 1

        record = await insert_next_unique_integer(
            self._session,
            read_next_version,
            lambda version: ProtocolVersionRecord(
                organization_id=organization_id,
                review_id=review_id,
                version=version,
                content=content,
                content_hash=content_hash,
                created_by_user_id=created_by_user_id,
            ),
        )
        await self._session.refresh(record)
        return _version_to_domain(record)

    async def get_version(
        self, organization_id: UUID, protocol_version_id: UUID
    ) -> ProtocolVersion | None:
        query = select(ProtocolVersionRecord).where(
            ProtocolVersionRecord.organization_id == organization_id,
            ProtocolVersionRecord.id == protocol_version_id,
        )
        record = (await self._session.execute(query)).scalar_one_or_none()
        return _version_to_domain(record) if record is not None else None

    async def list_versions(
        self, organization_id: UUID, review_id: UUID
    ) -> list[tuple[ProtocolVersion, ProtocolDecision | None]]:
        query = (
            select(ProtocolVersionRecord, ProtocolDecisionRecord)
            .outerjoin(
                ProtocolDecisionRecord,
                ProtocolDecisionRecord.protocol_version_id == ProtocolVersionRecord.id,
            )
            .where(
                ProtocolVersionRecord.organization_id == organization_id,
                ProtocolVersionRecord.review_id == review_id,
            )
            .order_by(ProtocolVersionRecord.version)
        )
        rows = (await self._session.execute(query)).all()
        return [
            (
                _version_to_domain(version),
                _decision_to_domain(decision) if decision is not None else None,
            )
            for version, decision in rows
        ]

    async def get_decision(
        self, organization_id: UUID, protocol_version_id: UUID
    ) -> ProtocolDecision | None:
        query = select(ProtocolDecisionRecord).where(
            ProtocolDecisionRecord.organization_id == organization_id,
            ProtocolDecisionRecord.protocol_version_id == protocol_version_id,
        )
        record = (await self._session.execute(query)).scalar_one_or_none()
        return _decision_to_domain(record) if record is not None else None

    async def append_decision(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        protocol_version_id: UUID,
        decision: ProtocolDecisionKind,
        decided_by_user_id: UUID,
        reason: str | None,
    ) -> ProtocolDecision:
        record = ProtocolDecisionRecord(
            organization_id=organization_id,
            review_id=review_id,
            protocol_version_id=protocol_version_id,
            decision=decision.value,
            decided_by_user_id=decided_by_user_id,
            reason=reason.strip() if reason else None,
        )
        self._session.add(record)
        await self._session.flush()
        await self._session.refresh(record)
        return _decision_to_domain(record)
