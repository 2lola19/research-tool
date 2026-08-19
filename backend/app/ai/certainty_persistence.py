from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
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

from backend.app.ai.certainty_domain import AICertaintyPolicy, AICertaintyProposalLink
from backend.app.db.base import Base
from backend.app.db.sequence import insert_next_unique_integer


class AICertaintyPolicyRecord(Base):
    __tablename__ = "ai_certainty_policy_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "review_id", "version", name="uq_ai_certainty_policy_version"
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_certainty_policy_tenant"
        ),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_certainty_policy_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_certainty_policy_creator",
            ondelete="RESTRICT",
        ),
        CheckConstraint("maximum_batch_size BETWEEN 1 AND 100", name="ck_ai_certainty_batch_size"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    maximum_batch_size: Mapped[int] = mapped_column(Integer)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AICertaintyProposalLinkRecord(Base):
    __tablename__ = "ai_certainty_proposal_links"
    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_ai_certainty_proposal"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_certainty_link_tenant"),
        Index(
            "ix_ai_certainty_assessment",
            "organization_id",
            "review_id",
            "assessment_id",
            "created_at",
        ),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_certainty_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            [
                "ai_execution_runs.id",
                "ai_execution_runs.organization_id",
                "ai_execution_runs.review_id",
            ],
            name="fk_ai_certainty_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assessment_id", "organization_id", "review_id"],
            [
                "certainty_assessments.id",
                "certainty_assessments.organization_id",
                "certainty_assessments.review_id",
            ],
            name="fk_ai_certainty_assessment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["outcome_version_id", "organization_id", "review_id"],
            [
                "outcome_definition_versions.id",
                "outcome_definition_versions.organization_id",
                "outcome_definition_versions.review_id",
            ],
            name="fk_ai_certainty_outcome",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["framework_version_id", "organization_id", "review_id"],
            [
                "certainty_framework_versions.id",
                "certainty_framework_versions.organization_id",
                "certainty_framework_versions.review_id",
            ],
            name="fk_ai_certainty_framework",
            ondelete="RESTRICT",
        ),
        CheckConstraint("length(outcome_version_hash) = 64", name="ck_ai_certainty_outcome_hash"),
        CheckConstraint(
            "length(framework_version_hash) = 64", name="ck_ai_certainty_framework_hash"
        ),
        CheckConstraint(
            "length(assessment_snapshot_hash) = 64", name="ck_ai_certainty_assessment_hash"
        ),
        CheckConstraint("length(evidence_profile_hash) = 64", name="ck_ai_certainty_profile_hash"),
        CheckConstraint("length(chunk_manifest_hash) = 64", name="ck_ai_certainty_chunk_hash"),
        CheckConstraint("length(selected_text_hash) = 64", name="ck_ai_certainty_text_hash"),
        CheckConstraint("task_definition_version > 0", name="ck_ai_certainty_task_version"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    ai_run_id: Mapped[UUID] = mapped_column()
    assessment_id: Mapped[UUID] = mapped_column()
    outcome_version_id: Mapped[UUID] = mapped_column()
    outcome_version_hash: Mapped[str] = mapped_column(String(64))
    framework_version_id: Mapped[UUID] = mapped_column()
    framework_version_hash: Mapped[str] = mapped_column(String(64))
    assessment_snapshot_hash: Mapped[str] = mapped_column(String(64))
    evidence_profile_hash: Mapped[str] = mapped_column(String(64))
    task_definition_version: Mapped[int] = mapped_column(Integer)
    source_manifest: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    selected_chunk_ids: Mapped[list[str]] = mapped_column(JSON)
    omitted_chunks: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    selection_method: Mapped[str] = mapped_column(String(120))
    chunk_manifest_hash: Mapped[str] = mapped_column(String(64))
    selected_text_hash: Mapped[str] = mapped_column(String(64))
    validation_results: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AICertaintyAccessRecord(Base):
    __tablename__ = "ai_certainty_access_events"
    __table_args__ = (
        UniqueConstraint(
            "proposal_id", "reviewer_user_id", "access_type", name="uq_ai_certainty_access"
        ),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_certainty_access_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reviewer_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_certainty_access_reviewer",
            ondelete="RESTRICT",
        ),
        CheckConstraint("access_type IN ('HUMAN_REVIEW')", name="ck_ai_certainty_access_type"),
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


class AICertaintyReviewRecord(Base):
    __tablename__ = "ai_certainty_human_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_certainty_human_review_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assessment_id", "organization_id", "review_id"],
            [
                "certainty_assessments.id",
                "certainty_assessments.organization_id",
                "certainty_assessments.review_id",
            ],
            name="fk_ai_certainty_human_review_assessment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reviewer_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_certainty_human_review_reviewer",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "action IN ('ACCEPTED','EDITED','REJECTED','UNRESOLVED')",
            name="ck_ai_certainty_review_action",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    assessment_id: Mapped[UUID] = mapped_column()
    action: Mapped[str] = mapped_column(String(20))
    canonical_action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    canonical_subject_id: Mapped[UUID | None] = mapped_column(nullable=True)
    ai_candidate_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    human_payload_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AICertaintyEvaluationDatasetRecord(Base):
    __tablename__ = "ai_certainty_evaluation_datasets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "review_id",
            "logical_key",
            "version",
            name="uq_ai_certainty_dataset_version",
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_certainty_dataset_tenant"
        ),
        CheckConstraint(
            "reference_standard IN ('HUMAN_RATIONALE','CURATED_GOLD','FINAL_CANONICAL')",
            name="ck_ai_certainty_reference_standard",
        ),
        CheckConstraint("length(content_hash) = 64", name="ck_ai_certainty_dataset_hash"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_certainty_dataset_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_certainty_dataset_creator",
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


class AICertaintyEvaluationResultRecord(Base):
    __tablename__ = "ai_certainty_evaluation_results"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_certainty_result_tenant"
        ),
        ForeignKeyConstraint(
            ["dataset_id", "organization_id", "review_id"],
            [
                "ai_certainty_evaluation_datasets.id",
                "ai_certainty_evaluation_datasets.organization_id",
                "ai_certainty_evaluation_datasets.review_id",
            ],
            name="fk_ai_certainty_result_dataset",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_certainty_result_creator",
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


class AICertaintyErrorClassificationRecord(Base):
    __tablename__ = "ai_certainty_error_classifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["evaluation_result_id", "organization_id", "review_id"],
            [
                "ai_certainty_evaluation_results.id",
                "ai_certainty_evaluation_results.organization_id",
                "ai_certainty_evaluation_results.review_id",
            ],
            name="fk_ai_certainty_error_result",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "classified_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_certainty_error_classifier",
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


def _policy(row: AICertaintyPolicyRecord) -> AICertaintyPolicy:
    return AICertaintyPolicy(
        row.id,
        row.organization_id,
        row.review_id,
        row.version,
        row.maximum_batch_size,
        row.created_by_user_id,
    )


def _link(row: AICertaintyProposalLinkRecord) -> AICertaintyProposalLink:
    return AICertaintyProposalLink(
        row.id,
        row.organization_id,
        row.review_id,
        row.proposal_id,
        row.ai_run_id,
        row.assessment_id,
        row.outcome_version_id,
        row.outcome_version_hash,
        row.framework_version_id,
        row.framework_version_hash,
        row.assessment_snapshot_hash,
        row.evidence_profile_hash,
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
    raise TypeError("AI certainty records are append-only")


for _immutable in (
    AICertaintyPolicyRecord,
    AICertaintyProposalLinkRecord,
    AICertaintyAccessRecord,
    AICertaintyReviewRecord,
    AICertaintyEvaluationDatasetRecord,
    AICertaintyEvaluationResultRecord,
    AICertaintyErrorClassificationRecord,
):
    event.listen(_immutable, "before_update", _reject_mutation)
    event.listen(_immutable, "before_delete", _reject_mutation)


class SqlAlchemyAICertaintyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def current_policy(
        self, organization_id: UUID, review_id: UUID
    ) -> AICertaintyPolicy | None:
        row = await self.session.scalar(
            select(AICertaintyPolicyRecord)
            .where(
                AICertaintyPolicyRecord.organization_id == organization_id,
                AICertaintyPolicyRecord.review_id == review_id,
            )
            .order_by(AICertaintyPolicyRecord.version.desc())
            .limit(1)
        )
        return _policy(row) if row else None

    async def create_policy(self, **values: Any) -> AICertaintyPolicy:
        async def next_version() -> int:
            current = await self.session.scalar(
                select(func.max(AICertaintyPolicyRecord.version)).where(
                    AICertaintyPolicyRecord.organization_id == values["organization_id"],
                    AICertaintyPolicyRecord.review_id == values["review_id"],
                )
            )
            return int(current or 0) + 1

        row = await insert_next_unique_integer(
            self.session,
            next_version,
            lambda version: AICertaintyPolicyRecord(**values, version=version),
        )
        await self.session.refresh(row)
        return _policy(row)

    async def create_link(self, **values: Any) -> AICertaintyProposalLink:
        row = AICertaintyProposalLinkRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _link(row)

    async def get_link(
        self, organization_id: UUID, review_id: UUID, proposal_id: UUID
    ) -> AICertaintyProposalLink | None:
        row = await self.session.scalar(
            select(AICertaintyProposalLinkRecord).where(
                AICertaintyProposalLinkRecord.organization_id == organization_id,
                AICertaintyProposalLinkRecord.review_id == review_id,
                AICertaintyProposalLinkRecord.proposal_id == proposal_id,
            )
        )
        return _link(row) if row else None

    async def list_links(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AICertaintyProposalLink]:
        rows = await self.session.scalars(
            select(AICertaintyProposalLinkRecord)
            .where(
                AICertaintyProposalLinkRecord.organization_id == organization_id,
                AICertaintyProposalLinkRecord.review_id == review_id,
            )
            .order_by(AICertaintyProposalLinkRecord.created_at.desc())
        )
        return [_link(row) for row in rows]

    async def record_access(self, **values: Any) -> None:
        existing = await self.session.scalar(
            select(AICertaintyAccessRecord).where(
                AICertaintyAccessRecord.organization_id == values["organization_id"],
                AICertaintyAccessRecord.review_id == values["review_id"],
                AICertaintyAccessRecord.proposal_id == values["proposal_id"],
                AICertaintyAccessRecord.reviewer_user_id == values["reviewer_user_id"],
                AICertaintyAccessRecord.access_type == values["access_type"],
            )
        )
        if existing is None:
            self.session.add(AICertaintyAccessRecord(**values))
            await self.session.flush()

    async def record_review(self, **values: Any) -> AICertaintyReviewRecord:
        row = AICertaintyReviewRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def create_dataset(self, **values: Any) -> AICertaintyEvaluationDatasetRecord:
        async def next_version() -> int:
            current = await self.session.scalar(
                select(func.max(AICertaintyEvaluationDatasetRecord.version)).where(
                    AICertaintyEvaluationDatasetRecord.organization_id == values["organization_id"],
                    AICertaintyEvaluationDatasetRecord.review_id == values["review_id"],
                    AICertaintyEvaluationDatasetRecord.logical_key == values["logical_key"],
                )
            )
            return int(current or 0) + 1

        row = await insert_next_unique_integer(
            self.session,
            next_version,
            lambda version: AICertaintyEvaluationDatasetRecord(**values, version=version),
        )
        await self.session.refresh(row)
        return row

    async def list_datasets(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AICertaintyEvaluationDatasetRecord]:
        rows = await self.session.scalars(
            select(AICertaintyEvaluationDatasetRecord)
            .where(
                AICertaintyEvaluationDatasetRecord.organization_id == organization_id,
                AICertaintyEvaluationDatasetRecord.review_id == review_id,
            )
            .order_by(AICertaintyEvaluationDatasetRecord.created_at.desc())
        )
        return list(rows)

    async def get_dataset(
        self, organization_id: UUID, review_id: UUID, dataset_id: UUID
    ) -> AICertaintyEvaluationDatasetRecord | None:
        return cast(
            AICertaintyEvaluationDatasetRecord | None,
            await self.session.scalar(
                select(AICertaintyEvaluationDatasetRecord).where(
                    AICertaintyEvaluationDatasetRecord.organization_id == organization_id,
                    AICertaintyEvaluationDatasetRecord.review_id == review_id,
                    AICertaintyEvaluationDatasetRecord.id == dataset_id,
                )
            ),
        )

    async def create_result(self, **values: Any) -> AICertaintyEvaluationResultRecord:
        row = AICertaintyEvaluationResultRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def list_results(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AICertaintyEvaluationResultRecord]:
        rows = await self.session.scalars(
            select(AICertaintyEvaluationResultRecord)
            .where(
                AICertaintyEvaluationResultRecord.organization_id == organization_id,
                AICertaintyEvaluationResultRecord.review_id == review_id,
            )
            .order_by(AICertaintyEvaluationResultRecord.created_at.desc())
        )
        return list(rows)

    async def get_result(
        self, organization_id: UUID, review_id: UUID, result_id: UUID
    ) -> AICertaintyEvaluationResultRecord | None:
        return cast(
            AICertaintyEvaluationResultRecord | None,
            await self.session.scalar(
                select(AICertaintyEvaluationResultRecord).where(
                    AICertaintyEvaluationResultRecord.organization_id == organization_id,
                    AICertaintyEvaluationResultRecord.review_id == review_id,
                    AICertaintyEvaluationResultRecord.id == result_id,
                )
            ),
        )

    async def classify_error(self, **values: Any) -> AICertaintyErrorClassificationRecord:
        result = await self.get_result(
            values["organization_id"], values["review_id"], values["evaluation_result_id"]
        )
        if result is None:
            raise LookupError("AI certainty evaluation result was not found")
        row = AICertaintyErrorClassificationRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row
