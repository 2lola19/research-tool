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

from backend.app.ai.full_text_domain import (
    AIFullTextProposalLink,
    FullTextDocumentRole,
    FullTextEvaluationCase,
    FullTextEvaluationDataset,
    FullTextReferenceStandard,
)
from backend.app.ai.persistence import AIExecutionRunRecord, AIOutputProposalRecord
from backend.app.ai.screening_domain import AIScreeningMode
from backend.app.db.base import Base
from backend.app.db.sequence import insert_next_unique_integer
from backend.app.screening.persistence import ScreeningDecisionRecord


class AIFullTextProposalLinkRecord(Base):
    __tablename__ = "ai_full_text_proposal_links"
    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_ai_full_text_proposal"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_full_text_link_tenant"),
        CheckConstraint(
            "assistance_mode IN ('BLINDED_AI','ASSISTED')", name="ck_ai_full_text_mode"
        ),
        CheckConstraint(
            "document_role IN "
            "('PRIMARY_FULL_TEXT','SUPPLEMENT','APPENDIX','OTHER_SUPPORTING_DOCUMENT')",
            name="ck_ai_full_text_document_role",
        ),
        CheckConstraint(
            "document_version_id = document_id", name="ck_ai_full_text_document_version"
        ),
        CheckConstraint("task_definition_version > 0", name="ck_ai_full_text_task_version"),
        CheckConstraint("length(protocol_content_hash) = 64", name="ck_ai_full_text_protocol_hash"),
        CheckConstraint(
            "length(exclusion_criteria_hash) = 64", name="ck_ai_full_text_criteria_hash"
        ),
        CheckConstraint("length(citation_content_hash) = 64", name="ck_ai_full_text_citation_hash"),
        CheckConstraint("length(document_content_hash) = 64", name="ck_ai_full_text_document_hash"),
        CheckConstraint(
            "length(parsed_representation_hash) = 64", name="ck_ai_full_text_parsed_hash"
        ),
        CheckConstraint("length(selected_text_hash) = 64", name="ck_ai_full_text_selected_hash"),
        CheckConstraint("length(chunk_manifest_hash) = 64", name="ck_ai_full_text_manifest_hash"),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_full_text_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            [
                "ai_execution_runs.id",
                "ai_execution_runs.organization_id",
                "ai_execution_runs.review_id",
            ],
            name="fk_ai_full_text_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assignment_id", "organization_id", "review_id"],
            [
                "screening_assignments.id",
                "screening_assignments.organization_id",
                "screening_assignments.review_id",
            ],
            name="fk_ai_full_text_assignment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_ai_full_text_article",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["protocol_version_id", "organization_id", "review_id"],
            [
                "protocol_versions.id",
                "protocol_versions.organization_id",
                "protocol_versions.review_id",
            ],
            name="fk_ai_full_text_protocol",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_ai_full_text_document",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_version_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_ai_full_text_document_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["processing_run_id", "organization_id", "review_id"],
            [
                "document_processing_runs.id",
                "document_processing_runs.organization_id",
                "document_processing_runs.review_id",
            ],
            name="fk_ai_full_text_processing_run",
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
    document_id: Mapped[UUID] = mapped_column()
    document_version_id: Mapped[UUID] = mapped_column()
    processing_run_id: Mapped[UUID] = mapped_column()
    document_role: Mapped[str] = mapped_column(String(40))
    parser_name: Mapped[str] = mapped_column(String(120))
    parser_version: Mapped[str] = mapped_column(String(80))
    protocol_content_hash: Mapped[str] = mapped_column(String(64))
    exclusion_criteria_hash: Mapped[str] = mapped_column(String(64))
    citation_content_hash: Mapped[str] = mapped_column(String(64))
    document_content_hash: Mapped[str] = mapped_column(String(64))
    parsed_representation_hash: Mapped[str] = mapped_column(String(64))
    selected_text_hash: Mapped[str] = mapped_column(String(64))
    chunk_manifest_hash: Mapped[str] = mapped_column(String(64))
    selected_chunk_ids: Mapped[list[str]] = mapped_column(JSON)
    omitted_chunks: Mapped[list[dict[str, str]]] = mapped_column(JSON)
    selection_method: Mapped[str] = mapped_column(String(80))
    task_definition_version: Mapped[int] = mapped_column(Integer)
    assistance_mode: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIFullTextAccessRecord(Base):
    __tablename__ = "ai_full_text_access_events"
    __table_args__ = (
        UniqueConstraint(
            "proposal_id", "reviewer_user_id", "access_type", name="uq_ai_full_text_access"
        ),
        CheckConstraint(
            "access_type IN ('ASSISTED_VIEW','POST_DECISION_REVEAL')",
            name="ck_ai_full_text_access_type",
        ),
        CheckConstraint(
            "(access_type = 'ASSISTED_VIEW' AND screening_decision_id IS NULL) OR "
            "(access_type = 'POST_DECISION_REVEAL' AND screening_decision_id IS NOT NULL)",
            name="ck_ai_full_text_access_decision",
        ),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_full_text_access_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assignment_id", "organization_id", "review_id"],
            [
                "screening_assignments.id",
                "screening_assignments.organization_id",
                "screening_assignments.review_id",
            ],
            name="fk_ai_full_text_access_assignment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["screening_decision_id"],
            ["screening_decisions.id"],
            name="fk_ai_full_text_access_canonical_decision",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reviewer_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_full_text_access_reviewer",
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


class AIFullTextDecisionLinkRecord(Base):
    __tablename__ = "ai_full_text_decision_links"
    __table_args__ = (
        UniqueConstraint("screening_decision_id", name="uq_ai_full_text_decision"),
        CheckConstraint(
            "interaction IN ('UNSEEN','VIEWED','ACCEPTED','OVERRIDDEN','DISAGREED')",
            name="ck_ai_full_text_interaction",
        ),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_full_text_decision_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["screening_decision_id"],
            ["screening_decisions.id"],
            name="fk_ai_full_text_decision_canonical",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "human_reviewer_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_full_text_decision_reviewer",
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
    exclusion_criterion_from_ai: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FullTextEvaluationDatasetRecord(Base):
    __tablename__ = "ai_full_text_evaluation_datasets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "review_id",
            "logical_key",
            "version",
            name="uq_ai_full_text_dataset_version",
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_full_text_dataset_tenant"
        ),
        CheckConstraint(
            "reference_standard IN "
            "('ADJUDICATED_FULL_TEXT','REVIEWER_CONSENSUS',"
            "'FINAL_HUMAN_FULL_TEXT','CURATED_DATASET')",
            name="ck_ai_full_text_reference_standard",
        ),
        CheckConstraint("length(content_hash) = 64", name="ck_ai_full_text_dataset_hash"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_full_text_dataset_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["protocol_version_id", "organization_id", "review_id"],
            [
                "protocol_versions.id",
                "protocol_versions.organization_id",
                "protocol_versions.review_id",
            ],
            name="fk_ai_full_text_dataset_protocol",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_full_text_dataset_creator",
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


class FullTextEvaluationCaseRecord(Base):
    __tablename__ = "ai_full_text_evaluation_cases"
    __table_args__ = (
        UniqueConstraint("dataset_id", "ordinal", name="uq_ai_full_text_case_ordinal"),
        UniqueConstraint("dataset_id", "document_version_id", name="uq_ai_full_text_case_document"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_full_text_case_tenant"),
        CheckConstraint(
            "reference_decision IN ('RETAIN','EXCLUDE')", name="ck_ai_full_text_reference_decision"
        ),
        CheckConstraint(
            "document_version_id = document_id", name="ck_ai_full_text_case_document_version"
        ),
        CheckConstraint(
            "length(evidence_snapshot_hash) = 64", name="ck_ai_full_text_case_evidence_hash"
        ),
        ForeignKeyConstraint(
            ["dataset_id", "organization_id", "review_id"],
            [
                "ai_full_text_evaluation_datasets.id",
                "ai_full_text_evaluation_datasets.organization_id",
                "ai_full_text_evaluation_datasets.review_id",
            ],
            name="fk_ai_full_text_case_dataset",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_ai_full_text_case_article",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_ai_full_text_case_document",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_version_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_ai_full_text_case_document_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["processing_run_id", "organization_id", "review_id"],
            [
                "document_processing_runs.id",
                "document_processing_runs.organization_id",
                "document_processing_runs.review_id",
            ],
            name="fk_ai_full_text_case_processing_run",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    article_id: Mapped[UUID] = mapped_column()
    document_id: Mapped[UUID] = mapped_column()
    document_version_id: Mapped[UUID] = mapped_column()
    processing_run_id: Mapped[UUID] = mapped_column()
    ordinal: Mapped[int] = mapped_column(Integer)
    reference_decision: Mapped[str] = mapped_column(String(20))
    reference_exclusion_criterion_id: Mapped[str | None] = mapped_column(String(200))
    reference_source_type: Mapped[str] = mapped_column(String(50))
    reference_source_id: Mapped[UUID | None] = mapped_column(nullable=True)
    evidence_snapshot_hash: Mapped[str] = mapped_column(String(64))


class FullTextEvaluationResultRecord(Base):
    __tablename__ = "ai_full_text_evaluation_results"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_full_text_result_tenant"
        ),
        CheckConstraint("length(content_hash) = 64", name="ck_ai_full_text_result_hash"),
        ForeignKeyConstraint(
            ["dataset_id", "organization_id", "review_id"],
            [
                "ai_full_text_evaluation_datasets.id",
                "ai_full_text_evaluation_datasets.organization_id",
                "ai_full_text_evaluation_datasets.review_id",
            ],
            name="fk_ai_full_text_result_dataset",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["protocol_version_id", "organization_id", "review_id"],
            [
                "protocol_versions.id",
                "protocol_versions.organization_id",
                "protocol_versions.review_id",
            ],
            name="fk_ai_full_text_result_protocol",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["prompt_version_id", "organization_id"],
            ["ai_prompt_template_versions.id", "ai_prompt_template_versions.organization_id"],
            name="fk_ai_full_text_result_prompt",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["model_version_id", "organization_id"],
            ["ai_model_versions.id", "ai_model_versions.organization_id"],
            name="fk_ai_full_text_result_model",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_full_text_result_creator",
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
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FullTextEvaluationCaseResultRecord(Base):
    __tablename__ = "ai_full_text_evaluation_case_results"
    __table_args__ = (
        UniqueConstraint("evaluation_result_id", "case_id", name="uq_ai_full_text_case_result"),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_full_text_case_result_tenant"
        ),
        ForeignKeyConstraint(
            ["evaluation_result_id", "organization_id", "review_id"],
            [
                "ai_full_text_evaluation_results.id",
                "ai_full_text_evaluation_results.organization_id",
                "ai_full_text_evaluation_results.review_id",
            ],
            name="fk_ai_full_text_case_result_result",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["case_id", "organization_id", "review_id"],
            [
                "ai_full_text_evaluation_cases.id",
                "ai_full_text_evaluation_cases.organization_id",
                "ai_full_text_evaluation_cases.review_id",
            ],
            name="fk_ai_full_text_case_result_case",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_full_text_case_result_proposal",
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
    proposed_criterion_ids: Mapped[list[str]] = mapped_column(JSON)
    reference_criterion_id: Mapped[str | None] = mapped_column(String(200))
    criterion_correct: Mapped[bool | None] = mapped_column(nullable=True)
    evidence_valid: Mapped[bool] = mapped_column()
    evidence_issue_codes: Mapped[list[str]] = mapped_column(JSON)
    evidence_sections: Mapped[list[str]] = mapped_column(JSON)
    disagreement: Mapped[str] = mapped_column(String(50))


class FullTextErrorClassificationRecord(Base):
    __tablename__ = "ai_full_text_error_classifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["case_result_id", "organization_id", "review_id"],
            [
                "ai_full_text_evaluation_case_results.id",
                "ai_full_text_evaluation_case_results.organization_id",
                "ai_full_text_evaluation_case_results.review_id",
            ],
            name="fk_ai_full_text_error_case",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "classified_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_full_text_error_actor",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    case_result_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    category: Mapped[str] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)
    classified_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


_IMMUTABLE = (
    AIFullTextProposalLinkRecord,
    AIFullTextAccessRecord,
    AIFullTextDecisionLinkRecord,
    FullTextEvaluationDatasetRecord,
    FullTextEvaluationCaseRecord,
    FullTextEvaluationResultRecord,
    FullTextEvaluationCaseResultRecord,
    FullTextErrorClassificationRecord,
)


def _reject_mutation(_mapper: Mapper[Any], _connection: Any, _target: Any) -> None:
    raise ValueError("AI full-text screening records are append-only")


for _record in _IMMUTABLE:
    event.listen(_record, "before_update", _reject_mutation)
    event.listen(_record, "before_delete", _reject_mutation)


class SqlAlchemyAIFullTextRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_proposal_link(self, **values: Any) -> AIFullTextProposalLink:
        row = AIFullTextProposalLinkRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _link(row)

    async def get_proposal_link(
        self, organization_id: UUID, review_id: UUID, proposal_id: UUID
    ) -> AIFullTextProposalLink | None:
        row = await self.session.scalar(
            select(AIFullTextProposalLinkRecord).where(
                AIFullTextProposalLinkRecord.organization_id == organization_id,
                AIFullTextProposalLinkRecord.review_id == review_id,
                AIFullTextProposalLinkRecord.proposal_id == proposal_id,
            )
        )
        return _link(row) if row else None

    async def latest_assignment_link(
        self, organization_id: UUID, review_id: UUID, assignment_id: UUID
    ) -> AIFullTextProposalLink | None:
        row = await self.session.scalar(
            select(AIFullTextProposalLinkRecord)
            .where(
                AIFullTextProposalLinkRecord.organization_id == organization_id,
                AIFullTextProposalLinkRecord.review_id == review_id,
                AIFullTextProposalLinkRecord.assignment_id == assignment_id,
            )
            .order_by(AIFullTextProposalLinkRecord.created_at.desc())
            .limit(1)
        )
        return _link(row) if row else None

    async def record_access(self, **values: Any) -> None:
        existing = await self.session.scalar(
            select(AIFullTextAccessRecord).where(
                AIFullTextAccessRecord.organization_id == values["organization_id"],
                AIFullTextAccessRecord.review_id == values["review_id"],
                AIFullTextAccessRecord.proposal_id == values["proposal_id"],
                AIFullTextAccessRecord.reviewer_user_id == values["reviewer_user_id"],
                AIFullTextAccessRecord.access_type == values["access_type"],
            )
        )
        if existing is None:
            self.session.add(AIFullTextAccessRecord(**values))
            await self.session.flush()

    async def has_access(
        self, organization_id: UUID, review_id: UUID, proposal_id: UUID, reviewer_user_id: UUID
    ) -> bool:
        return (
            await self.session.scalar(
                select(AIFullTextAccessRecord.id).where(
                    AIFullTextAccessRecord.organization_id == organization_id,
                    AIFullTextAccessRecord.review_id == review_id,
                    AIFullTextAccessRecord.proposal_id == proposal_id,
                    AIFullTextAccessRecord.reviewer_user_id == reviewer_user_id,
                )
            )
            is not None
        )

    async def link_decision(self, **values: Any) -> None:
        exists = await self.session.scalar(
            select(AIFullTextDecisionLinkRecord.id).where(
                AIFullTextDecisionLinkRecord.screening_decision_id
                == values["screening_decision_id"]
            )
        )
        if exists is None:
            self.session.add(AIFullTextDecisionLinkRecord(**values))
            await self.session.flush()

    async def create_dataset(
        self, *, cases: list[dict[str, Any]], **values: Any
    ) -> FullTextEvaluationDataset:
        async def next_version() -> int:
            current = await self.session.scalar(
                select(func.max(FullTextEvaluationDatasetRecord.version)).where(
                    FullTextEvaluationDatasetRecord.organization_id == values["organization_id"],
                    FullTextEvaluationDatasetRecord.review_id == values["review_id"],
                    FullTextEvaluationDatasetRecord.logical_key == values["logical_key"],
                )
            )
            return int(current or 0) + 1

        row = await insert_next_unique_integer(
            self.session,
            next_version,
            lambda version: FullTextEvaluationDatasetRecord(**values, version=version),
        )
        for ordinal, item in enumerate(cases, start=1):
            self.session.add(
                FullTextEvaluationCaseRecord(
                    dataset_id=row.id,
                    organization_id=row.organization_id,
                    review_id=row.review_id,
                    ordinal=ordinal,
                    **item,
                )
            )
        await self.session.flush()
        await self.session.refresh(row)
        return _dataset(row)

    async def get_dataset(
        self, organization_id: UUID, review_id: UUID, dataset_id: UUID
    ) -> FullTextEvaluationDataset | None:
        row = await self.session.scalar(
            select(FullTextEvaluationDatasetRecord).where(
                FullTextEvaluationDatasetRecord.organization_id == organization_id,
                FullTextEvaluationDatasetRecord.review_id == review_id,
                FullTextEvaluationDatasetRecord.id == dataset_id,
            )
        )
        return _dataset(row) if row else None

    async def list_datasets(
        self, organization_id: UUID, review_id: UUID
    ) -> list[FullTextEvaluationDataset]:
        rows = await self.session.scalars(
            select(FullTextEvaluationDatasetRecord)
            .where(
                FullTextEvaluationDatasetRecord.organization_id == organization_id,
                FullTextEvaluationDatasetRecord.review_id == review_id,
            )
            .order_by(
                FullTextEvaluationDatasetRecord.logical_key, FullTextEvaluationDatasetRecord.version
            )
        )
        return [_dataset(row) for row in rows]

    async def list_cases(
        self, organization_id: UUID, review_id: UUID, dataset_id: UUID
    ) -> list[FullTextEvaluationCase]:
        rows = await self.session.scalars(
            select(FullTextEvaluationCaseRecord)
            .where(
                FullTextEvaluationCaseRecord.organization_id == organization_id,
                FullTextEvaluationCaseRecord.review_id == review_id,
                FullTextEvaluationCaseRecord.dataset_id == dataset_id,
            )
            .order_by(FullTextEvaluationCaseRecord.ordinal)
        )
        return [_case(row) for row in rows]

    async def latest_dimensions(
        self, organization_id: UUID, review_id: UUID, protocol_version_id: UUID
    ) -> tuple[UUID, UUID] | None:
        row = (
            await self.session.execute(
                select(
                    AIExecutionRunRecord.prompt_version_id, AIExecutionRunRecord.model_version_id
                )
                .join(
                    AIFullTextProposalLinkRecord,
                    AIFullTextProposalLinkRecord.ai_run_id == AIExecutionRunRecord.id,
                )
                .where(
                    AIFullTextProposalLinkRecord.organization_id == organization_id,
                    AIFullTextProposalLinkRecord.review_id == review_id,
                    AIFullTextProposalLinkRecord.protocol_version_id == protocol_version_id,
                )
                .order_by(AIFullTextProposalLinkRecord.created_at.desc())
                .limit(1)
            )
        ).first()
        return (row[0], row[1]) if row else None

    async def matching_proposals(
        self,
        organization_id: UUID,
        review_id: UUID,
        protocol_version_id: UUID,
        prompt_version_id: UUID,
        model_version_id: UUID,
        document_version_ids: list[UUID],
    ) -> dict[
        UUID,
        tuple[
            AIOutputProposalRecord,
            AIFullTextProposalLinkRecord,
            AIExecutionRunRecord,
            UUID | None,
        ],
    ]:
        rows = (
            await self.session.execute(
                select(
                    AIOutputProposalRecord,
                    AIFullTextProposalLinkRecord,
                    AIExecutionRunRecord,
                    ScreeningDecisionRecord.id,
                )
                .join(
                    AIFullTextProposalLinkRecord,
                    AIFullTextProposalLinkRecord.proposal_id == AIOutputProposalRecord.id,
                )
                .join(
                    AIExecutionRunRecord,
                    AIExecutionRunRecord.id == AIFullTextProposalLinkRecord.ai_run_id,
                )
                .outerjoin(
                    ScreeningDecisionRecord,
                    (
                        ScreeningDecisionRecord.assignment_id
                        == AIFullTextProposalLinkRecord.assignment_id
                    )
                    & (
                        ScreeningDecisionRecord.organization_id
                        == AIFullTextProposalLinkRecord.organization_id
                    )
                    & (ScreeningDecisionRecord.review_id == AIFullTextProposalLinkRecord.review_id),
                )
                .where(
                    AIFullTextProposalLinkRecord.organization_id == organization_id,
                    AIFullTextProposalLinkRecord.review_id == review_id,
                    AIFullTextProposalLinkRecord.protocol_version_id == protocol_version_id,
                    AIFullTextProposalLinkRecord.document_version_id.in_(document_version_ids),
                    AIExecutionRunRecord.prompt_version_id == prompt_version_id,
                    AIExecutionRunRecord.model_version_id == model_version_id,
                    AIExecutionRunRecord.task_type == "FULL_TEXT_SCREENING_SUGGESTION",
                )
                .order_by(AIFullTextProposalLinkRecord.created_at.desc())
            )
        ).all()
        result: dict[
            UUID,
            tuple[
                AIOutputProposalRecord,
                AIFullTextProposalLinkRecord,
                AIExecutionRunRecord,
                UUID | None,
            ],
        ] = {}
        for proposal, link, run, decision_id in rows:
            result.setdefault(link.document_version_id, (proposal, link, run, decision_id))
        return result

    async def create_result(self, *, case_results: list[dict[str, Any]], **values: Any) -> UUID:
        row = FullTextEvaluationResultRecord(**values)
        self.session.add(row)
        await self.session.flush()
        for item in case_results:
            self.session.add(
                FullTextEvaluationCaseResultRecord(
                    evaluation_result_id=row.id,
                    organization_id=row.organization_id,
                    review_id=row.review_id,
                    **item,
                )
            )
        await self.session.flush()
        return row.id

    async def list_results(
        self, organization_id: UUID, review_id: UUID
    ) -> list[FullTextEvaluationResultRecord]:
        return list(
            await self.session.scalars(
                select(FullTextEvaluationResultRecord)
                .where(
                    FullTextEvaluationResultRecord.organization_id == organization_id,
                    FullTextEvaluationResultRecord.review_id == review_id,
                )
                .order_by(FullTextEvaluationResultRecord.created_at.desc())
            )
        )

    async def get_result(
        self, organization_id: UUID, review_id: UUID, result_id: UUID
    ) -> FullTextEvaluationResultRecord | None:
        return cast(
            FullTextEvaluationResultRecord | None,
            await self.session.scalar(
                select(FullTextEvaluationResultRecord).where(
                    FullTextEvaluationResultRecord.organization_id == organization_id,
                    FullTextEvaluationResultRecord.review_id == review_id,
                    FullTextEvaluationResultRecord.id == result_id,
                )
            ),
        )

    async def list_case_results(
        self, organization_id: UUID, review_id: UUID, result_id: UUID
    ) -> list[FullTextEvaluationCaseResultRecord]:
        return list(
            await self.session.scalars(
                select(FullTextEvaluationCaseResultRecord).where(
                    FullTextEvaluationCaseResultRecord.organization_id == organization_id,
                    FullTextEvaluationCaseResultRecord.review_id == review_id,
                    FullTextEvaluationCaseResultRecord.evaluation_result_id == result_id,
                )
            )
        )

    async def list_error_classifications_for_result(
        self, organization_id: UUID, review_id: UUID, result_id: UUID
    ) -> list[FullTextErrorClassificationRecord]:
        return list(
            await self.session.scalars(
                select(FullTextErrorClassificationRecord)
                .join(
                    FullTextEvaluationCaseResultRecord,
                    FullTextEvaluationCaseResultRecord.id
                    == FullTextErrorClassificationRecord.case_result_id,
                )
                .where(
                    FullTextErrorClassificationRecord.organization_id == organization_id,
                    FullTextErrorClassificationRecord.review_id == review_id,
                    FullTextEvaluationCaseResultRecord.evaluation_result_id == result_id,
                )
                .order_by(
                    FullTextErrorClassificationRecord.created_at,
                    FullTextErrorClassificationRecord.id,
                )
            )
        )

    async def classify_error(self, **values: Any) -> None:
        case_result = await self.session.scalar(
            select(FullTextEvaluationCaseResultRecord.id).where(
                FullTextEvaluationCaseResultRecord.organization_id == values["organization_id"],
                FullTextEvaluationCaseResultRecord.review_id == values["review_id"],
                FullTextEvaluationCaseResultRecord.id == values["case_result_id"],
            )
        )
        if case_result is None:
            raise LookupError("full-text evaluation case result was not found")
        self.session.add(FullTextErrorClassificationRecord(**values))
        await self.session.flush()


def _link(row: AIFullTextProposalLinkRecord) -> AIFullTextProposalLink:
    return AIFullTextProposalLink(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        proposal_id=row.proposal_id,
        ai_run_id=row.ai_run_id,
        article_id=row.article_id,
        assignment_id=row.assignment_id,
        protocol_version_id=row.protocol_version_id,
        document_id=row.document_id,
        document_version_id=row.document_version_id,
        processing_run_id=row.processing_run_id,
        document_role=FullTextDocumentRole(row.document_role),
        parser_name=row.parser_name,
        parser_version=row.parser_version,
        protocol_content_hash=row.protocol_content_hash,
        exclusion_criteria_hash=row.exclusion_criteria_hash,
        citation_content_hash=row.citation_content_hash,
        document_content_hash=row.document_content_hash,
        parsed_representation_hash=row.parsed_representation_hash,
        selected_text_hash=row.selected_text_hash,
        chunk_manifest_hash=row.chunk_manifest_hash,
        selected_chunk_ids=tuple(row.selected_chunk_ids),
        omitted_chunks=tuple(row.omitted_chunks),
        selection_method=row.selection_method,
        task_definition_version=row.task_definition_version,
        assistance_mode=AIScreeningMode(row.assistance_mode),
        created_at=row.created_at or datetime.now(UTC),
    )


def _dataset(row: FullTextEvaluationDatasetRecord) -> FullTextEvaluationDataset:
    return FullTextEvaluationDataset(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        logical_key=row.logical_key,
        version=row.version,
        protocol_version_id=row.protocol_version_id,
        name=row.name,
        reference_standard=FullTextReferenceStandard(row.reference_standard),
        content_hash=row.content_hash,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at or datetime.now(UTC),
    )


def _case(row: FullTextEvaluationCaseRecord) -> FullTextEvaluationCase:
    return FullTextEvaluationCase(
        id=row.id,
        dataset_id=row.dataset_id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        article_id=row.article_id,
        document_id=row.document_id,
        document_version_id=row.document_version_id,
        processing_run_id=row.processing_run_id,
        ordinal=row.ordinal,
        reference_decision=row.reference_decision,
        reference_exclusion_criterion_id=row.reference_exclusion_criterion_id,
        reference_source_type=FullTextReferenceStandard(row.reference_source_type),
        reference_source_id=row.reference_source_id,
        evidence_snapshot_hash=row.evidence_snapshot_hash,
    )
