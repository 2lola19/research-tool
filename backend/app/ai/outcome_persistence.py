from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
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

from backend.app.ai.outcome_domain import AIOutcomePolicy, AIOutcomeProposalLink
from backend.app.db.base import Base
from backend.app.db.sequence import insert_next_unique_integer


class AIOutcomePolicyRecord(Base):
    __tablename__ = "ai_outcome_policy_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "review_id", "version", name="uq_ai_outcome_policy_version"
        ),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_outcome_policy_tenant"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_outcome_policy_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_outcome_policy_creator",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    maximum_batch_size: Mapped[int] = mapped_column(Integer)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIOutcomeProposalLinkRecord(Base):
    __tablename__ = "ai_outcome_proposal_links"
    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_ai_outcome_proposal"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_outcome_link_tenant"),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_outcome_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            [
                "ai_execution_runs.id",
                "ai_execution_runs.organization_id",
                "ai_execution_runs.review_id",
            ],
            name="fk_ai_outcome_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["extraction_value_id", "organization_id", "review_id"],
            [
                "extraction_values.id",
                "extraction_values.organization_id",
                "extraction_values.review_id",
            ],
            name="fk_ai_outcome_extraction_value",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_ai_outcome_study",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["outcome_version_id", "organization_id", "review_id"],
            [
                "outcome_definition_versions.id",
                "outcome_definition_versions.organization_id",
                "outcome_definition_versions.review_id",
            ],
            name="fk_ai_outcome_version",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    ai_run_id: Mapped[UUID] = mapped_column()
    study_id: Mapped[UUID] = mapped_column()
    extraction_value_id: Mapped[UUID] = mapped_column()
    outcome_version_id: Mapped[UUID] = mapped_column()
    outcome_version_hash: Mapped[str] = mapped_column(String(64))
    extraction_snapshot_hash: Mapped[str] = mapped_column(String(64))
    task_definition_version: Mapped[int] = mapped_column(Integer)
    source_manifest: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    selected_chunk_ids: Mapped[list[str]] = mapped_column(JSON)
    omitted_chunks: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    selection_method: Mapped[str] = mapped_column(String(100))
    chunk_manifest_hash: Mapped[str] = mapped_column(String(64))
    selected_text_hash: Mapped[str] = mapped_column(String(64))
    validation_results: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIOutcomeAccessRecord(Base):
    __tablename__ = "ai_outcome_access_events"
    __table_args__ = (
        UniqueConstraint(
            "proposal_id", "reviewer_user_id", "access_type", name="uq_ai_outcome_access"
        ),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_outcome_access_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reviewer_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_outcome_access_reviewer",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    reviewer_user_id: Mapped[UUID] = mapped_column()
    access_type: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AIOutcomeReviewRecord(Base):
    __tablename__ = "ai_outcome_human_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_outcome_human_review_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reviewer_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_outcome_human_review_reviewer",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    action: Mapped[str] = mapped_column(String(20))
    canonical_action: Mapped[str | None] = mapped_column(String(40), nullable=True)
    canonical_subject_id: Mapped[UUID | None] = mapped_column(nullable=True)
    ai_candidate_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    human_payload_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIOutcomeEvaluationDatasetRecord(Base):
    __tablename__ = "ai_outcome_evaluation_datasets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "review_id",
            "logical_key",
            "version",
            name="uq_ai_outcome_dataset_version",
        ),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_outcome_dataset_tenant"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_outcome_dataset_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_outcome_dataset_creator",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    logical_key: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(300))
    reference_standard: Mapped[str] = mapped_column(String(40))
    cases: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIOutcomeEvaluationResultRecord(Base):
    __tablename__ = "ai_outcome_evaluation_results"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_outcome_result_tenant"),
        ForeignKeyConstraint(
            ["dataset_id", "organization_id", "review_id"],
            [
                "ai_outcome_evaluation_datasets.id",
                "ai_outcome_evaluation_datasets.organization_id",
                "ai_outcome_evaluation_datasets.review_id",
            ],
            name="fk_ai_outcome_result_dataset",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_outcome_result_creator",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    dataset_id: Mapped[UUID] = mapped_column()
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSON)
    case_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    result_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIOutcomeErrorClassificationRecord(Base):
    __tablename__ = "ai_outcome_error_classifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["evaluation_result_id", "organization_id", "review_id"],
            [
                "ai_outcome_evaluation_results.id",
                "ai_outcome_evaluation_results.organization_id",
                "ai_outcome_evaluation_results.review_id",
            ],
            name="fk_ai_outcome_error_result",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "classified_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_outcome_error_classifier",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    evaluation_result_id: Mapped[UUID] = mapped_column()
    case_key: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(80))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    classified_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _policy(row: AIOutcomePolicyRecord) -> AIOutcomePolicy:
    return AIOutcomePolicy(
        row.id,
        row.organization_id,
        row.review_id,
        row.version,
        row.maximum_batch_size,
        row.created_by_user_id,
    )


def _link(row: AIOutcomeProposalLinkRecord) -> AIOutcomeProposalLink:
    return AIOutcomeProposalLink(
        row.id,
        row.organization_id,
        row.review_id,
        row.proposal_id,
        row.ai_run_id,
        row.study_id,
        row.extraction_value_id,
        row.outcome_version_id,
        row.outcome_version_hash,
        row.extraction_snapshot_hash,
        row.task_definition_version,
        list(row.source_manifest),
        tuple(row.selected_chunk_ids),
        tuple(row.omitted_chunks),
        row.selection_method,
        row.chunk_manifest_hash,
        row.selected_text_hash,
        row.validation_results,
    )


def _reject_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("AI outcome records are append-only")


for _immutable in (
    AIOutcomePolicyRecord,
    AIOutcomeProposalLinkRecord,
    AIOutcomeAccessRecord,
    AIOutcomeReviewRecord,
    AIOutcomeEvaluationDatasetRecord,
    AIOutcomeEvaluationResultRecord,
    AIOutcomeErrorClassificationRecord,
):
    event.listen(_immutable, "before_update", _reject_mutation)
    event.listen(_immutable, "before_delete", _reject_mutation)


class SqlAlchemyAIOutcomeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def current_policy(
        self, organization_id: UUID, review_id: UUID
    ) -> AIOutcomePolicy | None:
        row = await self.session.scalar(
            select(AIOutcomePolicyRecord)
            .where(
                AIOutcomePolicyRecord.organization_id == organization_id,
                AIOutcomePolicyRecord.review_id == review_id,
            )
            .order_by(AIOutcomePolicyRecord.version.desc())
            .limit(1)
        )
        return _policy(row) if row else None

    async def create_policy(self, **values: Any) -> AIOutcomePolicy:
        async def next_version() -> int:
            current = await self.session.scalar(
                select(func.max(AIOutcomePolicyRecord.version)).where(
                    AIOutcomePolicyRecord.organization_id == values["organization_id"],
                    AIOutcomePolicyRecord.review_id == values["review_id"],
                )
            )
            return int(current or 0) + 1

        row = await insert_next_unique_integer(
            self.session,
            next_version,
            lambda version: AIOutcomePolicyRecord(**values, version=version),
        )
        await self.session.refresh(row)
        return _policy(row)

    async def create_link(self, **values: Any) -> AIOutcomeProposalLink:
        row = AIOutcomeProposalLinkRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _link(row)

    async def get_link(
        self, organization_id: UUID, review_id: UUID, proposal_id: UUID
    ) -> AIOutcomeProposalLink | None:
        row = await self.session.scalar(
            select(AIOutcomeProposalLinkRecord).where(
                AIOutcomeProposalLinkRecord.organization_id == organization_id,
                AIOutcomeProposalLinkRecord.review_id == review_id,
                AIOutcomeProposalLinkRecord.proposal_id == proposal_id,
            )
        )
        return _link(row) if row else None

    async def list_links(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AIOutcomeProposalLink]:
        rows = await self.session.scalars(
            select(AIOutcomeProposalLinkRecord)
            .where(
                AIOutcomeProposalLinkRecord.organization_id == organization_id,
                AIOutcomeProposalLinkRecord.review_id == review_id,
            )
            .order_by(AIOutcomeProposalLinkRecord.created_at.desc())
        )
        return [_link(row) for row in rows]

    async def record_access(self, **values: Any) -> None:
        existing = await self.session.scalar(
            select(AIOutcomeAccessRecord).where(
                AIOutcomeAccessRecord.organization_id == values["organization_id"],
                AIOutcomeAccessRecord.review_id == values["review_id"],
                AIOutcomeAccessRecord.proposal_id == values["proposal_id"],
                AIOutcomeAccessRecord.reviewer_user_id == values["reviewer_user_id"],
                AIOutcomeAccessRecord.access_type == values["access_type"],
            )
        )
        if existing is None:
            self.session.add(AIOutcomeAccessRecord(**values))
            await self.session.flush()

    async def record_review(self, **values: Any) -> AIOutcomeReviewRecord:
        row = AIOutcomeReviewRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def create_dataset(self, **values: Any) -> AIOutcomeEvaluationDatasetRecord:
        async def next_version() -> int:
            current = await self.session.scalar(
                select(func.max(AIOutcomeEvaluationDatasetRecord.version)).where(
                    AIOutcomeEvaluationDatasetRecord.organization_id == values["organization_id"],
                    AIOutcomeEvaluationDatasetRecord.review_id == values["review_id"],
                    AIOutcomeEvaluationDatasetRecord.logical_key == values["logical_key"],
                )
            )
            return int(current or 0) + 1

        row = await insert_next_unique_integer(
            self.session,
            next_version,
            lambda version: AIOutcomeEvaluationDatasetRecord(**values, version=version),
        )
        await self.session.refresh(row)
        return row

    async def list_datasets(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AIOutcomeEvaluationDatasetRecord]:
        rows = await self.session.scalars(
            select(AIOutcomeEvaluationDatasetRecord)
            .where(
                AIOutcomeEvaluationDatasetRecord.organization_id == organization_id,
                AIOutcomeEvaluationDatasetRecord.review_id == review_id,
            )
            .order_by(AIOutcomeEvaluationDatasetRecord.created_at.desc())
        )
        return list(rows)

    async def get_dataset(
        self, organization_id: UUID, review_id: UUID, dataset_id: UUID
    ) -> AIOutcomeEvaluationDatasetRecord | None:
        return cast(
            AIOutcomeEvaluationDatasetRecord | None,
            await self.session.scalar(
                select(AIOutcomeEvaluationDatasetRecord).where(
                    AIOutcomeEvaluationDatasetRecord.organization_id == organization_id,
                    AIOutcomeEvaluationDatasetRecord.review_id == review_id,
                    AIOutcomeEvaluationDatasetRecord.id == dataset_id,
                )
            ),
        )

    async def create_result(self, **values: Any) -> AIOutcomeEvaluationResultRecord:
        row = AIOutcomeEvaluationResultRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def list_results(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AIOutcomeEvaluationResultRecord]:
        rows = await self.session.scalars(
            select(AIOutcomeEvaluationResultRecord)
            .where(
                AIOutcomeEvaluationResultRecord.organization_id == organization_id,
                AIOutcomeEvaluationResultRecord.review_id == review_id,
            )
            .order_by(AIOutcomeEvaluationResultRecord.created_at.desc())
        )
        return list(rows)

    async def classify_error(self, **values: Any) -> AIOutcomeErrorClassificationRecord:
        result = await self.session.scalar(
            select(AIOutcomeEvaluationResultRecord).where(
                AIOutcomeEvaluationResultRecord.organization_id == values["organization_id"],
                AIOutcomeEvaluationResultRecord.review_id == values["review_id"],
                AIOutcomeEvaluationResultRecord.id == values["evaluation_result_id"],
            )
        )
        if result is None:
            raise LookupError("AI outcome evaluation result was not found")
        row = AIOutcomeErrorClassificationRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row


def _now_if_missing(value: datetime | None) -> datetime:
    return value or datetime.now(UTC)
