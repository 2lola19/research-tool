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

from backend.app.ai.copilot_domain import (
    AICopilotPolicy,
    AICopilotQuery,
    AICopilotQueryStatus,
    AICopilotTaskKey,
)
from backend.app.db.base import Base
from backend.app.db.sequence import insert_next_unique_integer


class AICopilotPolicyRecord(Base):
    __tablename__ = "ai_copilot_policy_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "review_id", "version", name="uq_ai_copilot_policy_version"
        ),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_copilot_policy_tenant"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_copilot_policy_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_copilot_policy_creator",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "maximum_query_characters BETWEEN 100 AND 4000",
            name="ck_ai_copilot_query_characters",
        ),
        CheckConstraint(
            "maximum_context_items BETWEEN 2 AND 200",
            name="ck_ai_copilot_context_items",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    maximum_query_characters: Mapped[int] = mapped_column(Integer)
    maximum_context_items: Mapped[int] = mapped_column(Integer)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AICopilotQueryRecord(Base):
    __tablename__ = "ai_copilot_queries"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_copilot_query_tenant"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_copilot_query_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_copilot_query_creator",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            [
                "ai_execution_runs.id",
                "ai_execution_runs.organization_id",
                "ai_execution_runs.review_id",
            ],
            name="fk_ai_copilot_query_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_copilot_query_proposal",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('SUCCEEDED','ABSTAINED','FAILED','INVALID_OUTPUT')",
            name="ck_ai_copilot_query_status",
        ),
        CheckConstraint("length(context_hash) = 64", name="ck_ai_copilot_context_hash"),
        CheckConstraint("length(query_text) BETWEEN 1 AND 4000", name="ck_ai_copilot_query_text"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    task_key: Mapped[str] = mapped_column(String(50))
    query_text: Mapped[str] = mapped_column(Text)
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    context_hash: Mapped[str] = mapped_column(String(64))
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    ai_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    proposal_id: Mapped[UUID | None] = mapped_column(nullable=True)
    answer_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    validation_results: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30))
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _policy(row: AICopilotPolicyRecord) -> AICopilotPolicy:
    return AICopilotPolicy(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        version=row.version,
        maximum_query_characters=row.maximum_query_characters,
        maximum_context_items=row.maximum_context_items,
        created_by_user_id=row.created_by_user_id,
    )


def _query(row: AICopilotQueryRecord) -> AICopilotQuery:
    return AICopilotQuery(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        task_key=AICopilotTaskKey(row.task_key),
        query_text=row.query_text,
        context_snapshot=row.context_snapshot,
        context_hash=row.context_hash,
        citations=tuple(row.citations),
        ai_run_id=row.ai_run_id,
        proposal_id=row.proposal_id,
        answer_snapshot=row.answer_snapshot,
        validation_results=row.validation_results,
        status=AICopilotQueryStatus(row.status),
        failure_reason=row.failure_reason,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at or datetime.now(UTC),
    )


def _reject_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("AI copilot policy and query records are append-only")


event.listen(AICopilotPolicyRecord, "before_update", _reject_mutation)
event.listen(AICopilotPolicyRecord, "before_delete", _reject_mutation)
event.listen(AICopilotQueryRecord, "before_update", _reject_mutation)
event.listen(AICopilotQueryRecord, "before_delete", _reject_mutation)


class SqlAlchemyAICopilotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def current_policy(
        self, organization_id: UUID, review_id: UUID
    ) -> AICopilotPolicy | None:
        row = await self.session.scalar(
            select(AICopilotPolicyRecord)
            .where(
                AICopilotPolicyRecord.organization_id == organization_id,
                AICopilotPolicyRecord.review_id == review_id,
            )
            .order_by(AICopilotPolicyRecord.version.desc())
            .limit(1)
        )
        return _policy(row) if row else None

    async def create_policy(self, **values: Any) -> AICopilotPolicy:
        async def next_version() -> int:
            current = await self.session.scalar(
                select(func.max(AICopilotPolicyRecord.version)).where(
                    AICopilotPolicyRecord.organization_id == values["organization_id"],
                    AICopilotPolicyRecord.review_id == values["review_id"],
                )
            )
            return int(current or 0) + 1

        row = await insert_next_unique_integer(
            self.session,
            next_version,
            lambda version: AICopilotPolicyRecord(**values, version=version),
        )
        await self.session.refresh(row)
        return _policy(row)

    async def create_query(self, **values: Any) -> AICopilotQuery:
        row = AICopilotQueryRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _query(row)

    async def get_query(
        self, organization_id: UUID, review_id: UUID, query_id: UUID
    ) -> AICopilotQuery | None:
        row = await self.session.scalar(
            select(AICopilotQueryRecord).where(
                AICopilotQueryRecord.organization_id == organization_id,
                AICopilotQueryRecord.review_id == review_id,
                AICopilotQueryRecord.id == query_id,
            )
        )
        return _query(row) if row else None

    async def list_queries(self, organization_id: UUID, review_id: UUID) -> list[AICopilotQuery]:
        rows = await self.session.scalars(
            select(AICopilotQueryRecord)
            .where(
                AICopilotQueryRecord.organization_id == organization_id,
                AICopilotQueryRecord.review_id == review_id,
            )
            .order_by(AICopilotQueryRecord.created_at.desc(), AICopilotQueryRecord.id.desc())
        )
        return [_query(row) for row in rows]
