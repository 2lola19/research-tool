from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
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
    inspect,
    or_,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from backend.app.db.base import Base
from backend.app.db.sequence import insert_next_unique_integer
from backend.app.documents.persistence import DocumentEvidenceLocationRecord, DocumentRecord
from backend.app.risk_of_bias.domain import (
    AssessmentStatus,
    ComparisonStatus,
    InstrumentDecision,
    RiskOfBiasAnswer,
    RiskOfBiasAssessment,
    RiskOfBiasComparison,
    RiskOfBiasDomainJudgment,
    RiskOfBiasInstrument,
    RiskOfBiasInstrumentVersion,
)


class RiskOfBiasInstrumentRecord(Base):
    __tablename__ = "rob_instruments"
    __table_args__ = (
        UniqueConstraint("organization_id", "review_id", "key", name="uq_rob_instrument_key"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_rob_instrument_id_tenant"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_rob_instrument_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_rob_instrument_creator_membership",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    key: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskOfBiasInstrumentVersionRecord(Base):
    __tablename__ = "rob_instrument_versions"
    __table_args__ = (
        UniqueConstraint("instrument_id", "version", name="uq_rob_instrument_version_number"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_rob_version_id_tenant"),
        ForeignKeyConstraint(
            ["instrument_id", "organization_id", "review_id"],
            ["rob_instruments.id", "rob_instruments.organization_id", "rob_instruments.review_id"],
            name="fk_rob_version_instrument_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_rob_version_creator_membership",
            ondelete="RESTRICT",
        ),
        CheckConstraint("version > 0", name="ck_rob_version_positive"),
        CheckConstraint("length(content_hash) = 64", name="ck_rob_version_hash"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskOfBiasInstrumentDecisionRecord(Base):
    __tablename__ = "rob_instrument_decisions"
    __table_args__ = (
        UniqueConstraint("instrument_version_id", name="uq_rob_version_decision"),
        CheckConstraint("decision IN ('APPROVED','REJECTED')", name="ck_rob_version_decision"),
        ForeignKeyConstraint(
            ["instrument_version_id", "organization_id", "review_id"],
            [
                "rob_instrument_versions.id",
                "rob_instrument_versions.organization_id",
                "rob_instrument_versions.review_id",
            ],
            name="fk_rob_decision_version_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "decided_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_rob_decision_actor_membership",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    instrument_version_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    decision: Mapped[str] = mapped_column(String(20))
    decided_by_user_id: Mapped[UUID] = mapped_column()
    reason: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RiskOfBiasAssessmentRecord(Base):
    __tablename__ = "rob_assessments"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_rob_assessment_id_tenant"),
        UniqueConstraint(
            "study_id",
            "instrument_version_id",
            "round_number",
            "assessor_user_id",
            "revision",
            name="uq_rob_assessment_assessor_revision",
        ),
        UniqueConstraint("supersedes_assessment_id", name="uq_rob_assessment_single_correction"),
        CheckConstraint("round_number > 0 AND revision > 0", name="ck_rob_assessment_numbers"),
        CheckConstraint("status IN ('IN_PROGRESS','SUBMITTED')", name="ck_rob_assessment_status"),
        ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_rob_assessment_study_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["instrument_version_id", "organization_id", "review_id"],
            [
                "rob_instrument_versions.id",
                "rob_instrument_versions.organization_id",
                "rob_instrument_versions.review_id",
            ],
            name="fk_rob_assessment_version_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["supersedes_assessment_id", "organization_id", "review_id"],
            ["rob_assessments.id", "rob_assessments.organization_id", "rob_assessments.review_id"],
            name="fk_rob_assessment_correction_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["overall_evidence_location_id", "organization_id", "review_id"],
            [
                "document_evidence_locations.id",
                "document_evidence_locations.organization_id",
                "document_evidence_locations.review_id",
            ],
            name="fk_rob_assessment_overall_evidence_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "assessor_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_rob_assessment_assessor_membership",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    study_id: Mapped[UUID] = mapped_column()
    instrument_version_id: Mapped[UUID] = mapped_column()
    assessor_user_id: Mapped[UUID] = mapped_column()
    round_number: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    supersedes_assessment_id: Mapped[UUID | None] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default=AssessmentStatus.IN_PROGRESS.value)
    overall_suggested_judgment: Mapped[str | None] = mapped_column(String(120))
    overall_final_judgment: Mapped[str | None] = mapped_column(String(120))
    overall_rationale: Mapped[str | None] = mapped_column(Text)
    overall_override_reason: Mapped[str | None] = mapped_column(Text)
    overall_evidence_location_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RiskOfBiasAnswerRecord(Base):
    __tablename__ = "rob_answers"
    __table_args__ = (
        UniqueConstraint("assessment_id", "question_key", name="uq_rob_answer_question"),
        ForeignKeyConstraint(
            ["assessment_id", "organization_id", "review_id"],
            ["rob_assessments.id", "rob_assessments.organization_id", "rob_assessments.review_id"],
            name="fk_rob_answer_assessment_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["evidence_location_id", "organization_id", "review_id"],
            [
                "document_evidence_locations.id",
                "document_evidence_locations.organization_id",
                "document_evidence_locations.review_id",
            ],
            name="fk_rob_answer_evidence_tenant",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    assessment_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    question_key: Mapped[str] = mapped_column(String(120))
    answer: Mapped[str] = mapped_column(String(120))
    rationale: Mapped[str | None] = mapped_column(Text)
    evidence_location_id: Mapped[UUID | None] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RiskOfBiasDomainJudgmentRecord(Base):
    __tablename__ = "rob_domain_judgments"
    __table_args__ = (
        UniqueConstraint("assessment_id", "domain_key", name="uq_rob_domain_judgment"),
        ForeignKeyConstraint(
            ["assessment_id", "organization_id", "review_id"],
            ["rob_assessments.id", "rob_assessments.organization_id", "rob_assessments.review_id"],
            name="fk_rob_domain_assessment_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["evidence_location_id", "organization_id", "review_id"],
            [
                "document_evidence_locations.id",
                "document_evidence_locations.organization_id",
                "document_evidence_locations.review_id",
            ],
            name="fk_rob_domain_evidence_tenant",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    assessment_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    domain_key: Mapped[str] = mapped_column(String(120))
    suggested_judgment: Mapped[str | None] = mapped_column(String(120))
    final_judgment: Mapped[str] = mapped_column(String(120))
    rationale: Mapped[str] = mapped_column(Text)
    override_reason: Mapped[str | None] = mapped_column(Text)
    evidence_location_id: Mapped[UUID | None] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RiskOfBiasComparisonRecord(Base):
    __tablename__ = "rob_comparisons"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_rob_comparison_id_tenant"),
        UniqueConstraint("assessment_a_id", "assessment_b_id", name="uq_rob_comparison_pair"),
        CheckConstraint("status IN ('AGREEMENT','CONFLICT')", name="ck_rob_comparison_status"),
        ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_rob_comparison_study_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["instrument_version_id", "organization_id", "review_id"],
            [
                "rob_instrument_versions.id",
                "rob_instrument_versions.organization_id",
                "rob_instrument_versions.review_id",
            ],
            name="fk_rob_comparison_version_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assessment_a_id", "organization_id", "review_id"],
            ["rob_assessments.id", "rob_assessments.organization_id", "rob_assessments.review_id"],
            name="fk_rob_comparison_a_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assessment_b_id", "organization_id", "review_id"],
            ["rob_assessments.id", "rob_assessments.organization_id", "rob_assessments.review_id"],
            name="fk_rob_comparison_b_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "compared_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_rob_comparison_actor_membership",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    study_id: Mapped[UUID] = mapped_column()
    instrument_version_id: Mapped[UUID] = mapped_column()
    round_number: Mapped[int] = mapped_column(Integer)
    assessment_a_id: Mapped[UUID] = mapped_column()
    assessment_b_id: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(20))
    differences: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    compared_by_user_id: Mapped[UUID] = mapped_column()
    compared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RiskOfBiasAdjudicationRecord(Base):
    __tablename__ = "rob_adjudications"
    __table_args__ = (
        UniqueConstraint("comparison_id", name="uq_rob_adjudication_comparison"),
        ForeignKeyConstraint(
            ["comparison_id", "organization_id", "review_id"],
            ["rob_comparisons.id", "rob_comparisons.organization_id", "rob_comparisons.review_id"],
            name="fk_rob_adjudication_comparison_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["evidence_location_id", "organization_id", "review_id"],
            [
                "document_evidence_locations.id",
                "document_evidence_locations.organization_id",
                "document_evidence_locations.review_id",
            ],
            name="fk_rob_adjudication_evidence_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "adjudicated_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_rob_adjudication_actor_membership",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    comparison_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    final_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    rationale: Mapped[str] = mapped_column(Text)
    evidence_location_id: Mapped[UUID | None] = mapped_column()
    adjudicated_by_user_id: Mapped[UUID] = mapped_column()
    adjudicated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


def _reject_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("approved Risk of Bias scientific history is append-only")


def _reject_submitted_assessment_mutation(
    _: Mapper[Any], __: object, target: RiskOfBiasAssessmentRecord
) -> None:
    status_history = inspect(target).attrs.status.history
    prior_status = status_history.deleted[0] if status_history.deleted else target.status
    if prior_status == AssessmentStatus.SUBMITTED.value:
        raise TypeError("submitted Risk of Bias assessments are immutable")


for _immutable in (
    RiskOfBiasInstrumentRecord,
    RiskOfBiasInstrumentVersionRecord,
    RiskOfBiasInstrumentDecisionRecord,
    RiskOfBiasComparisonRecord,
    RiskOfBiasAdjudicationRecord,
):
    event.listen(_immutable, "before_update", _reject_mutation)
    event.listen(_immutable, "before_delete", _reject_mutation)

event.listen(
    RiskOfBiasAssessmentRecord,
    "before_update",
    _reject_submitted_assessment_mutation,
)
event.listen(RiskOfBiasAssessmentRecord, "before_delete", _reject_mutation)


def _time(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class SqlAlchemyRiskOfBiasRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_instrument(self, **values: Any) -> RiskOfBiasInstrument:
        row = RiskOfBiasInstrumentRecord(**values)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._instrument(row)

    async def get_instrument(
        self, organization_id: UUID, review_id: UUID, instrument_id: UUID
    ) -> RiskOfBiasInstrument | None:
        row = await self._session.scalar(
            select(RiskOfBiasInstrumentRecord).where(
                RiskOfBiasInstrumentRecord.organization_id == organization_id,
                RiskOfBiasInstrumentRecord.review_id == review_id,
                RiskOfBiasInstrumentRecord.id == instrument_id,
            )
        )
        return self._instrument(row) if row else None

    async def list_instruments(
        self, organization_id: UUID, review_id: UUID
    ) -> list[RiskOfBiasInstrument]:
        rows = await self._session.scalars(
            select(RiskOfBiasInstrumentRecord)
            .where(
                RiskOfBiasInstrumentRecord.organization_id == organization_id,
                RiskOfBiasInstrumentRecord.review_id == review_id,
            )
            .order_by(RiskOfBiasInstrumentRecord.key, RiskOfBiasInstrumentRecord.id)
        )
        return [self._instrument(row) for row in rows]

    async def create_version(self, **values: Any) -> RiskOfBiasInstrumentVersion:
        async def read_next_version() -> int:
            latest = await self._session.scalar(
                select(func.max(RiskOfBiasInstrumentVersionRecord.version)).where(
                    RiskOfBiasInstrumentVersionRecord.instrument_id == values["instrument_id"]
                )
            )
            return int(latest or 0) + 1

        row = await insert_next_unique_integer(
            self._session,
            read_next_version,
            lambda version: RiskOfBiasInstrumentVersionRecord(version=version, **values),
        )
        result = await self.get_version(row.organization_id, row.review_id, row.id)
        assert result is not None
        return result

    async def get_version(
        self, organization_id: UUID, review_id: UUID, version_id: UUID
    ) -> RiskOfBiasInstrumentVersion | None:
        row = await self._session.scalar(
            select(RiskOfBiasInstrumentVersionRecord).where(
                RiskOfBiasInstrumentVersionRecord.organization_id == organization_id,
                RiskOfBiasInstrumentVersionRecord.review_id == review_id,
                RiskOfBiasInstrumentVersionRecord.id == version_id,
            )
        )
        return await self._version(row) if row else None

    async def list_versions(
        self, organization_id: UUID, review_id: UUID, instrument_id: UUID
    ) -> list[RiskOfBiasInstrumentVersion]:
        rows = await self._session.scalars(
            select(RiskOfBiasInstrumentVersionRecord)
            .where(
                RiskOfBiasInstrumentVersionRecord.organization_id == organization_id,
                RiskOfBiasInstrumentVersionRecord.review_id == review_id,
                RiskOfBiasInstrumentVersionRecord.instrument_id == instrument_id,
            )
            .order_by(RiskOfBiasInstrumentVersionRecord.version)
        )
        return [await self._version(row) for row in rows]

    async def decide_version(
        self,
        *,
        version: RiskOfBiasInstrumentVersion,
        decision: InstrumentDecision,
        decided_by_user_id: UUID,
        reason: str | None,
    ) -> RiskOfBiasInstrumentVersion:
        self._session.add(
            RiskOfBiasInstrumentDecisionRecord(
                instrument_version_id=version.id,
                organization_id=version.organization_id,
                review_id=version.review_id,
                decision=decision.value,
                decided_by_user_id=decided_by_user_id,
                reason=reason,
            )
        )
        await self._session.flush()
        result = await self.get_version(version.organization_id, version.review_id, version.id)
        assert result is not None
        return result

    async def create_assessment(self, **values: Any) -> RiskOfBiasAssessment:
        row = RiskOfBiasAssessmentRecord(**values)
        self._session.add(row)
        await self._session.flush()
        return await self._load_assessment(row)

    async def get_assessment(
        self, organization_id: UUID, review_id: UUID, assessment_id: UUID
    ) -> RiskOfBiasAssessment | None:
        row = await self._session.scalar(
            select(RiskOfBiasAssessmentRecord).where(
                RiskOfBiasAssessmentRecord.organization_id == organization_id,
                RiskOfBiasAssessmentRecord.review_id == review_id,
                RiskOfBiasAssessmentRecord.id == assessment_id,
            )
        )
        return await self._load_assessment(row) if row else None

    async def list_assessments(
        self, organization_id: UUID, review_id: UUID, *, assessor_user_id: UUID | None = None
    ) -> list[RiskOfBiasAssessment]:
        query = select(RiskOfBiasAssessmentRecord).where(
            RiskOfBiasAssessmentRecord.organization_id == organization_id,
            RiskOfBiasAssessmentRecord.review_id == review_id,
        )
        if assessor_user_id is not None:
            query = query.where(RiskOfBiasAssessmentRecord.assessor_user_id == assessor_user_id)
        rows = await self._session.scalars(
            query.order_by(
                RiskOfBiasAssessmentRecord.study_id,
                RiskOfBiasAssessmentRecord.instrument_version_id,
                RiskOfBiasAssessmentRecord.round_number,
                RiskOfBiasAssessmentRecord.assessor_user_id,
                RiskOfBiasAssessmentRecord.revision,
            )
        )
        return [await self._load_assessment(row) for row in rows]

    async def save_answer(self, **values: Any) -> RiskOfBiasAssessment:
        assessment: RiskOfBiasAssessment = values.pop("assessment")
        row = await self._session.scalar(
            select(RiskOfBiasAnswerRecord).where(
                RiskOfBiasAnswerRecord.assessment_id == assessment.id,
                RiskOfBiasAnswerRecord.question_key == values["question_key"],
            )
        )
        if row is None:
            row = RiskOfBiasAnswerRecord(
                assessment_id=assessment.id,
                organization_id=assessment.organization_id,
                review_id=assessment.review_id,
                **values,
            )
            self._session.add(row)
        else:
            for key, value in values.items():
                setattr(row, key, value)
        await self._session.flush()
        result = await self.get_assessment(
            assessment.organization_id, assessment.review_id, assessment.id
        )
        assert result is not None
        return result

    async def save_domain_judgment(self, **values: Any) -> RiskOfBiasAssessment:
        assessment: RiskOfBiasAssessment = values.pop("assessment")
        row = await self._session.scalar(
            select(RiskOfBiasDomainJudgmentRecord).where(
                RiskOfBiasDomainJudgmentRecord.assessment_id == assessment.id,
                RiskOfBiasDomainJudgmentRecord.domain_key == values["domain_key"],
            )
        )
        if row is None:
            row = RiskOfBiasDomainJudgmentRecord(
                assessment_id=assessment.id,
                organization_id=assessment.organization_id,
                review_id=assessment.review_id,
                **values,
            )
            self._session.add(row)
        else:
            for key, value in values.items():
                setattr(row, key, value)
        await self._session.flush()
        result = await self.get_assessment(
            assessment.organization_id, assessment.review_id, assessment.id
        )
        assert result is not None
        return result

    async def save_overall(self, **values: Any) -> RiskOfBiasAssessment:
        assessment: RiskOfBiasAssessment = values.pop("assessment")
        row = await self._session.scalar(
            select(RiskOfBiasAssessmentRecord).where(
                RiskOfBiasAssessmentRecord.id == assessment.id,
                RiskOfBiasAssessmentRecord.organization_id == assessment.organization_id,
                RiskOfBiasAssessmentRecord.review_id == assessment.review_id,
            )
        )
        assert row is not None
        for key, value in values.items():
            setattr(row, key, value)
        await self._session.flush()
        return await self._load_assessment(row)

    async def submit_assessment(self, assessment: RiskOfBiasAssessment) -> RiskOfBiasAssessment:
        row = await self._session.scalar(
            select(RiskOfBiasAssessmentRecord).where(
                RiskOfBiasAssessmentRecord.id == assessment.id,
                RiskOfBiasAssessmentRecord.organization_id == assessment.organization_id,
                RiskOfBiasAssessmentRecord.review_id == assessment.review_id,
            )
        )
        assert row is not None
        row.status = AssessmentStatus.SUBMITTED.value
        row.submitted_at = datetime.now(UTC)
        await self._session.flush()
        return await self._load_assessment(row)

    async def get_evidence_article(
        self, organization_id: UUID, review_id: UUID, evidence_location_id: UUID
    ) -> UUID | None:
        return cast(
            UUID | None,
            await self._session.scalar(
                select(DocumentRecord.article_id)
                .join(
                    DocumentEvidenceLocationRecord,
                    DocumentEvidenceLocationRecord.document_id == DocumentRecord.id,
                )
                .where(
                    DocumentEvidenceLocationRecord.id == evidence_location_id,
                    DocumentEvidenceLocationRecord.organization_id == organization_id,
                    DocumentEvidenceLocationRecord.review_id == review_id,
                )
            ),
        )

    async def get_comparison_for_pair(
        self, organization_id: UUID, review_id: UUID, assessment_a_id: UUID, assessment_b_id: UUID
    ) -> RiskOfBiasComparison | None:
        row = await self._session.scalar(
            select(RiskOfBiasComparisonRecord).where(
                RiskOfBiasComparisonRecord.organization_id == organization_id,
                RiskOfBiasComparisonRecord.review_id == review_id,
                or_(
                    RiskOfBiasComparisonRecord.assessment_a_id == assessment_a_id,
                    RiskOfBiasComparisonRecord.assessment_a_id == assessment_b_id,
                ),
                or_(
                    RiskOfBiasComparisonRecord.assessment_b_id == assessment_a_id,
                    RiskOfBiasComparisonRecord.assessment_b_id == assessment_b_id,
                ),
            )
        )
        return await self._comparison(row) if row else None

    async def create_comparison(self, **values: Any) -> RiskOfBiasComparison:
        row = RiskOfBiasComparisonRecord(**values)
        self._session.add(row)
        await self._session.flush()
        return await self._comparison(row)

    async def get_comparison(
        self, organization_id: UUID, review_id: UUID, comparison_id: UUID
    ) -> RiskOfBiasComparison | None:
        row = await self._session.scalar(
            select(RiskOfBiasComparisonRecord).where(
                RiskOfBiasComparisonRecord.organization_id == organization_id,
                RiskOfBiasComparisonRecord.review_id == review_id,
                RiskOfBiasComparisonRecord.id == comparison_id,
            )
        )
        return await self._comparison(row) if row else None

    async def list_comparisons(
        self, organization_id: UUID, review_id: UUID
    ) -> list[RiskOfBiasComparison]:
        rows = await self._session.scalars(
            select(RiskOfBiasComparisonRecord)
            .where(
                RiskOfBiasComparisonRecord.organization_id == organization_id,
                RiskOfBiasComparisonRecord.review_id == review_id,
            )
            .order_by(
                RiskOfBiasComparisonRecord.study_id,
                RiskOfBiasComparisonRecord.instrument_version_id,
                RiskOfBiasComparisonRecord.round_number,
                RiskOfBiasComparisonRecord.id,
            )
        )
        return [await self._comparison(row) for row in rows]

    async def adjudicate(self, **values: Any) -> RiskOfBiasComparison:
        comparison: RiskOfBiasComparison = values.pop("comparison")
        self._session.add(
            RiskOfBiasAdjudicationRecord(
                comparison_id=comparison.id,
                organization_id=comparison.organization_id,
                review_id=comparison.review_id,
                **values,
            )
        )
        await self._session.flush()
        result = await self.get_comparison(
            comparison.organization_id, comparison.review_id, comparison.id
        )
        assert result is not None
        return result

    @staticmethod
    def _instrument(row: RiskOfBiasInstrumentRecord) -> RiskOfBiasInstrument:
        return RiskOfBiasInstrument(
            row.id,
            row.organization_id,
            row.review_id,
            row.key,
            row.name,
            row.description,
            row.created_by_user_id,
            _time(row.created_at),
        )

    async def _version(self, row: RiskOfBiasInstrumentVersionRecord) -> RiskOfBiasInstrumentVersion:
        decision = await self._session.scalar(
            select(RiskOfBiasInstrumentDecisionRecord.decision).where(
                RiskOfBiasInstrumentDecisionRecord.instrument_version_id == row.id
            )
        )
        return RiskOfBiasInstrumentVersion(
            row.id,
            row.instrument_id,
            row.organization_id,
            row.review_id,
            row.version,
            row.definition,
            row.content_hash,
            row.created_by_user_id,
            _time(row.created_at),
            InstrumentDecision(decision) if decision else None,
        )

    async def _load_assessment(self, row: RiskOfBiasAssessmentRecord) -> RiskOfBiasAssessment:
        answers = list(
            await self._session.scalars(
                select(RiskOfBiasAnswerRecord)
                .where(RiskOfBiasAnswerRecord.assessment_id == row.id)
                .order_by(RiskOfBiasAnswerRecord.question_key)
            )
        )
        domains = list(
            await self._session.scalars(
                select(RiskOfBiasDomainJudgmentRecord)
                .where(RiskOfBiasDomainJudgmentRecord.assessment_id == row.id)
                .order_by(RiskOfBiasDomainJudgmentRecord.domain_key)
            )
        )
        return RiskOfBiasAssessment(
            row.id,
            row.organization_id,
            row.review_id,
            row.study_id,
            row.instrument_version_id,
            row.assessor_user_id,
            row.round_number,
            row.revision,
            row.supersedes_assessment_id,
            AssessmentStatus(row.status),
            row.overall_suggested_judgment,
            row.overall_final_judgment,
            row.overall_rationale,
            row.overall_override_reason,
            row.overall_evidence_location_id,
            _time(row.created_at),
            _time(row.submitted_at) if row.submitted_at else None,
            tuple(
                RiskOfBiasAnswer(
                    item.id,
                    item.assessment_id,
                    item.question_key,
                    item.answer,
                    item.rationale,
                    item.evidence_location_id,
                    _time(item.updated_at),
                )
                for item in answers
            ),
            tuple(
                RiskOfBiasDomainJudgment(
                    item.id,
                    item.assessment_id,
                    item.domain_key,
                    item.suggested_judgment,
                    item.final_judgment,
                    item.rationale,
                    item.override_reason,
                    item.evidence_location_id,
                    _time(item.updated_at),
                )
                for item in domains
            ),
        )

    async def _comparison(self, row: RiskOfBiasComparisonRecord) -> RiskOfBiasComparison:
        adjudication = await self._session.scalar(
            select(RiskOfBiasAdjudicationRecord).where(
                RiskOfBiasAdjudicationRecord.comparison_id == row.id
            )
        )
        return RiskOfBiasComparison(
            row.id,
            row.organization_id,
            row.review_id,
            row.study_id,
            row.instrument_version_id,
            row.round_number,
            row.assessment_a_id,
            row.assessment_b_id,
            ComparisonStatus.ADJUDICATED if adjudication else ComparisonStatus(row.status),
            tuple(row.differences),
            row.compared_by_user_id,
            _time(row.compared_at),
            adjudication.final_snapshot if adjudication else None,
            adjudication.adjudicated_by_user_id if adjudication else None,
            adjudication.rationale if adjudication else None,
            adjudication.evidence_location_id if adjudication else None,
            _time(adjudication.adjudicated_at) if adjudication else None,
        )
