from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
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

from backend.app.ai.extraction_domain import (
    AIExtractionEvaluationDataset,
    AIExtractionPolicy,
    AIExtractionProposalLink,
    AIExtractionReferenceStandard,
)
from backend.app.ai.screening_domain import AIScreeningMode
from backend.app.db.base import Base
from backend.app.db.sequence import insert_next_unique_integer
from backend.app.extraction.verification_persistence import ExtractionVerificationRecord


class AIExtractionPolicyRecord(Base):
    __tablename__ = "ai_extraction_policy_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "review_id", "version", name="uq_ai_extraction_policy_version"
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_extraction_policy_tenant"
        ),
        CheckConstraint("mode IN ('OFF','BLINDED_AI','ASSISTED')", name="ck_ai_extraction_mode"),
        CheckConstraint("maximum_batch_size BETWEEN 1 AND 100", name="ck_ai_extraction_batch_size"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_extraction_policy_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_extraction_policy_creator",
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


class AIExtractionProposalLinkRecord(Base):
    __tablename__ = "ai_extraction_proposal_links"
    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_ai_extraction_proposal"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_extraction_link_tenant"),
        CheckConstraint(
            "assistance_mode IN ('BLINDED_AI','ASSISTED')", name="ck_ai_extraction_link_mode"
        ),
        CheckConstraint("length(schema_hash) = 64", name="ck_ai_extraction_schema_hash"),
        CheckConstraint("length(ordered_field_hash) = 64", name="ck_ai_extraction_field_hash"),
        CheckConstraint("length(chunk_manifest_hash) = 64", name="ck_ai_extraction_chunk_hash"),
        CheckConstraint("length(selected_text_hash) = 64", name="ck_ai_extraction_text_hash"),
        CheckConstraint("task_definition_version > 0", name="ck_ai_extraction_task_version"),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_extraction_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            [
                "ai_execution_runs.id",
                "ai_execution_runs.organization_id",
                "ai_execution_runs.review_id",
            ],
            name="fk_ai_extraction_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assignment_id", "organization_id", "review_id"],
            ["extraction_runs.id", "extraction_runs.organization_id", "extraction_runs.review_id"],
            name="fk_ai_extraction_assignment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_ai_extraction_study",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["schema_version_id", "organization_id", "review_id"],
            [
                "extraction_schema_versions.id",
                "extraction_schema_versions.organization_id",
                "extraction_schema_versions.review_id",
            ],
            name="fk_ai_extraction_schema",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    ai_run_id: Mapped[UUID] = mapped_column()
    assignment_id: Mapped[UUID] = mapped_column()
    study_id: Mapped[UUID] = mapped_column()
    schema_version_id: Mapped[UUID] = mapped_column()
    schema_hash: Mapped[str] = mapped_column(String(64))
    ordered_field_hash: Mapped[str] = mapped_column(String(64))
    task_definition_version: Mapped[int] = mapped_column(Integer)
    assistance_mode: Mapped[str] = mapped_column(String(20))
    source_manifest: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    selected_chunk_ids: Mapped[list[str]] = mapped_column(JSON)
    omitted_chunks: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    field_targets: Mapped[dict[str, list[str]]] = mapped_column(JSON)
    selection_method: Mapped[str] = mapped_column(String(80))
    chunk_manifest_hash: Mapped[str] = mapped_column(String(64))
    selected_text_hash: Mapped[str] = mapped_column(String(64))
    validation_results: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIExtractionSourceRecord(Base):
    __tablename__ = "ai_extraction_sources"
    __table_args__ = (
        UniqueConstraint("proposal_link_id", "ordinal", name="uq_ai_extraction_source_ordinal"),
        UniqueConstraint(
            "proposal_link_id", "document_id", name="uq_ai_extraction_source_document"
        ),
        CheckConstraint(
            "document_role IN "
            "('PRIMARY_FULL_TEXT','SUPPLEMENT','APPENDIX','OTHER_SUPPORTING_DOCUMENT')",
            name="ck_ai_extraction_source_role",
        ),
        CheckConstraint("document_version_id = document_id", name="ck_ai_extraction_doc_version"),
        ForeignKeyConstraint(
            ["proposal_link_id", "organization_id", "review_id"],
            [
                "ai_extraction_proposal_links.id",
                "ai_extraction_proposal_links.organization_id",
                "ai_extraction_proposal_links.review_id",
            ],
            name="fk_ai_extraction_source_link",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["article_id", "organization_id", "review_id"],
            ["articles.id", "articles.organization_id", "articles.review_id"],
            name="fk_ai_extraction_source_article",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_ai_extraction_source_document",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_version_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_ai_extraction_source_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["processing_run_id", "organization_id", "review_id"],
            [
                "document_processing_runs.id",
                "document_processing_runs.organization_id",
                "document_processing_runs.review_id",
            ],
            name="fk_ai_extraction_source_processing",
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


class AIExtractionEvidenceRecord(Base):
    __tablename__ = "ai_extraction_evidence"
    __table_args__ = (
        UniqueConstraint(
            "proposal_link_id", "field_key", "ordinal", name="uq_ai_extraction_evidence_ordinal"
        ),
        ForeignKeyConstraint(
            ["proposal_link_id", "organization_id", "review_id"],
            [
                "ai_extraction_proposal_links.id",
                "ai_extraction_proposal_links.organization_id",
                "ai_extraction_proposal_links.review_id",
            ],
            name="fk_ai_extraction_evidence_link",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_ai_extraction_evidence_document",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["document_version_id", "organization_id", "review_id"],
            ["documents.id", "documents.organization_id", "documents.review_id"],
            name="fk_ai_extraction_evidence_version",
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
            name="fk_ai_extraction_evidence_block",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_link_id: Mapped[UUID] = mapped_column()
    field_key: Mapped[str] = mapped_column(String(200))
    ordinal: Mapped[int] = mapped_column(Integer)
    document_id: Mapped[UUID] = mapped_column()
    document_version_id: Mapped[UUID] = mapped_column()
    chunk_id: Mapped[str] = mapped_column(String(500))
    source_block_id: Mapped[UUID] = mapped_column()
    page: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(500))
    table_id: Mapped[str | None] = mapped_column(String(200))
    figure_id: Mapped[str | None] = mapped_column(String(200))
    quote: Mapped[str] = mapped_column(Text)
    evidence_hash: Mapped[str] = mapped_column(String(64))


class AIExtractionAccessRecord(Base):
    __tablename__ = "ai_extraction_access_events"
    __table_args__ = (
        UniqueConstraint(
            "proposal_id", "reviewer_user_id", "access_type", name="uq_ai_extraction_access"
        ),
        CheckConstraint(
            "access_type IN ('ASSISTED_VIEW','POST_SUBMISSION_REVEAL')",
            name="ck_ai_extraction_access_type",
        ),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_extraction_access_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assignment_id", "organization_id", "review_id"],
            ["extraction_runs.id", "extraction_runs.organization_id", "extraction_runs.review_id"],
            name="fk_ai_extraction_access_assignment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["canonical_run_id", "organization_id", "review_id"],
            ["extraction_runs.id", "extraction_runs.organization_id", "extraction_runs.review_id"],
            name="fk_ai_extraction_access_canonical_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reviewer_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_extraction_access_reviewer",
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
    canonical_run_id: Mapped[UUID | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(String(500))
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AIExtractionFieldReviewRecord(Base):
    __tablename__ = "ai_extraction_field_reviews"
    __table_args__ = (
        CheckConstraint(
            "action IN ('ACCEPTED','EDITED','REJECTED','UNRESOLVED')",
            name="ck_ai_extraction_field_action",
        ),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_extraction_field_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assignment_id", "organization_id", "review_id"],
            ["extraction_runs.id", "extraction_runs.organization_id", "extraction_runs.review_id"],
            name="fk_ai_extraction_field_assignment",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["canonical_value_id", "organization_id", "review_id"],
            [
                "extraction_values.id",
                "extraction_values.organization_id",
                "extraction_values.review_id",
            ],
            name="fk_ai_extraction_field_value",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reviewer_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_extraction_field_reviewer",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    assignment_id: Mapped[UUID] = mapped_column()
    field_key: Mapped[str] = mapped_column(String(200))
    reviewer_user_id: Mapped[UUID] = mapped_column()
    action: Mapped[str] = mapped_column(String(20))
    ai_value_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    human_value_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    canonical_value_id: Mapped[UUID | None] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIExtractionEvaluationDatasetRecord(Base):
    __tablename__ = "ai_extraction_evaluation_datasets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "review_id",
            "logical_key",
            "version",
            name="uq_ai_extraction_dataset_version",
        ),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_extraction_dataset_tenant"
        ),
        ForeignKeyConstraint(
            ["schema_version_id", "organization_id", "review_id"],
            [
                "extraction_schema_versions.id",
                "extraction_schema_versions.organization_id",
                "extraction_schema_versions.review_id",
            ],
            name="fk_ai_extraction_dataset_schema",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_extraction_dataset_creator",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    schema_version_id: Mapped[UUID] = mapped_column()
    logical_key: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(300))
    reference_standard: Mapped[str] = mapped_column(String(50))
    tolerance_policy_version: Mapped[str | None] = mapped_column(String(80))
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIExtractionEvaluationCaseRecord(Base):
    __tablename__ = "ai_extraction_evaluation_cases"
    __table_args__ = (
        UniqueConstraint("dataset_id", "ordinal", name="uq_ai_extraction_case_ordinal"),
        UniqueConstraint("dataset_id", "study_id", "field_key", name="uq_ai_extraction_case_field"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_extraction_case_tenant"),
        ForeignKeyConstraint(
            ["dataset_id", "organization_id", "review_id"],
            [
                "ai_extraction_evaluation_datasets.id",
                "ai_extraction_evaluation_datasets.organization_id",
                "ai_extraction_evaluation_datasets.review_id",
            ],
            name="fk_ai_extraction_case_dataset",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_ai_extraction_case_study",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    dataset_id: Mapped[UUID] = mapped_column()
    ordinal: Mapped[int] = mapped_column(Integer)
    study_id: Mapped[UUID] = mapped_column()
    field_key: Mapped[str] = mapped_column(String(200))
    field_type: Mapped[str] = mapped_column(String(30))
    reference_missingness: Mapped[str] = mapped_column(String(40))
    reference_value: Mapped[Any | None] = mapped_column(JSON)
    reference_unit: Mapped[str | None] = mapped_column(String(100))
    reference_source_id: Mapped[UUID | None] = mapped_column()
    evidence_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    absolute_tolerance: Mapped[float | None] = mapped_column(Float)


class AIExtractionEvaluationResultRecord(Base):
    __tablename__ = "ai_extraction_evaluation_results"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_extraction_result_tenant"
        ),
        ForeignKeyConstraint(
            ["dataset_id", "organization_id", "review_id"],
            [
                "ai_extraction_evaluation_datasets.id",
                "ai_extraction_evaluation_datasets.organization_id",
                "ai_extraction_evaluation_datasets.review_id",
            ],
            name="fk_ai_extraction_result_dataset",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_extraction_result_creator",
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


class AIExtractionEvaluationCaseResultRecord(Base):
    __tablename__ = "ai_extraction_evaluation_case_results"
    __table_args__ = (
        UniqueConstraint("evaluation_result_id", "case_id", name="uq_ai_extraction_case_result"),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_ai_extraction_case_result_tenant"
        ),
        ForeignKeyConstraint(
            ["evaluation_result_id", "organization_id", "review_id"],
            [
                "ai_extraction_evaluation_results.id",
                "ai_extraction_evaluation_results.organization_id",
                "ai_extraction_evaluation_results.review_id",
            ],
            name="fk_ai_extraction_case_result_evaluation",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["case_id", "organization_id", "review_id"],
            [
                "ai_extraction_evaluation_cases.id",
                "ai_extraction_evaluation_cases.organization_id",
                "ai_extraction_evaluation_cases.review_id",
            ],
            name="fk_ai_extraction_case_result_case",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_extraction_case_result_proposal",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    evaluation_result_id: Mapped[UUID] = mapped_column()
    case_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID | None] = mapped_column()
    classification: Mapped[str] = mapped_column(String(50))
    ai_status: Mapped[str | None] = mapped_column(String(50))
    ai_value: Mapped[Any | None] = mapped_column(JSON)
    reference_value: Mapped[Any | None] = mapped_column(JSON)
    absolute_error: Mapped[float | None] = mapped_column(Float)
    relative_error: Mapped[float | None] = mapped_column(Float)
    evidence_valid: Mapped[bool] = mapped_column(Boolean)
    error_categories: Mapped[list[str]] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float)
    source_location: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class AIExtractionErrorClassificationRecord(Base):
    __tablename__ = "ai_extraction_error_classifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["case_result_id", "organization_id", "review_id"],
            [
                "ai_extraction_evaluation_case_results.id",
                "ai_extraction_evaluation_case_results.organization_id",
                "ai_extraction_evaluation_case_results.review_id",
            ],
            name="fk_ai_extraction_error_case_result",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "classified_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_extraction_error_classifier",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    case_result_id: Mapped[UUID] = mapped_column()
    category: Mapped[str] = mapped_column(String(50))
    note: Mapped[str | None] = mapped_column(Text)
    classified_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _policy(row: AIExtractionPolicyRecord) -> AIExtractionPolicy:
    return AIExtractionPolicy(
        row.id,
        row.organization_id,
        row.review_id,
        row.version,
        AIScreeningMode(row.mode),
        row.maximum_batch_size,
        row.created_by_user_id,
    )


def _link(row: AIExtractionProposalLinkRecord) -> AIExtractionProposalLink:
    return AIExtractionProposalLink(
        row.id,
        row.organization_id,
        row.review_id,
        row.proposal_id,
        row.ai_run_id,
        row.assignment_id,
        row.study_id,
        row.schema_version_id,
        row.schema_hash,
        row.ordered_field_hash,
        row.task_definition_version,
        AIScreeningMode(row.assistance_mode),
        row.source_manifest,
        tuple(row.selected_chunk_ids),
        tuple(row.omitted_chunks),
        row.field_targets,
        row.selection_method,
        row.chunk_manifest_hash,
        row.selected_text_hash,
        row.validation_results,
    )


def _dataset(row: AIExtractionEvaluationDatasetRecord) -> AIExtractionEvaluationDataset:
    return AIExtractionEvaluationDataset(
        row.id,
        row.organization_id,
        row.review_id,
        row.schema_version_id,
        row.logical_key,
        row.version,
        row.name,
        AIExtractionReferenceStandard(row.reference_standard),
        row.content_hash,
    )


def _reject_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("AI extraction records are append-only")


for _immutable in (
    AIExtractionPolicyRecord,
    AIExtractionProposalLinkRecord,
    AIExtractionSourceRecord,
    AIExtractionEvidenceRecord,
    AIExtractionAccessRecord,
    AIExtractionFieldReviewRecord,
    AIExtractionEvaluationDatasetRecord,
    AIExtractionEvaluationCaseRecord,
    AIExtractionEvaluationResultRecord,
    AIExtractionEvaluationCaseResultRecord,
    AIExtractionErrorClassificationRecord,
):
    event.listen(_immutable, "before_update", _reject_mutation)
    event.listen(_immutable, "before_delete", _reject_mutation)


class SqlAlchemyAIExtractionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def current_policy(
        self, organization_id: UUID, review_id: UUID
    ) -> AIExtractionPolicy | None:
        row = await self.session.scalar(
            select(AIExtractionPolicyRecord)
            .where(
                AIExtractionPolicyRecord.organization_id == organization_id,
                AIExtractionPolicyRecord.review_id == review_id,
            )
            .order_by(AIExtractionPolicyRecord.version.desc())
            .limit(1)
        )
        return _policy(row) if row else None

    async def create_policy(self, **values: Any) -> AIExtractionPolicy:
        async def next_version() -> int:
            current = await self.session.scalar(
                select(func.max(AIExtractionPolicyRecord.version)).where(
                    AIExtractionPolicyRecord.organization_id == values["organization_id"],
                    AIExtractionPolicyRecord.review_id == values["review_id"],
                )
            )
            return int(current or 0) + 1

        row = await insert_next_unique_integer(
            self.session,
            next_version,
            lambda version: AIExtractionPolicyRecord(**values, version=version),
        )
        await self.session.refresh(row)
        return _policy(row)

    async def create_proposal_link(
        self,
        *,
        sources: list[dict[str, Any]],
        evidence: list[dict[str, Any]],
        **values: Any,
    ) -> AIExtractionProposalLink:
        row = AIExtractionProposalLinkRecord(**values)
        self.session.add(row)
        await self.session.flush()
        for ordinal, source in enumerate(sources, 1):
            self.session.add(
                AIExtractionSourceRecord(
                    organization_id=row.organization_id,
                    review_id=row.review_id,
                    proposal_link_id=row.id,
                    ordinal=ordinal,
                    **source,
                )
            )
        for item in evidence:
            self.session.add(
                AIExtractionEvidenceRecord(
                    organization_id=row.organization_id,
                    review_id=row.review_id,
                    proposal_link_id=row.id,
                    **item,
                )
            )
        await self.session.flush()
        await self.session.refresh(row)
        return _link(row)

    async def get_link(
        self, organization_id: UUID, review_id: UUID, proposal_id: UUID
    ) -> AIExtractionProposalLink | None:
        row = await self.session.scalar(
            select(AIExtractionProposalLinkRecord).where(
                AIExtractionProposalLinkRecord.organization_id == organization_id,
                AIExtractionProposalLinkRecord.review_id == review_id,
                AIExtractionProposalLinkRecord.proposal_id == proposal_id,
            )
        )
        return _link(row) if row else None

    async def latest_assignment_link(
        self, organization_id: UUID, review_id: UUID, assignment_id: UUID
    ) -> AIExtractionProposalLink | None:
        row = await self.session.scalar(
            select(AIExtractionProposalLinkRecord)
            .where(
                AIExtractionProposalLinkRecord.organization_id == organization_id,
                AIExtractionProposalLinkRecord.review_id == review_id,
                AIExtractionProposalLinkRecord.assignment_id == assignment_id,
            )
            .order_by(AIExtractionProposalLinkRecord.created_at.desc())
            .limit(1)
        )
        return _link(row) if row else None

    async def list_links(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AIExtractionProposalLink]:
        rows = await self.session.scalars(
            select(AIExtractionProposalLinkRecord)
            .where(
                AIExtractionProposalLinkRecord.organization_id == organization_id,
                AIExtractionProposalLinkRecord.review_id == review_id,
            )
            .order_by(AIExtractionProposalLinkRecord.created_at.desc())
        )
        return [_link(row) for row in rows]

    async def latest_study_link(
        self, organization_id: UUID, review_id: UUID, study_id: UUID
    ) -> AIExtractionProposalLink | None:
        row = await self.session.scalar(
            select(AIExtractionProposalLinkRecord)
            .where(
                AIExtractionProposalLinkRecord.organization_id == organization_id,
                AIExtractionProposalLinkRecord.review_id == review_id,
                AIExtractionProposalLinkRecord.study_id == study_id,
            )
            .order_by(AIExtractionProposalLinkRecord.created_at.desc())
            .limit(1)
        )
        return _link(row) if row else None

    async def record_access(self, **values: Any) -> None:
        existing = await self.session.scalar(
            select(AIExtractionAccessRecord).where(
                AIExtractionAccessRecord.organization_id == values["organization_id"],
                AIExtractionAccessRecord.review_id == values["review_id"],
                AIExtractionAccessRecord.proposal_id == values["proposal_id"],
                AIExtractionAccessRecord.reviewer_user_id == values["reviewer_user_id"],
                AIExtractionAccessRecord.access_type == values["access_type"],
            )
        )
        if existing is None:
            self.session.add(AIExtractionAccessRecord(**values))
            await self.session.flush()

    async def record_field_review(self, **values: Any) -> AIExtractionFieldReviewRecord:
        row = AIExtractionFieldReviewRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def create_dataset(
        self, *, cases: list[dict[str, Any]], **values: Any
    ) -> AIExtractionEvaluationDataset:
        async def next_version() -> int:
            current = await self.session.scalar(
                select(func.max(AIExtractionEvaluationDatasetRecord.version)).where(
                    AIExtractionEvaluationDatasetRecord.organization_id
                    == values["organization_id"],
                    AIExtractionEvaluationDatasetRecord.review_id == values["review_id"],
                    AIExtractionEvaluationDatasetRecord.logical_key == values["logical_key"],
                )
            )
            return int(current or 0) + 1

        row = await insert_next_unique_integer(
            self.session,
            next_version,
            lambda version: AIExtractionEvaluationDatasetRecord(**values, version=version),
        )
        await self.session.flush()
        for ordinal, case in enumerate(cases, 1):
            self.session.add(
                AIExtractionEvaluationCaseRecord(
                    organization_id=row.organization_id,
                    review_id=row.review_id,
                    dataset_id=row.id,
                    ordinal=ordinal,
                    **case,
                )
            )
        await self.session.flush()
        await self.session.refresh(row)
        return _dataset(row)

    async def verified_reference_exists(
        self, organization_id: UUID, review_id: UUID, source_id: UUID
    ) -> bool:
        row = await self.session.scalar(
            select(ExtractionVerificationRecord.id).where(
                ExtractionVerificationRecord.organization_id == organization_id,
                ExtractionVerificationRecord.review_id == review_id,
                ExtractionVerificationRecord.id == source_id,
                ExtractionVerificationRecord.status.in_(("MATCHED", "ADJUDICATED")),
            )
        )
        return row is not None

    async def get_dataset(
        self, organization_id: UUID, review_id: UUID, dataset_id: UUID
    ) -> AIExtractionEvaluationDataset | None:
        row = await self.session.scalar(
            select(AIExtractionEvaluationDatasetRecord).where(
                AIExtractionEvaluationDatasetRecord.organization_id == organization_id,
                AIExtractionEvaluationDatasetRecord.review_id == review_id,
                AIExtractionEvaluationDatasetRecord.id == dataset_id,
            )
        )
        return _dataset(row) if row else None

    async def list_datasets(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AIExtractionEvaluationDataset]:
        rows = await self.session.scalars(
            select(AIExtractionEvaluationDatasetRecord)
            .where(
                AIExtractionEvaluationDatasetRecord.organization_id == organization_id,
                AIExtractionEvaluationDatasetRecord.review_id == review_id,
            )
            .order_by(AIExtractionEvaluationDatasetRecord.created_at.desc())
        )
        return [_dataset(row) for row in rows]

    async def list_cases(
        self, organization_id: UUID, review_id: UUID, dataset_id: UUID
    ) -> list[AIExtractionEvaluationCaseRecord]:
        rows = await self.session.scalars(
            select(AIExtractionEvaluationCaseRecord)
            .where(
                AIExtractionEvaluationCaseRecord.organization_id == organization_id,
                AIExtractionEvaluationCaseRecord.review_id == review_id,
                AIExtractionEvaluationCaseRecord.dataset_id == dataset_id,
            )
            .order_by(AIExtractionEvaluationCaseRecord.ordinal)
        )
        return list(rows)

    async def create_evaluation(
        self,
        *,
        case_results: list[dict[str, Any]],
        **values: Any,
    ) -> AIExtractionEvaluationResultRecord:
        row = AIExtractionEvaluationResultRecord(**values)
        self.session.add(row)
        await self.session.flush()
        for item in case_results:
            self.session.add(
                AIExtractionEvaluationCaseResultRecord(
                    organization_id=row.organization_id,
                    review_id=row.review_id,
                    evaluation_result_id=row.id,
                    **item,
                )
            )
        await self.session.flush()
        await self.session.refresh(row)
        return row

    async def high_risk_queue(
        self, organization_id: UUID, review_id: UUID, evaluation_result_id: UUID
    ) -> list[AIExtractionEvaluationCaseResultRecord]:
        high_risk = (
            "AI_VALUE_REFERENCE_MISSING",
            "AI_MISSING_REFERENCE_VALUE",
            "EVIDENCE_INVALID",
            "MISMATCH",
        )
        rows = await self.session.scalars(
            select(AIExtractionEvaluationCaseResultRecord).where(
                AIExtractionEvaluationCaseResultRecord.organization_id == organization_id,
                AIExtractionEvaluationCaseResultRecord.review_id == review_id,
                AIExtractionEvaluationCaseResultRecord.evaluation_result_id == evaluation_result_id,
                AIExtractionEvaluationCaseResultRecord.classification.in_(high_risk),
            )
        )
        return list(rows)

    async def list_evaluations(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AIExtractionEvaluationResultRecord]:
        rows = await self.session.scalars(
            select(AIExtractionEvaluationResultRecord)
            .where(
                AIExtractionEvaluationResultRecord.organization_id == organization_id,
                AIExtractionEvaluationResultRecord.review_id == review_id,
            )
            .order_by(AIExtractionEvaluationResultRecord.created_at.desc())
        )
        return list(rows)

    async def list_case_results(
        self, organization_id: UUID, review_id: UUID, evaluation_result_id: UUID
    ) -> list[AIExtractionEvaluationCaseResultRecord]:
        rows = await self.session.scalars(
            select(AIExtractionEvaluationCaseResultRecord)
            .where(
                AIExtractionEvaluationCaseResultRecord.organization_id == organization_id,
                AIExtractionEvaluationCaseResultRecord.review_id == review_id,
                AIExtractionEvaluationCaseResultRecord.evaluation_result_id == evaluation_result_id,
            )
            .order_by(AIExtractionEvaluationCaseResultRecord.id)
        )
        return list(rows)

    async def classify_error(self, **values: Any) -> AIExtractionErrorClassificationRecord:
        case_result = await self.session.scalar(
            select(AIExtractionEvaluationCaseResultRecord.id).where(
                AIExtractionEvaluationCaseResultRecord.id == values["case_result_id"],
                AIExtractionEvaluationCaseResultRecord.organization_id == values["organization_id"],
                AIExtractionEvaluationCaseResultRecord.review_id == values["review_id"],
            )
        )
        if case_result is None:
            raise LookupError("AI extraction evaluation case result was not found")
        row = AIExtractionErrorClassificationRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return row
