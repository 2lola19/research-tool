from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
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

from backend.app.ai.persistence import AIExecutionRunRecord, AIOutputProposalRecord
from backend.app.ai.screening_domain import (
    AIScreeningAccess,
    AIScreeningAccessType,
    AIScreeningDisagreement,
    AIScreeningMode,
    AIScreeningPolicyVersion,
    AIScreeningProposalLink,
    AIScreeningSuggestion,
    ScreeningEvaluationCase,
    ScreeningEvaluationCaseResult,
    ScreeningEvaluationDataset,
    ScreeningEvaluationPolicy,
    ScreeningEvaluationResult,
    ScreeningReferenceDecision,
    ScreeningReferenceStandard,
)
from backend.app.db.base import Base
from backend.app.db.sequence import insert_next_unique_integer


class AIScreeningPolicyVersionRecord(Base):
    __tablename__ = "ai_screening_policy_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "review_id", "version", name="uq_ai_screening_policy_version"
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_screening_policy_tenant"
        ),
        CheckConstraint("mode IN ('OFF','BLINDED_AI','ASSISTED')", name="ck_ai_screening_mode"),
        CheckConstraint("maximum_batch_size BETWEEN 1 AND 100", name="ck_ai_screening_batch_size"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_screening_policy_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_screening_policy_creator",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(20))
    maximum_batch_size: Mapped[int] = mapped_column(Integer)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIScreeningProposalLinkRecord(Base):
    __tablename__ = "ai_screening_proposal_links"
    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_ai_screening_proposal_link"),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_screening_proposal_link_tenant"
        ),
        CheckConstraint("length(protocol_content_hash) = 64", name="ck_ai_screening_protocol_hash"),
        CheckConstraint(
            "length(eligibility_criteria_hash) = 64", name="ck_ai_screening_eligibility_hash"
        ),
        CheckConstraint(
            "length(exclusion_criteria_hash) = 64", name="ck_ai_screening_exclusion_hash"
        ),
        CheckConstraint("length(citation_content_hash) = 64", name="ck_ai_screening_citation_hash"),
        CheckConstraint(
            "assistance_mode IN ('BLINDED_AI','ASSISTED')",
            name="ck_ai_screening_link_mode",
        ),
        CheckConstraint("task_definition_version > 0", name="ck_ai_screening_task_version"),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_screening_link_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            [
                "ai_execution_runs.id",
                "ai_execution_runs.organization_id",
                "ai_execution_runs.review_id",
            ],
            name="fk_ai_screening_link_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_ai_screening_link_article",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assignment_id", "organization_id", "review_id"],
            [
                "screening_assignments.id",
                "screening_assignments.organization_id",
                "screening_assignments.review_id",
            ],
            name="fk_ai_screening_link_assignment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["protocol_version_id", "organization_id", "review_id"],
            [
                "protocol_versions.id",
                "protocol_versions.organization_id",
                "protocol_versions.review_id",
            ],
            name="fk_ai_screening_link_protocol",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    ai_run_id: Mapped[UUID] = mapped_column()
    article_id: Mapped[UUID] = mapped_column()
    assignment_id: Mapped[UUID] = mapped_column()
    protocol_version_id: Mapped[UUID] = mapped_column()
    protocol_content_hash: Mapped[str] = mapped_column(String(64))
    eligibility_criteria_hash: Mapped[str] = mapped_column(String(64))
    exclusion_criteria_hash: Mapped[str] = mapped_column(String(64))
    citation_content_hash: Mapped[str] = mapped_column(String(64))
    task_definition_version: Mapped[int] = mapped_column(Integer)
    assistance_mode: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIScreeningAccessRecord(Base):
    __tablename__ = "ai_screening_access_events"
    __table_args__ = (
        UniqueConstraint(
            "proposal_id", "reviewer_user_id", "access_type", name="uq_ai_screening_access"
        ),
        CheckConstraint(
            "access_type IN ('ASSISTED_VIEW','POST_DECISION_REVEAL')",
            name="ck_ai_screening_access_type",
        ),
        CheckConstraint(
            "(access_type = 'ASSISTED_VIEW' AND screening_decision_id IS NULL) OR "
            "(access_type = 'POST_DECISION_REVEAL' AND screening_decision_id IS NOT NULL)",
            name="ck_ai_screening_reveal_decision",
        ),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_screening_access_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assignment_id", "organization_id", "review_id"],
            [
                "screening_assignments.id",
                "screening_assignments.organization_id",
                "screening_assignments.review_id",
            ],
            name="fk_ai_screening_access_assignment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reviewer_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_screening_access_reviewer",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["screening_decision_id"],
            ["screening_decisions.id"],
            name="fk_ai_screening_access_decision",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    assignment_id: Mapped[UUID] = mapped_column()
    reviewer_user_id: Mapped[UUID] = mapped_column()
    access_type: Mapped[str] = mapped_column(String(30))
    screening_decision_id: Mapped[UUID | None] = mapped_column(nullable=True)
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AIScreeningDecisionLinkRecord(Base):
    __tablename__ = "ai_screening_decision_links"
    __table_args__ = (
        UniqueConstraint("screening_decision_id", name="uq_ai_screening_decision_link"),
        CheckConstraint(
            "interaction IN ('UNSEEN','VIEWED','ACCEPTED','OVERRIDDEN','DISAGREED')",
            name="ck_ai_screening_interaction",
        ),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_screening_decision_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["screening_decision_id"],
            ["screening_decisions.id"],
            name="fk_ai_screening_decision_canonical",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "human_reviewer_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_screening_decision_reviewer",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    screening_decision_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    human_reviewer_user_id: Mapped[UUID] = mapped_column()
    interaction: Mapped[str] = mapped_column(String(20))
    disagreement: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScreeningEvaluationDatasetRecord(Base):
    __tablename__ = "ai_screening_evaluation_datasets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "review_id",
            "logical_key",
            "version",
            name="uq_ai_screening_dataset_version",
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_screening_dataset_tenant"
        ),
        CheckConstraint(
            "reference_standard IN ('ADJUDICATED_TITLE_ABSTRACT','CONSENSUS_DECISION',"
            "'FINAL_FULL_TEXT_INCLUSION','CURATED_DATASET')",
            name="ck_ai_screening_reference_standard",
        ),
        CheckConstraint("length(content_hash) = 64", name="ck_ai_screening_dataset_hash"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_screening_dataset_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["protocol_version_id", "organization_id", "review_id"],
            [
                "protocol_versions.id",
                "protocol_versions.organization_id",
                "protocol_versions.review_id",
            ],
            name="fk_ai_screening_dataset_protocol",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_screening_dataset_creator",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    logical_key: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer)
    protocol_version_id: Mapped[UUID] = mapped_column()
    name: Mapped[str] = mapped_column(String(300))
    reference_standard: Mapped[str] = mapped_column(String(50))
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScreeningEvaluationCaseRecord(Base):
    __tablename__ = "ai_screening_evaluation_cases"
    __table_args__ = (
        UniqueConstraint("dataset_id", "ordinal", name="uq_ai_screening_case_ordinal"),
        UniqueConstraint("dataset_id", "article_id", name="uq_ai_screening_case_article"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_screening_case_tenant"),
        CheckConstraint(
            "reference_decision IN ('RETAIN','EXCLUDE')",
            name="ck_ai_screening_reference_decision",
        ),
        ForeignKeyConstraint(
            ["dataset_id", "organization_id", "review_id"],
            [
                "ai_screening_evaluation_datasets.id",
                "ai_screening_evaluation_datasets.organization_id",
                "ai_screening_evaluation_datasets.review_id",
            ],
            name="fk_ai_screening_case_dataset",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_ai_screening_case_article",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    article_id: Mapped[UUID] = mapped_column()
    ordinal: Mapped[int] = mapped_column(Integer)
    reference_decision: Mapped[str] = mapped_column(String(20))
    reference_source_type: Mapped[str] = mapped_column(String(50))
    reference_source_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScreeningEvaluationResultRecord(Base):
    __tablename__ = "ai_screening_evaluation_results"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_screening_result_tenant"
        ),
        CheckConstraint(
            "evaluation_policy IN ('CONSERVATIVE','STRICT_MODEL_DECISION','COVERAGE_ONLY')",
            name="ck_ai_screening_evaluation_policy",
        ),
        CheckConstraint("task_definition_version > 0", name="ck_ai_screening_result_task_version"),
        CheckConstraint("length(content_hash) = 64", name="ck_ai_screening_result_hash"),
        ForeignKeyConstraint(
            ["dataset_id", "organization_id", "review_id"],
            [
                "ai_screening_evaluation_datasets.id",
                "ai_screening_evaluation_datasets.organization_id",
                "ai_screening_evaluation_datasets.review_id",
            ],
            name="fk_ai_screening_result_dataset",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["protocol_version_id", "organization_id", "review_id"],
            [
                "protocol_versions.id",
                "protocol_versions.organization_id",
                "protocol_versions.review_id",
            ],
            name="fk_ai_screening_result_protocol",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["prompt_version_id", "organization_id"],
            ["ai_prompt_template_versions.id", "ai_prompt_template_versions.organization_id"],
            name="fk_ai_screening_result_prompt",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["model_version_id", "organization_id"],
            ["ai_model_versions.id", "ai_model_versions.organization_id"],
            name="fk_ai_screening_result_model",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_screening_result_creator",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    protocol_version_id: Mapped[UUID] = mapped_column()
    prompt_version_id: Mapped[UUID] = mapped_column()
    model_version_id: Mapped[UUID] = mapped_column()
    task_definition_version: Mapped[int] = mapped_column(Integer)
    evaluation_policy: Mapped[str] = mapped_column(String(30))
    metric_version: Mapped[str] = mapped_column(String(80))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    calibration: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    threshold_simulation: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    high_risk_disagreements: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScreeningEvaluationCaseResultRecord(Base):
    __tablename__ = "ai_screening_evaluation_case_results"
    __table_args__ = (
        UniqueConstraint("evaluation_result_id", "case_id", name="uq_ai_screening_case_result"),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_screening_case_result_tenant"
        ),
        CheckConstraint(
            "suggestion IN ('INCLUDE','EXCLUDE','MAYBE','ABSTAIN')",
            name="ck_ai_screening_case_suggestion",
        ),
        CheckConstraint(
            "model_reported_confidence >= 0 AND model_reported_confidence <= 1",
            name="ck_ai_screening_case_confidence",
        ),
        CheckConstraint(
            "reference_decision IN ('RETAIN','EXCLUDE')",
            name="ck_ai_screening_case_result_reference",
        ),
        ForeignKeyConstraint(
            ["evaluation_result_id", "organization_id", "review_id"],
            [
                "ai_screening_evaluation_results.id",
                "ai_screening_evaluation_results.organization_id",
                "ai_screening_evaluation_results.review_id",
            ],
            name="fk_ai_screening_case_result_result",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["case_id", "organization_id", "review_id"],
            [
                "ai_screening_evaluation_cases.id",
                "ai_screening_evaluation_cases.organization_id",
                "ai_screening_evaluation_cases.review_id",
            ],
            name="fk_ai_screening_case_result_case",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_screening_case_result_proposal",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    evaluation_result_id: Mapped[UUID] = mapped_column()
    case_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    suggestion: Mapped[str] = mapped_column(String(20))
    reference_decision: Mapped[str] = mapped_column(String(20))
    model_reported_confidence: Mapped[float] = mapped_column(Float)
    disagreement: Mapped[str] = mapped_column(String(50))


class AIScreeningErrorClassificationRecord(Base):
    __tablename__ = "ai_screening_error_classifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["case_result_id", "organization_id", "review_id"],
            [
                "ai_screening_evaluation_case_results.id",
                "ai_screening_evaluation_case_results.organization_id",
                "ai_screening_evaluation_case_results.review_id",
            ],
            name="fk_ai_screening_error_case",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "classified_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_screening_error_actor",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_result_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    category: Mapped[str] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    classified_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _reject_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("AI screening policies, proposals, reveals, and evaluations are immutable")


for _immutable in (
    AIScreeningPolicyVersionRecord,
    AIScreeningProposalLinkRecord,
    AIScreeningAccessRecord,
    AIScreeningDecisionLinkRecord,
    ScreeningEvaluationDatasetRecord,
    ScreeningEvaluationCaseRecord,
    ScreeningEvaluationResultRecord,
    ScreeningEvaluationCaseResultRecord,
    AIScreeningErrorClassificationRecord,
):
    event.listen(_immutable, "before_update", _reject_mutation)
    event.listen(_immutable, "before_delete", _reject_mutation)


class SqlAlchemyAIScreeningRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def current_policy(
        self, organization_id: UUID, review_id: UUID
    ) -> AIScreeningPolicyVersion | None:
        row = await self.session.scalar(
            select(AIScreeningPolicyVersionRecord)
            .where(
                AIScreeningPolicyVersionRecord.organization_id == organization_id,
                AIScreeningPolicyVersionRecord.review_id == review_id,
            )
            .order_by(AIScreeningPolicyVersionRecord.version.desc())
            .limit(1)
        )
        return _policy(row) if row else None

    async def create_policy(self, **values: Any) -> AIScreeningPolicyVersion:
        async def next_version() -> int:
            value = await self.session.scalar(
                select(func.max(AIScreeningPolicyVersionRecord.version)).where(
                    AIScreeningPolicyVersionRecord.organization_id == values["organization_id"],
                    AIScreeningPolicyVersionRecord.review_id == values["review_id"],
                )
            )
            return int(value or 0) + 1

        row = await insert_next_unique_integer(
            self.session,
            next_version,
            lambda version: AIScreeningPolicyVersionRecord(**values, version=version),
        )
        await self.session.refresh(row)
        return _policy(row)

    async def create_proposal_link(self, **values: Any) -> AIScreeningProposalLink:
        row = AIScreeningProposalLinkRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _proposal_link(row)

    async def get_proposal_link(
        self, organization_id: UUID, review_id: UUID, proposal_id: UUID
    ) -> AIScreeningProposalLink | None:
        row = await self.session.scalar(
            select(AIScreeningProposalLinkRecord).where(
                AIScreeningProposalLinkRecord.organization_id == organization_id,
                AIScreeningProposalLinkRecord.review_id == review_id,
                AIScreeningProposalLinkRecord.proposal_id == proposal_id,
            )
        )
        return _proposal_link(row) if row else None

    async def latest_article_link(
        self, organization_id: UUID, review_id: UUID, article_id: UUID
    ) -> AIScreeningProposalLink | None:
        row = await self.session.scalar(
            select(AIScreeningProposalLinkRecord)
            .where(
                AIScreeningProposalLinkRecord.organization_id == organization_id,
                AIScreeningProposalLinkRecord.review_id == review_id,
                AIScreeningProposalLinkRecord.article_id == article_id,
            )
            .order_by(AIScreeningProposalLinkRecord.created_at.desc())
            .limit(1)
        )
        return _proposal_link(row) if row else None

    async def latest_assignment_link(
        self, organization_id: UUID, review_id: UUID, assignment_id: UUID
    ) -> AIScreeningProposalLink | None:
        row = await self.session.scalar(
            select(AIScreeningProposalLinkRecord)
            .where(
                AIScreeningProposalLinkRecord.organization_id == organization_id,
                AIScreeningProposalLinkRecord.review_id == review_id,
                AIScreeningProposalLinkRecord.assignment_id == assignment_id,
            )
            .order_by(AIScreeningProposalLinkRecord.created_at.desc())
            .limit(1)
        )
        return _proposal_link(row) if row else None

    async def record_access(self, **values: Any) -> AIScreeningAccess:
        existing = await self.session.scalar(
            select(AIScreeningAccessRecord).where(
                AIScreeningAccessRecord.organization_id == values["organization_id"],
                AIScreeningAccessRecord.review_id == values["review_id"],
                AIScreeningAccessRecord.proposal_id == values["proposal_id"],
                AIScreeningAccessRecord.reviewer_user_id == values["reviewer_user_id"],
                AIScreeningAccessRecord.access_type == values["access_type"],
            )
        )
        if existing:
            return _access(existing)
        row = AIScreeningAccessRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _access(row)

    async def get_decision_link(
        self, organization_id: UUID, review_id: UUID, screening_decision_id: UUID
    ) -> AIScreeningDecisionLinkRecord | None:
        return cast(
            AIScreeningDecisionLinkRecord | None,
            await self.session.scalar(
                select(AIScreeningDecisionLinkRecord).where(
                    AIScreeningDecisionLinkRecord.organization_id == organization_id,
                    AIScreeningDecisionLinkRecord.review_id == review_id,
                    AIScreeningDecisionLinkRecord.screening_decision_id == screening_decision_id,
                )
            ),
        )

    async def link_decision(self, **values: Any) -> None:
        if await self.get_decision_link(
            values["organization_id"], values["review_id"], values["screening_decision_id"]
        ):
            return
        self.session.add(AIScreeningDecisionLinkRecord(**values))
        await self.session.flush()

    async def create_dataset(
        self, *, cases: list[dict[str, Any]], **values: Any
    ) -> ScreeningEvaluationDataset:
        async def next_version() -> int:
            value = await self.session.scalar(
                select(func.max(ScreeningEvaluationDatasetRecord.version)).where(
                    ScreeningEvaluationDatasetRecord.organization_id == values["organization_id"],
                    ScreeningEvaluationDatasetRecord.review_id == values["review_id"],
                    ScreeningEvaluationDatasetRecord.logical_key == values["logical_key"],
                )
            )
            return int(value or 0) + 1

        row = await insert_next_unique_integer(
            self.session,
            next_version,
            lambda version: ScreeningEvaluationDatasetRecord(**values, version=version),
        )
        await self.session.flush()
        for ordinal, case in enumerate(cases, start=1):
            self.session.add(
                ScreeningEvaluationCaseRecord(
                    dataset_id=row.id,
                    organization_id=row.organization_id,
                    review_id=row.review_id,
                    ordinal=ordinal,
                    **case,
                )
            )
        await self.session.flush()
        await self.session.refresh(row)
        return _dataset(row)

    async def get_dataset(
        self, organization_id: UUID, review_id: UUID, dataset_id: UUID
    ) -> ScreeningEvaluationDataset | None:
        row = await self.session.scalar(
            select(ScreeningEvaluationDatasetRecord).where(
                ScreeningEvaluationDatasetRecord.organization_id == organization_id,
                ScreeningEvaluationDatasetRecord.review_id == review_id,
                ScreeningEvaluationDatasetRecord.id == dataset_id,
            )
        )
        return _dataset(row) if row else None

    async def list_datasets(
        self, organization_id: UUID, review_id: UUID
    ) -> list[ScreeningEvaluationDataset]:
        rows = await self.session.scalars(
            select(ScreeningEvaluationDatasetRecord)
            .where(
                ScreeningEvaluationDatasetRecord.organization_id == organization_id,
                ScreeningEvaluationDatasetRecord.review_id == review_id,
            )
            .order_by(
                ScreeningEvaluationDatasetRecord.logical_key,
                ScreeningEvaluationDatasetRecord.version,
            )
        )
        return [_dataset(row) for row in rows]

    async def list_cases(
        self, organization_id: UUID, review_id: UUID, dataset_id: UUID
    ) -> list[ScreeningEvaluationCase]:
        rows = await self.session.scalars(
            select(ScreeningEvaluationCaseRecord)
            .where(
                ScreeningEvaluationCaseRecord.organization_id == organization_id,
                ScreeningEvaluationCaseRecord.review_id == review_id,
                ScreeningEvaluationCaseRecord.dataset_id == dataset_id,
            )
            .order_by(ScreeningEvaluationCaseRecord.ordinal)
        )
        return [_case(row) for row in rows]

    async def matching_proposals(
        self,
        organization_id: UUID,
        review_id: UUID,
        protocol_version_id: UUID,
        prompt_version_id: UUID,
        model_version_id: UUID,
        article_ids: list[UUID],
    ) -> dict[UUID, tuple[AIOutputProposalRecord, AIScreeningProposalLinkRecord]]:
        rows = (
            await self.session.execute(
                select(AIOutputProposalRecord, AIScreeningProposalLinkRecord)
                .join(
                    AIScreeningProposalLinkRecord,
                    AIScreeningProposalLinkRecord.proposal_id == AIOutputProposalRecord.id,
                )
                .join(
                    AIExecutionRunRecord,
                    AIExecutionRunRecord.id == AIOutputProposalRecord.ai_run_id,
                )
                .where(
                    AIOutputProposalRecord.organization_id == organization_id,
                    AIOutputProposalRecord.review_id == review_id,
                    AIExecutionRunRecord.organization_id == organization_id,
                    AIExecutionRunRecord.review_id == review_id,
                    AIOutputProposalRecord.task_type == "SCREENING_SUGGESTION",
                    AIScreeningProposalLinkRecord.protocol_version_id == protocol_version_id,
                    AIExecutionRunRecord.prompt_version_id == prompt_version_id,
                    AIExecutionRunRecord.model_version_id == model_version_id,
                    AIScreeningProposalLinkRecord.article_id.in_(article_ids),
                )
                .order_by(AIScreeningProposalLinkRecord.created_at.desc())
            )
        ).all()
        result: dict[UUID, tuple[AIOutputProposalRecord, AIScreeningProposalLinkRecord]] = {}
        for proposal, link in rows:
            result.setdefault(link.article_id, (proposal, link))
        return result

    async def latest_screening_dimensions(
        self,
        organization_id: UUID,
        review_id: UUID,
        protocol_version_id: UUID,
        article_ids: list[UUID],
    ) -> tuple[UUID, UUID] | None:
        row = (
            await self.session.execute(
                select(
                    AIExecutionRunRecord.prompt_version_id, AIExecutionRunRecord.model_version_id
                )
                .join(
                    AIScreeningProposalLinkRecord,
                    AIScreeningProposalLinkRecord.ai_run_id == AIExecutionRunRecord.id,
                )
                .where(
                    AIExecutionRunRecord.organization_id == organization_id,
                    AIExecutionRunRecord.review_id == review_id,
                    AIExecutionRunRecord.task_type == "SCREENING_SUGGESTION",
                    AIScreeningProposalLinkRecord.organization_id == organization_id,
                    AIScreeningProposalLinkRecord.review_id == review_id,
                    AIScreeningProposalLinkRecord.protocol_version_id == protocol_version_id,
                    AIScreeningProposalLinkRecord.article_id.in_(article_ids),
                )
                .order_by(AIScreeningProposalLinkRecord.created_at.desc())
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        return row[0], row[1]

    async def create_result(
        self, *, case_results: list[dict[str, Any]], **values: Any
    ) -> ScreeningEvaluationResult:
        row = ScreeningEvaluationResultRecord(**values)
        self.session.add(row)
        await self.session.flush()
        for item in case_results:
            self.session.add(
                ScreeningEvaluationCaseResultRecord(
                    evaluation_result_id=row.id,
                    organization_id=row.organization_id,
                    review_id=row.review_id,
                    **item,
                )
            )
        await self.session.flush()
        await self.session.refresh(row)
        return _result(row)

    async def list_results(
        self, organization_id: UUID, review_id: UUID
    ) -> list[ScreeningEvaluationResult]:
        rows = await self.session.scalars(
            select(ScreeningEvaluationResultRecord)
            .where(
                ScreeningEvaluationResultRecord.organization_id == organization_id,
                ScreeningEvaluationResultRecord.review_id == review_id,
            )
            .order_by(ScreeningEvaluationResultRecord.created_at.desc())
        )
        return [_result(row) for row in rows]

    async def get_result(
        self, organization_id: UUID, review_id: UUID, result_id: UUID
    ) -> ScreeningEvaluationResult | None:
        row = await self.session.scalar(
            select(ScreeningEvaluationResultRecord).where(
                ScreeningEvaluationResultRecord.organization_id == organization_id,
                ScreeningEvaluationResultRecord.review_id == review_id,
                ScreeningEvaluationResultRecord.id == result_id,
            )
        )
        return _result(row) if row else None

    async def list_case_results(
        self, organization_id: UUID, review_id: UUID, result_id: UUID
    ) -> list[ScreeningEvaluationCaseResult]:
        rows = await self.session.scalars(
            select(ScreeningEvaluationCaseResultRecord)
            .where(
                ScreeningEvaluationCaseResultRecord.organization_id == organization_id,
                ScreeningEvaluationCaseResultRecord.review_id == review_id,
                ScreeningEvaluationCaseResultRecord.evaluation_result_id == result_id,
            )
            .order_by(ScreeningEvaluationCaseResultRecord.id)
        )
        return [_case_result(row) for row in rows]

    async def get_case_result(
        self, organization_id: UUID, review_id: UUID, case_result_id: UUID
    ) -> ScreeningEvaluationCaseResult | None:
        row = await self.session.scalar(
            select(ScreeningEvaluationCaseResultRecord).where(
                ScreeningEvaluationCaseResultRecord.organization_id == organization_id,
                ScreeningEvaluationCaseResultRecord.review_id == review_id,
                ScreeningEvaluationCaseResultRecord.id == case_result_id,
            )
        )
        return _case_result(row) if row else None

    async def classify_error(self, **values: Any) -> None:
        self.session.add(AIScreeningErrorClassificationRecord(**values))
        await self.session.flush()


def _policy(row: AIScreeningPolicyVersionRecord) -> AIScreeningPolicyVersion:
    return AIScreeningPolicyVersion(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        version=row.version,
        mode=AIScreeningMode(row.mode),
        maximum_batch_size=row.maximum_batch_size,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at or datetime.now(UTC),
    )


def _proposal_link(row: AIScreeningProposalLinkRecord) -> AIScreeningProposalLink:
    return AIScreeningProposalLink(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        proposal_id=row.proposal_id,
        ai_run_id=row.ai_run_id,
        article_id=row.article_id,
        assignment_id=row.assignment_id,
        protocol_version_id=row.protocol_version_id,
        protocol_content_hash=row.protocol_content_hash,
        eligibility_criteria_hash=row.eligibility_criteria_hash,
        exclusion_criteria_hash=row.exclusion_criteria_hash,
        citation_content_hash=row.citation_content_hash,
        task_definition_version=row.task_definition_version,
        assistance_mode=AIScreeningMode(row.assistance_mode),
        created_at=row.created_at or datetime.now(UTC),
    )


def _access(row: AIScreeningAccessRecord) -> AIScreeningAccess:
    return AIScreeningAccess(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        proposal_id=row.proposal_id,
        assignment_id=row.assignment_id,
        reviewer_user_id=row.reviewer_user_id,
        access_type=AIScreeningAccessType(row.access_type),
        screening_decision_id=row.screening_decision_id,
        accessed_at=row.accessed_at or datetime.now(UTC),
    )


def _dataset(row: ScreeningEvaluationDatasetRecord) -> ScreeningEvaluationDataset:
    return ScreeningEvaluationDataset(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        logical_key=row.logical_key,
        version=row.version,
        protocol_version_id=row.protocol_version_id,
        name=row.name,
        reference_standard=ScreeningReferenceStandard(row.reference_standard),
        content_hash=row.content_hash,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at or datetime.now(UTC),
    )


def _case(row: ScreeningEvaluationCaseRecord) -> ScreeningEvaluationCase:
    return ScreeningEvaluationCase(
        id=row.id,
        dataset_id=row.dataset_id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        article_id=row.article_id,
        ordinal=row.ordinal,
        reference_decision=ScreeningReferenceDecision(row.reference_decision),
        reference_source_type=ScreeningReferenceStandard(row.reference_source_type),
        reference_source_id=row.reference_source_id,
        created_at=row.created_at or datetime.now(UTC),
    )


def _result(row: ScreeningEvaluationResultRecord) -> ScreeningEvaluationResult:
    return ScreeningEvaluationResult(
        id=row.id,
        dataset_id=row.dataset_id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        protocol_version_id=row.protocol_version_id,
        prompt_version_id=row.prompt_version_id,
        model_version_id=row.model_version_id,
        task_definition_version=row.task_definition_version,
        evaluation_policy=ScreeningEvaluationPolicy(row.evaluation_policy),
        metric_version=row.metric_version,
        metrics=row.metrics,
        calibration=row.calibration,
        threshold_simulation=row.threshold_simulation,
        high_risk_disagreements=row.high_risk_disagreements,
        content_hash=row.content_hash,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at or datetime.now(UTC),
    )


def _case_result(row: ScreeningEvaluationCaseResultRecord) -> ScreeningEvaluationCaseResult:
    return ScreeningEvaluationCaseResult(
        id=row.id,
        evaluation_result_id=row.evaluation_result_id,
        case_id=row.case_id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        proposal_id=row.proposal_id,
        suggestion=AIScreeningSuggestion(row.suggestion),
        reference_decision=ScreeningReferenceDecision(row.reference_decision),
        model_reported_confidence=row.model_reported_confidence,
        disagreement=AIScreeningDisagreement(row.disagreement),
    )
