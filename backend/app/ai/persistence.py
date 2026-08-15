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

from backend.app.ai.domain import (
    AIOutputProposal,
    AIProposalState,
    AIRun,
    AIRunState,
    AITaskType,
    ModelVersion,
    PromptTemplateVersion,
)
from backend.app.db.base import Base


class AIModelVersionRecord(Base):
    __tablename__ = "ai_model_versions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider_key",
            "model_identifier",
            "configuration_version",
            name="uq_ai_model_version",
        ),
        UniqueConstraint("id", "organization_id", name="uq_ai_model_versions_id_org"),
        ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name="fk_ai_model_org", ondelete="CASCADE"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    provider_key: Mapped[str] = mapped_column(String(80))
    model_identifier: Mapped[str] = mapped_column(String(160))
    display_name: Mapped[str] = mapped_column(String(160))
    configuration_version: Mapped[int] = mapped_column(Integer)
    capabilities: Mapped[list[str]] = mapped_column(JSON)
    structured_output_supported: Mapped[bool] = mapped_column(Boolean)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pricing: Mapped[dict[str, Any]] = mapped_column(JSON)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIPromptTemplateVersionRecord(Base):
    __tablename__ = "ai_prompt_template_versions"
    __table_args__ = (
        UniqueConstraint("organization_id", "prompt_key", "version", name="uq_ai_prompt_version"),
        UniqueConstraint("id", "organization_id", name="uq_ai_prompt_versions_id_org"),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_prompt_creator",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    prompt_key: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer)
    purpose: Mapped[str] = mapped_column(String(240))
    task_type: Mapped[str] = mapped_column(String(60))
    system_instructions: Mapped[str] = mapped_column(Text)
    user_template: Mapped[str] = mapped_column(Text)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSON)
    validation_requirements: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30))
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIExecutionRunRecord(Base):
    __tablename__ = "ai_execution_runs"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_execution_runs_tenant"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_ai_execution_run_review",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["prompt_version_id", "organization_id"],
            ["ai_prompt_template_versions.id", "ai_prompt_template_versions.organization_id"],
            name="fk_ai_execution_run_prompt",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["model_version_id", "organization_id"],
            ["ai_model_versions.id", "ai_model_versions.organization_id"],
            name="fk_ai_execution_run_model",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_execution_run_creator",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "state IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','TIMED_OUT','CANCELLED','INVALID_OUTPUT')",  # noqa: E501
            name="ck_ai_execution_run_state",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    task_type: Mapped[str] = mapped_column(String(60))
    task_definition_key: Mapped[str] = mapped_column(String(120))
    task_definition_version: Mapped[int] = mapped_column(Integer)
    output_schema_version: Mapped[int] = mapped_column(Integer)
    prompt_version_id: Mapped[UUID] = mapped_column()
    model_version_id: Mapped[UUID] = mapped_column()
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    input_hash: Mapped[str] = mapped_column(String(64))
    rendered_prompt: Mapped[str] = mapped_column(Text)
    rendered_prompt_hash: Mapped[str] = mapped_column(String(64))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(30))
    identical_prior_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIRunAttemptRecord(Base):
    __tablename__ = "ai_run_attempts"
    __table_args__ = (
        UniqueConstraint("ai_run_id", "attempt_number", name="uq_ai_run_attempt_number"),
        ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            [
                "ai_execution_runs.id",
                "ai_execution_runs.organization_id",
                "ai_execution_runs.review_id",
            ],
            name="fk_ai_attempt_run",
            ondelete="CASCADE",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    ai_run_id: Mapped[UUID] = mapped_column()
    attempt_number: Mapped[int] = mapped_column(Integer)
    provider_key: Mapped[str] = mapped_column(String(80))
    model_identifier: Mapped[str] = mapped_column(String(160))
    state: Mapped[str] = mapped_column(String(30))
    error_kind: Mapped[str | None] = mapped_column(String(40), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    response_snapshot: Mapped[dict[str, Any] | str | None] = mapped_column(JSON, nullable=True)
    response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    usage: Mapped[dict[str, Any]] = mapped_column(JSON)
    estimated_cost: Mapped[str | None] = mapped_column(String(80), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIValidationResultRecord(Base):
    __tablename__ = "ai_validation_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            [
                "ai_execution_runs.id",
                "ai_execution_runs.organization_id",
                "ai_execution_runs.review_id",
            ],
            name="fk_ai_validation_run",
            ondelete="CASCADE",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    ai_run_id: Mapped[UUID] = mapped_column()
    stage: Mapped[str] = mapped_column(String(30))
    valid: Mapped[bool] = mapped_column(Boolean)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    validator_version: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIOutputProposalRecord(Base):
    __tablename__ = "ai_output_proposals"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_ai_output_proposal_tenant"),
        ForeignKeyConstraint(
            ["ai_run_id", "organization_id", "review_id"],
            [
                "ai_execution_runs.id",
                "ai_execution_runs.organization_id",
                "ai_execution_runs.review_id",
            ],
            name="fk_ai_proposal_run",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    ai_run_id: Mapped[UUID] = mapped_column()
    task_type: Mapped[str] = mapped_column(String(60))
    target_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_id: Mapped[UUID | None] = mapped_column(nullable=True)
    structured_value: Mapped[dict[str, Any]] = mapped_column(JSON)
    evidence_references: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    model_reported_confidence: Mapped[float | None] = mapped_column(nullable=True)
    response_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIReviewDecisionRecord(Base):
    __tablename__ = "ai_review_decisions"
    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_ai_proposal_single_decision"),
        ForeignKeyConstraint(
            ["proposal_id", "organization_id", "review_id"],
            [
                "ai_output_proposals.id",
                "ai_output_proposals.organization_id",
                "ai_output_proposals.review_id",
            ],
            name="fk_ai_review_decision_proposal",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reviewer_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_ai_review_decision_reviewer",
            ondelete="RESTRICT",
        ),
        CheckConstraint("decision IN ('ACCEPTED','REJECTED')", name="ck_ai_review_decision"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    proposal_id: Mapped[UUID] = mapped_column()
    decision: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_subject_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    canonical_subject_id: Mapped[UUID | None] = mapped_column(nullable=True)
    reviewer_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _reject_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("AI evidence, attempts, proposals, and decisions are immutable")


for _immutable in (
    AIModelVersionRecord,
    AIPromptTemplateVersionRecord,
    AIRunAttemptRecord,
    AIValidationResultRecord,
    AIOutputProposalRecord,
    AIReviewDecisionRecord,
):
    event.listen(_immutable, "before_update", _reject_mutation)
    event.listen(_immutable, "before_delete", _reject_mutation)


class SqlAlchemyAIRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_models(self, organization_id: UUID) -> list[ModelVersion]:
        rows = await self.session.scalars(
            select(AIModelVersionRecord)
            .where(AIModelVersionRecord.organization_id == organization_id)
            .order_by(
                AIModelVersionRecord.provider_key,
                AIModelVersionRecord.model_identifier,
                AIModelVersionRecord.configuration_version,
            )
        )
        return [_model(row) for row in rows]

    async def get_model(self, organization_id: UUID, model_id: UUID) -> ModelVersion | None:
        row = await self.session.scalar(
            select(AIModelVersionRecord).where(
                AIModelVersionRecord.organization_id == organization_id,
                AIModelVersionRecord.id == model_id,
            )
        )
        return _model(row) if row else None

    async def list_prompts(self, organization_id: UUID) -> list[PromptTemplateVersion]:
        rows = await self.session.scalars(
            select(AIPromptTemplateVersionRecord)
            .where(AIPromptTemplateVersionRecord.organization_id == organization_id)
            .order_by(
                AIPromptTemplateVersionRecord.prompt_key, AIPromptTemplateVersionRecord.version
            )
        )
        return [_prompt(row) for row in rows]

    async def get_prompt(
        self, organization_id: UUID, prompt_id: UUID
    ) -> PromptTemplateVersion | None:
        row = await self.session.scalar(
            select(AIPromptTemplateVersionRecord).where(
                AIPromptTemplateVersionRecord.organization_id == organization_id,
                AIPromptTemplateVersionRecord.id == prompt_id,
            )
        )
        return _prompt(row) if row else None

    async def create_model(self, **values: Any) -> ModelVersion:
        row = AIModelVersionRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _model(row)

    async def create_prompt(self, **values: Any) -> PromptTemplateVersion:
        row = AIPromptTemplateVersionRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _prompt(row)

    async def create_run(self, **values: Any) -> AIRun:
        row = AIExecutionRunRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return _run(row)

    async def update_run(
        self, run_id: UUID, organization_id: UUID, review_id: UUID, **values: Any
    ) -> AIRun:
        row = await self.session.scalar(
            select(AIExecutionRunRecord).where(
                AIExecutionRunRecord.id == run_id,
                AIExecutionRunRecord.organization_id == organization_id,
                AIExecutionRunRecord.review_id == review_id,
            )
        )
        if row is None:
            raise LookupError("AI run not found")
        for key, value in values.items():
            setattr(row, key, value)
        await self.session.flush()
        await self.session.refresh(row)
        return _run(row)

    async def get_run(self, organization_id: UUID, review_id: UUID, run_id: UUID) -> AIRun | None:
        row = await self.session.scalar(
            select(AIExecutionRunRecord).where(
                AIExecutionRunRecord.id == run_id,
                AIExecutionRunRecord.organization_id == organization_id,
                AIExecutionRunRecord.review_id == review_id,
            )
        )
        return _run(row) if row else None

    async def list_runs(self, organization_id: UUID, review_id: UUID) -> list[AIRun]:
        rows = await self.session.scalars(
            select(AIExecutionRunRecord)
            .where(
                AIExecutionRunRecord.organization_id == organization_id,
                AIExecutionRunRecord.review_id == review_id,
            )
            .order_by(AIExecutionRunRecord.created_at.desc())
        )
        return [_run(row) for row in rows]

    async def find_identical_run(
        self,
        organization_id: UUID,
        review_id: UUID,
        task_type: str,
        prompt_version_id: UUID,
        model_version_id: UUID,
        input_hash: str,
    ) -> UUID | None:
        return await self.session.scalar(  # type: ignore[no-any-return]
            select(AIExecutionRunRecord.id)
            .where(
                AIExecutionRunRecord.organization_id == organization_id,
                AIExecutionRunRecord.review_id == review_id,
                AIExecutionRunRecord.task_type == task_type,
                AIExecutionRunRecord.prompt_version_id == prompt_version_id,
                AIExecutionRunRecord.model_version_id == model_version_id,
                AIExecutionRunRecord.input_hash == input_hash,
            )
            .order_by(AIExecutionRunRecord.created_at.desc())
            .limit(1)
        )

    async def append_attempt(self, **values: Any) -> None:
        self.session.add(AIRunAttemptRecord(**values))
        await self.session.flush()

    async def append_validation(self, **values: Any) -> None:
        self.session.add(AIValidationResultRecord(**values))
        await self.session.flush()

    async def create_proposal(self, **values: Any) -> AIOutputProposal:
        row = AIOutputProposalRecord(**values)
        self.session.add(row)
        await self.session.flush()
        await self.session.refresh(row)
        return await self._proposal(row)

    async def get_proposal(
        self, organization_id: UUID, review_id: UUID, proposal_id: UUID
    ) -> AIOutputProposal | None:
        row = await self.session.scalar(
            select(AIOutputProposalRecord).where(
                AIOutputProposalRecord.id == proposal_id,
                AIOutputProposalRecord.organization_id == organization_id,
                AIOutputProposalRecord.review_id == review_id,
            )
        )
        return await self._proposal(row) if row else None

    async def decide(self, **values: Any) -> AIOutputProposal:
        self.session.add(AIReviewDecisionRecord(**values))
        await self.session.flush()
        row = await self.session.get(AIOutputProposalRecord, values["proposal_id"])
        if row is None:
            raise LookupError("AI proposal not found")
        return await self._proposal(row)

    async def _proposal(self, row: AIOutputProposalRecord) -> AIOutputProposal:
        decision = await self.session.scalar(
            select(AIReviewDecisionRecord.decision).where(
                AIReviewDecisionRecord.proposal_id == row.id
            )
        )
        state = AIProposalState(decision) if decision else AIProposalState.PENDING_REVIEW
        return AIOutputProposal(
            id=row.id,
            organization_id=row.organization_id,
            review_id=row.review_id,
            ai_run_id=row.ai_run_id,
            task_type=AITaskType(row.task_type),
            target_type=row.target_type,
            target_id=row.target_id,
            structured_value=row.structured_value,
            evidence_references=tuple(row.evidence_references),
            model_reported_confidence=row.model_reported_confidence,
            response_hash=row.response_hash,
            state=state,
            created_at=row.created_at or datetime.now(UTC),
        )


def _model(row: AIModelVersionRecord) -> ModelVersion:
    return ModelVersion(
        id=row.id,
        organization_id=row.organization_id,
        provider_key=row.provider_key,
        model_identifier=row.model_identifier,
        display_name=row.display_name,
        configuration_version=row.configuration_version,
        capabilities=tuple(row.capabilities),
        structured_output_supported=row.structured_output_supported,
        context_window=row.context_window,
        pricing=row.pricing,
        active=row.active,
        deprecated=row.deprecated,
        content_hash=row.content_hash,
        created_at=row.created_at or datetime.now(UTC),
    )


def _prompt(row: AIPromptTemplateVersionRecord) -> PromptTemplateVersion:
    return PromptTemplateVersion(
        id=row.id,
        organization_id=row.organization_id,
        prompt_key=row.prompt_key,
        version=row.version,
        purpose=row.purpose,
        task_type=AITaskType(row.task_type),
        system_instructions=row.system_instructions,
        user_template=row.user_template,
        output_schema=row.output_schema,
        validation_requirements=row.validation_requirements,
        status=row.status,
        content_hash=row.content_hash,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at or datetime.now(UTC),
    )


def _run(row: AIExecutionRunRecord) -> AIRun:
    return AIRun(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        task_type=AITaskType(row.task_type),
        task_definition_key=row.task_definition_key,
        task_definition_version=row.task_definition_version,
        prompt_version_id=row.prompt_version_id,
        model_version_id=row.model_version_id,
        input_snapshot=row.input_snapshot,
        input_hash=row.input_hash,
        rendered_prompt_hash=row.rendered_prompt_hash,
        state=AIRunState(row.state),
        identical_prior_run_id=row.identical_prior_run_id,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at or datetime.now(UTC),
        completed_at=row.completed_at,
    )
