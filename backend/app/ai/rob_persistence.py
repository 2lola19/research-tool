from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
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

from backend.app.ai.rob_domain import (
    AIRobAccessType,
    AIRobEvaluationDataset,
    AIRobPolicy,
    AIRobProposalLink,
    AIRobReferenceStandard,
)
from backend.app.ai.screening_domain import AIScreeningMode
from backend.app.db.base import Base
from backend.app.db.sequence import insert_next_unique_integer


class AIRobPolicyRecord(Base):
    __tablename__ = "ai_rob_policy_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "review_id", "version", name="uq_ai_rob_policy_version"
        ),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_rob_policy_tenant"),
        CheckConstraint("mode IN ('OFF','BLINDED_AI','ASSISTED')", name="ck_ai_rob_mode"),
        CheckConstraint("maximum_batch_size BETWEEN 1 AND 100", name="ck_ai_rob_batch_size"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_rob_policy_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_rob_policy_creator",
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


class AIRobProposalLinkRecord(Base):
    __tablename__ = "ai_rob_proposal_links"
    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_ai_rob_proposal"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_rob_link_tenant"),
        Index(
            "ix_ai_rob_assessment",
            "organization_id",
            "review_id",
            "assessment_id",
            "created_at",
        ),
        CheckConstraint("assistance_mode IN ('BLINDED_AI','ASSISTED')", name="ck_ai_rob_link_mode"),
        CheckConstraint("length(instrument_content_hash) = 64", name="ck_ai_rob_instrument_hash"),
        CheckConstraint("length(chunk_manifest_hash) = 64", name="ck_ai_rob_chunk_hash"),
        CheckConstraint("length(selected_text_hash) = 64", name="ck_ai_rob_text_hash"),
        CheckConstraint("task_definition_version > 0", name="ck_ai_rob_task_version"),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_rob_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            [
                "ai_execution_runs.id",
                "ai_execution_runs.organization_id",
                "ai_execution_runs.review_id",
            ],
            name="fk_ai_rob_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assessment_id", "organization_id", "review_id"],
            ["rob_assessments.id", "rob_assessments.organization_id", "rob_assessments.review_id"],
            name="fk_ai_rob_assessment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_ai_rob_study",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["instrument_version_id", "organization_id", "review_id"],
            [
                "rob_instrument_versions.id",
                "rob_instrument_versions.organization_id",
                "rob_instrument_versions.review_id",
            ],
            name="fk_ai_rob_instrument_version",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    ai_run_id: Mapped[UUID] = mapped_column()
    assessment_id: Mapped[UUID] = mapped_column()
    study_id: Mapped[UUID] = mapped_column()
    instrument_version_id: Mapped[UUID] = mapped_column()
    instrument_content_hash: Mapped[str] = mapped_column(String(64))
    task_definition_version: Mapped[int] = mapped_column(Integer)
    assistance_mode: Mapped[str] = mapped_column(String(20))
    source_manifest: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    selected_chunk_ids: Mapped[list[str]] = mapped_column(JSON)
    omitted_chunks: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    selection_method: Mapped[str] = mapped_column(String(100))
    chunk_manifest_hash: Mapped[str] = mapped_column(String(64))
    selected_text_hash: Mapped[str] = mapped_column(String(64))
    validation_results: Mapped[dict[str, Any]] = mapped_column(JSON)
    domain_suggestions: Mapped[dict[str, str | None]] = mapped_column(JSON)
    overall_suggestion: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIRobSourceRecord(Base):
    __tablename__ = "ai_rob_sources"
    __table_args__ = (
        UniqueConstraint("proposal_link_id", "ordinal", name="uq_ai_rob_source_ordinal"),
        UniqueConstraint("proposal_link_id", "document_id", name="uq_ai_rob_source_document"),
        CheckConstraint("document_version_id = document_id", name="ck_ai_rob_source_version"),
        ForeignKeyConstraint(
            ["proposal_link_id", "organization_id", "review_id"],
            [
                "ai_rob_proposal_links.id",
                "ai_rob_proposal_links.organization_id",
                "ai_rob_proposal_links.review_id",
            ],
            name="fk_ai_rob_source_link",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_ai_rob_source_article",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_ai_rob_source_document",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_version_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_ai_rob_source_document_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["processing_run_id", "organization_id", "review_id"],
            [
                "document_processing_runs.id",
                "document_processing_runs.organization_id",
                "document_processing_runs.review_id",
            ],
            name="fk_ai_rob_source_processing",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_link_id: Mapped[UUID] = mapped_column()
    ordinal: Mapped[int] = mapped_column(Integer)
    article_id: Mapped[UUID] = mapped_column()
    document_id: Mapped[UUID] = mapped_column()
    document_version_id: Mapped[UUID] = mapped_column()
    processing_run_id: Mapped[UUID] = mapped_column()
    document_role: Mapped[str] = mapped_column(String(40))
    document_content_hash: Mapped[str] = mapped_column(String(64))
    parser_name: Mapped[str] = mapped_column(String(120))
    parser_version: Mapped[str] = mapped_column(String(80))
    parsed_content_hash: Mapped[str] = mapped_column(String(64))
    block_count: Mapped[int] = mapped_column(Integer)


class AIRobEvidenceRecord(Base):
    __tablename__ = "ai_rob_evidence"
    __table_args__ = (
        UniqueConstraint(
            "proposal_link_id", "question_key", "ordinal", name="uq_ai_rob_evidence_ordinal"
        ),
        Index("ix_ai_rob_evidence_question", "proposal_link_id", "question_key"),
        ForeignKeyConstraint(
            ["proposal_link_id", "organization_id", "review_id"],
            [
                "ai_rob_proposal_links.id",
                "ai_rob_proposal_links.organization_id",
                "ai_rob_proposal_links.review_id",
            ],
            name="fk_ai_rob_evidence_link",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_ai_rob_evidence_document",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_version_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_ai_rob_evidence_document_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_block_id", "document_id", "organization_id", "review_id"],
            [
                "document_blocks.id",
                "document_blocks.document_id",
                "document_blocks.organization_id",
                "document_blocks.review_id",
            ],
            name="fk_ai_rob_evidence_block",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_link_id: Mapped[UUID] = mapped_column()
    question_key: Mapped[str] = mapped_column(String(120))
    ordinal: Mapped[int] = mapped_column(Integer)
    document_id: Mapped[UUID] = mapped_column()
    document_version_id: Mapped[UUID] = mapped_column()
    chunk_id: Mapped[str] = mapped_column(String(500))
    source_block_id: Mapped[UUID] = mapped_column()
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(500), nullable=True)
    quote: Mapped[str] = mapped_column(Text)
    evidence_hash: Mapped[str] = mapped_column(String(64))


class AIRobAccessRecord(Base):
    __tablename__ = "ai_rob_access_events"
    __table_args__ = (
        UniqueConstraint("proposal_id", "reviewer_user_id", "access_type", name="uq_ai_rob_access"),
        CheckConstraint(
            "access_type IN ('ASSISTED_VIEW','POST_SUBMISSION_REVEAL')",
            name="ck_ai_rob_access_type",
        ),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_rob_access_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assessment_id", "organization_id", "review_id"],
            ["rob_assessments.id", "rob_assessments.organization_id", "rob_assessments.review_id"],
            name="fk_ai_rob_access_assessment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["canonical_assessment_id", "organization_id", "review_id"],
            ["rob_assessments.id", "rob_assessments.organization_id", "rob_assessments.review_id"],
            name="fk_ai_rob_access_canonical_assessment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reviewer_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_rob_access_reviewer",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    assessment_id: Mapped[UUID] = mapped_column()
    reviewer_user_id: Mapped[UUID] = mapped_column()
    access_type: Mapped[str] = mapped_column(String(30))
    canonical_assessment_id: Mapped[UUID | None] = mapped_column(nullable=True)
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AIRobAnswerReviewRecord(Base):
    __tablename__ = "ai_rob_answer_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_rob_answer_review_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assessment_id", "organization_id", "review_id"],
            ["rob_assessments.id", "rob_assessments.organization_id", "rob_assessments.review_id"],
            name="fk_ai_rob_answer_review_assessment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reviewer_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_rob_answer_review_reviewer",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "action IN ('ACCEPTED','EDITED','REJECTED','UNRESOLVED')",
            name="ck_ai_rob_answer_review_action",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    assessment_id: Mapped[UUID] = mapped_column()
    question_key: Mapped[str] = mapped_column(String(120))
    reviewer_user_id: Mapped[UUID] = mapped_column()
    action: Mapped[str] = mapped_column(String(20))
    ai_answer_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    human_answer_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIRobEvaluationDatasetRecord(Base):
    __tablename__ = "ai_rob_evaluation_datasets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "review_id",
            "logical_key",
            "version",
            name="uq_ai_rob_dataset_version",
        ),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_rob_dataset_tenant"),
        CheckConstraint(
            "reference_standard IN ("
            "'ADJUDICATED_ASSESSMENT','DUAL_HUMAN_ASSESSMENT','CURATED_GOLD')",
            name="ck_ai_rob_reference_standard",
        ),
        CheckConstraint("length(content_hash) = 64", name="ck_ai_rob_dataset_hash"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_rob_dataset_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["instrument_version_id", "organization_id", "review_id"],
            [
                "rob_instrument_versions.id",
                "rob_instrument_versions.organization_id",
                "rob_instrument_versions.review_id",
            ],
            name="fk_ai_rob_dataset_instrument",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_rob_dataset_creator",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    instrument_version_id: Mapped[UUID] = mapped_column()
    logical_key: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(300))
    reference_standard: Mapped[str] = mapped_column(String(40))
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIRobEvaluationCaseRecord(Base):
    __tablename__ = "ai_rob_evaluation_cases"
    __table_args__ = (
        UniqueConstraint("dataset_id", "ordinal", name="uq_ai_rob_case_ordinal"),
        UniqueConstraint("dataset_id", "study_id", "question_key", name="uq_ai_rob_case_question"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_rob_case_tenant"),
        ForeignKeyConstraint(
            ["dataset_id", "organization_id", "review_id"],
            [
                "ai_rob_evaluation_datasets.id",
                "ai_rob_evaluation_datasets.organization_id",
                "ai_rob_evaluation_datasets.review_id",
            ],
            name="fk_ai_rob_case_dataset",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_ai_rob_case_study",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assessment_id", "organization_id", "review_id"],
            ["rob_assessments.id", "rob_assessments.organization_id", "rob_assessments.review_id"],
            name="fk_ai_rob_case_assessment",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    dataset_id: Mapped[UUID] = mapped_column()
    ordinal: Mapped[int] = mapped_column(Integer)
    study_id: Mapped[UUID] = mapped_column()
    assessment_id: Mapped[UUID | None] = mapped_column(nullable=True)
    question_key: Mapped[str] = mapped_column(String(120))
    reference_answers: Mapped[dict[str, str]] = mapped_column(JSON)
    reference_domains: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    reference_overall: Mapped[str | None] = mapped_column(String(120), nullable=True)
    evidence_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class AIRobEvaluationResultRecord(Base):
    __tablename__ = "ai_rob_evaluation_results"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_rob_result_tenant"),
        ForeignKeyConstraint(
            ["dataset_id", "organization_id", "review_id"],
            [
                "ai_rob_evaluation_datasets.id",
                "ai_rob_evaluation_datasets.organization_id",
                "ai_rob_evaluation_datasets.review_id",
            ],
            name="fk_ai_rob_result_dataset",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_rob_result_creator",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    dataset_id: Mapped[UUID] = mapped_column()
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON)
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSON)
    result_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIRobEvaluationCaseResultRecord(Base):
    __tablename__ = "ai_rob_evaluation_case_results"
    __table_args__ = (
        UniqueConstraint("evaluation_result_id", "case_id", name="uq_ai_rob_case_result"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_rob_case_result_tenant"),
        ForeignKeyConstraint(
            ["evaluation_result_id", "organization_id", "review_id"],
            [
                "ai_rob_evaluation_results.id",
                "ai_rob_evaluation_results.organization_id",
                "ai_rob_evaluation_results.review_id",
            ],
            name="fk_ai_rob_case_result_result",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["case_id", "organization_id", "review_id"],
            [
                "ai_rob_evaluation_cases.id",
                "ai_rob_evaluation_cases.organization_id",
                "ai_rob_evaluation_cases.review_id",
            ],
            name="fk_ai_rob_case_result_case",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_rob_case_result_proposal",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    evaluation_result_id: Mapped[UUID] = mapped_column()
    case_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID | None] = mapped_column(nullable=True)
    classification: Mapped[str] = mapped_column(String(40))
    signalling_agreement: Mapped[bool] = mapped_column(Boolean)
    domain_agreement: Mapped[bool] = mapped_column(Boolean)
    overall_agreement: Mapped[bool] = mapped_column(Boolean)
    evidence_grounding_valid: Mapped[bool] = mapped_column(Boolean)
    abstention: Mapped[bool] = mapped_column(Boolean)
    dangerous_underestimation: Mapped[bool] = mapped_column(Boolean)
    details: Mapped[dict[str, Any]] = mapped_column(JSON)


class AIRobErrorClassificationRecord(Base):
    __tablename__ = "ai_rob_error_classifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["case_result_id", "organization_id", "review_id"],
            [
                "ai_rob_evaluation_case_results.id",
                "ai_rob_evaluation_case_results.organization_id",
                "ai_rob_evaluation_case_results.review_id",
            ],
            name="fk_ai_rob_error_case_result",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "classified_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_rob_error_classifier",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    case_result_id: Mapped[UUID] = mapped_column()
    category: Mapped[str] = mapped_column(String(60))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    classified_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _reject_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("AI Risk of Bias evidence and evaluation history is immutable")


for _immutable in (
    AIRobPolicyRecord,
    AIRobProposalLinkRecord,
    AIRobSourceRecord,
    AIRobEvidenceRecord,
    AIRobAccessRecord,
    AIRobAnswerReviewRecord,
    AIRobEvaluationDatasetRecord,
    AIRobEvaluationCaseRecord,
    AIRobEvaluationResultRecord,
    AIRobEvaluationCaseResultRecord,
    AIRobErrorClassificationRecord,
):
    event.listen(_immutable, "before_update", _reject_mutation)
    event.listen(_immutable, "before_delete", _reject_mutation)


def _policy(row: AIRobPolicyRecord) -> AIRobPolicy:
    return AIRobPolicy(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        version=row.version,
        mode=AIScreeningMode(row.mode),
        maximum_batch_size=row.maximum_batch_size,
        created_by_user_id=row.created_by_user_id,
    )


def _link(row: AIRobProposalLinkRecord) -> AIRobProposalLink:
    return AIRobProposalLink(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        proposal_id=row.proposal_id,
        ai_run_id=row.ai_run_id,
        assessment_id=row.assessment_id,
        study_id=row.study_id,
        instrument_version_id=row.instrument_version_id,
        instrument_content_hash=row.instrument_content_hash,
        task_definition_version=row.task_definition_version,
        assistance_mode=AIScreeningMode(row.assistance_mode),
        source_manifest=list(row.source_manifest),
        selected_chunk_ids=tuple(row.selected_chunk_ids),
        omitted_chunks=tuple(row.omitted_chunks),
        selection_method=row.selection_method,
        chunk_manifest_hash=row.chunk_manifest_hash,
        selected_text_hash=row.selected_text_hash,
        validation_results=row.validation_results,
        domain_suggestions=dict(row.domain_suggestions),
        overall_suggestion=row.overall_suggestion,
    )


def _dataset(row: AIRobEvaluationDatasetRecord) -> AIRobEvaluationDataset:
    return AIRobEvaluationDataset(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        instrument_version_id=row.instrument_version_id,
        logical_key=row.logical_key,
        version=row.version,
        name=row.name,
        reference_standard=AIRobReferenceStandard(row.reference_standard),
        content_hash=row.content_hash,
    )


class SqlAlchemyAIRobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def current_policy(self, organization_id: UUID, review_id: UUID) -> AIRobPolicy | None:
        row = await self._session.scalar(
            select(AIRobPolicyRecord)
            .where(
                AIRobPolicyRecord.organization_id == organization_id,
                AIRobPolicyRecord.review_id == review_id,
            )
            .order_by(AIRobPolicyRecord.version.desc())
            .limit(1)
        )
        return _policy(row) if row else None

    async def create_policy(self, **values: Any) -> AIRobPolicy:
        async def next_version() -> int:
            latest = await self._session.scalar(
                select(func.max(AIRobPolicyRecord.version)).where(
                    AIRobPolicyRecord.organization_id == values["organization_id"],
                    AIRobPolicyRecord.review_id == values["review_id"],
                )
            )
            return int(latest or 0) + 1

        row = await insert_next_unique_integer(
            self._session,
            next_version,
            lambda version: AIRobPolicyRecord(version=version, **values),
        )
        await self._session.refresh(row)
        return _policy(row)

    async def create_proposal_link(self, **values: Any) -> AIRobProposalLink:
        row = AIRobProposalLinkRecord(**values)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _link(row)

    async def get_link(
        self, organization_id: UUID, review_id: UUID, link_id: UUID
    ) -> AIRobProposalLink | None:
        row = await self._session.scalar(
            select(AIRobProposalLinkRecord).where(
                AIRobProposalLinkRecord.id == link_id,
                AIRobProposalLinkRecord.organization_id == organization_id,
                AIRobProposalLinkRecord.review_id == review_id,
            )
        )
        return _link(row) if row else None

    async def get_link_by_proposal(
        self, organization_id: UUID, review_id: UUID, proposal_id: UUID
    ) -> AIRobProposalLink | None:
        row = await self._session.scalar(
            select(AIRobProposalLinkRecord).where(
                AIRobProposalLinkRecord.proposal_id == proposal_id,
                AIRobProposalLinkRecord.organization_id == organization_id,
                AIRobProposalLinkRecord.review_id == review_id,
            )
        )
        return _link(row) if row else None

    async def access_exists(
        self,
        organization_id: UUID,
        review_id: UUID,
        proposal_id: UUID,
        reviewer_user_id: UUID,
        access_type: AIRobAccessType,
    ) -> bool:
        row = await self._session.scalar(
            select(AIRobAccessRecord.id).where(
                AIRobAccessRecord.organization_id == organization_id,
                AIRobAccessRecord.review_id == review_id,
                AIRobAccessRecord.proposal_id == proposal_id,
                AIRobAccessRecord.reviewer_user_id == reviewer_user_id,
                AIRobAccessRecord.access_type == access_type.value,
            )
        )
        return row is not None

    async def latest_assignment_link(
        self, organization_id: UUID, review_id: UUID, assessment_id: UUID
    ) -> AIRobProposalLink | None:
        row = await self._session.scalar(
            select(AIRobProposalLinkRecord)
            .where(
                AIRobProposalLinkRecord.assessment_id == assessment_id,
                AIRobProposalLinkRecord.organization_id == organization_id,
                AIRobProposalLinkRecord.review_id == review_id,
            )
            .order_by(AIRobProposalLinkRecord.created_at.desc())
            .limit(1)
        )
        return _link(row) if row else None

    async def latest_study_link(
        self, organization_id: UUID, review_id: UUID, study_id: UUID
    ) -> AIRobProposalLink | None:
        row = await self._session.scalar(
            select(AIRobProposalLinkRecord)
            .where(
                AIRobProposalLinkRecord.study_id == study_id,
                AIRobProposalLinkRecord.organization_id == organization_id,
                AIRobProposalLinkRecord.review_id == review_id,
            )
            .order_by(AIRobProposalLinkRecord.created_at.desc())
            .limit(1)
        )
        return _link(row) if row else None

    async def list_links(self, organization_id: UUID, review_id: UUID) -> list[AIRobProposalLink]:
        rows = await self._session.scalars(
            select(AIRobProposalLinkRecord)
            .where(
                AIRobProposalLinkRecord.organization_id == organization_id,
                AIRobProposalLinkRecord.review_id == review_id,
            )
            .order_by(AIRobProposalLinkRecord.created_at.desc(), AIRobProposalLinkRecord.id)
        )
        return [_link(row) for row in rows]

    async def create_source(self, **values: Any) -> None:
        for key in (
            "article_id",
            "document_id",
            "document_version_id",
            "processing_run_id",
        ):
            values[key] = UUID(str(values[key]))
        self._session.add(AIRobSourceRecord(**values))
        await self._session.flush()

    async def create_evidence(self, **values: Any) -> None:
        self._session.add(AIRobEvidenceRecord(**values))
        await self._session.flush()

    async def record_access(self, **values: Any) -> None:
        self._session.add(AIRobAccessRecord(**values))
        await self._session.flush()

    async def record_answer_review(self, **values: Any) -> AIRobAnswerReviewRecord:
        row = AIRobAnswerReviewRecord(**values)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def create_dataset(
        self, *, cases: list[dict[str, Any]], **values: Any
    ) -> AIRobEvaluationDataset:
        row = AIRobEvaluationDatasetRecord(**values)
        self._session.add(row)
        await self._session.flush()
        for ordinal, case in enumerate(cases, 1):
            self._session.add(
                AIRobEvaluationCaseRecord(
                    organization_id=values["organization_id"],
                    review_id=values["review_id"],
                    dataset_id=row.id,
                    ordinal=ordinal,
                    **case,
                )
            )
        await self._session.flush()
        await self._session.refresh(row)
        return _dataset(row)

    async def get_dataset(
        self, organization_id: UUID, review_id: UUID, dataset_id: UUID
    ) -> AIRobEvaluationDataset | None:
        row = await self._session.scalar(
            select(AIRobEvaluationDatasetRecord).where(
                AIRobEvaluationDatasetRecord.id == dataset_id,
                AIRobEvaluationDatasetRecord.organization_id == organization_id,
                AIRobEvaluationDatasetRecord.review_id == review_id,
            )
        )
        return _dataset(row) if row else None

    async def list_datasets(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AIRobEvaluationDataset]:
        rows = await self._session.scalars(
            select(AIRobEvaluationDatasetRecord)
            .where(
                AIRobEvaluationDatasetRecord.organization_id == organization_id,
                AIRobEvaluationDatasetRecord.review_id == review_id,
            )
            .order_by(
                AIRobEvaluationDatasetRecord.logical_key, AIRobEvaluationDatasetRecord.version
            )
        )
        return [_dataset(row) for row in rows]

    async def list_cases(
        self, organization_id: UUID, review_id: UUID, dataset_id: UUID
    ) -> list[AIRobEvaluationCaseRecord]:
        rows = await self._session.scalars(
            select(AIRobEvaluationCaseRecord)
            .where(
                AIRobEvaluationCaseRecord.dataset_id == dataset_id,
                AIRobEvaluationCaseRecord.organization_id == organization_id,
                AIRobEvaluationCaseRecord.review_id == review_id,
            )
            .order_by(AIRobEvaluationCaseRecord.ordinal)
        )
        return list(rows)

    async def create_evaluation(
        self, *, case_results: list[dict[str, Any]], **values: Any
    ) -> AIRobEvaluationResultRecord:
        row = AIRobEvaluationResultRecord(**values)
        self._session.add(row)
        await self._session.flush()
        for item in case_results:
            self._session.add(
                AIRobEvaluationCaseResultRecord(
                    organization_id=values["organization_id"],
                    review_id=values["review_id"],
                    evaluation_result_id=row.id,
                    **item,
                )
            )
        await self._session.flush()
        await self._session.refresh(row)
        return row

    async def list_evaluations(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AIRobEvaluationResultRecord]:
        rows = await self._session.scalars(
            select(AIRobEvaluationResultRecord)
            .where(
                AIRobEvaluationResultRecord.organization_id == organization_id,
                AIRobEvaluationResultRecord.review_id == review_id,
            )
            .order_by(AIRobEvaluationResultRecord.created_at.desc())
        )
        return list(rows)

    async def list_case_results(
        self, organization_id: UUID, review_id: UUID, evaluation_result_id: UUID
    ) -> list[AIRobEvaluationCaseResultRecord]:
        rows = await self._session.scalars(
            select(AIRobEvaluationCaseResultRecord)
            .where(
                AIRobEvaluationCaseResultRecord.evaluation_result_id == evaluation_result_id,
                AIRobEvaluationCaseResultRecord.organization_id == organization_id,
                AIRobEvaluationCaseResultRecord.review_id == review_id,
            )
            .order_by(AIRobEvaluationCaseResultRecord.id)
        )
        return list(rows)

    async def high_risk_queue(
        self, organization_id: UUID, review_id: UUID, evaluation_result_id: UUID
    ) -> list[AIRobEvaluationCaseResultRecord]:
        rows = await self._session.scalars(
            select(AIRobEvaluationCaseResultRecord)
            .where(
                AIRobEvaluationCaseResultRecord.evaluation_result_id == evaluation_result_id,
                AIRobEvaluationCaseResultRecord.organization_id == organization_id,
                AIRobEvaluationCaseResultRecord.review_id == review_id,
                AIRobEvaluationCaseResultRecord.dangerous_underestimation.is_(True),
            )
            .order_by(AIRobEvaluationCaseResultRecord.id)
        )
        return list(rows)

    async def classify_error(self, **values: Any) -> AIRobErrorClassificationRecord:
        case_result = await self._session.scalar(
            select(AIRobEvaluationCaseResultRecord).where(
                AIRobEvaluationCaseResultRecord.id == values["case_result_id"],
                AIRobEvaluationCaseResultRecord.organization_id == values["organization_id"],
                AIRobEvaluationCaseResultRecord.review_id == values["review_id"],
            )
        )
        if case_result is None:
            raise LookupError("Risk of Bias evaluation case result was not found")
        row = AIRobErrorClassificationRecord(**values)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row


def now_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
