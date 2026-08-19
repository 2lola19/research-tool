from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
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
    inspect,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from backend.app.certainty.domain import (
    AdjustmentDirection,
    CertaintyAssessment,
    CertaintyAssessmentStatus,
    CertaintyComparison,
    CertaintyComparisonStatus,
    CertaintyDomainJudgment,
    CertaintyFramework,
    CertaintyFrameworkVersion,
    CertaintyLevel,
    DecisionThresholdVersion,
    EvidenceBodyType,
    SummaryOfFindingsSnapshot,
)
from backend.app.db.base import Base
from backend.app.db.sequence import insert_next_unique_integer
from backend.app.documents.persistence import DocumentEvidenceLocationRecord


def _review_fk(name: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["review_id", "organization_id"],
        ["reviews.id", "reviews.organization_id"],
        name=name,
        ondelete="CASCADE",
    )


def _actor_fk(column: str, name: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["organization_id", column],
        ["memberships.organization_id", "memberships.user_id"],
        name=name,
        ondelete="RESTRICT",
    )


class CertaintyFrameworkRecord(Base):
    __tablename__ = "certainty_frameworks"
    __table_args__ = (
        UniqueConstraint("organization_id", "review_id", "key", name="uq_cert_framework_key"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_cert_framework_tenant"),
        Index("ix_certainty_frameworks_review", "organization_id", "review_id"),
        _review_fk("fk_cert_framework_review"),
        _actor_fk("created_by_user_id", "fk_cert_framework_actor"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    key: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CertaintyFrameworkVersionRecord(Base):
    __tablename__ = "certainty_framework_versions"
    __table_args__ = (
        UniqueConstraint("framework_id", "version", name="uq_cert_framework_version"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_cert_version_tenant"),
        ForeignKeyConstraint(
            ["framework_id", "organization_id", "review_id"],
            [
                "certainty_frameworks.id",
                "certainty_frameworks.organization_id",
                "certainty_frameworks.review_id",
            ],
            name="fk_cert_version_framework",
            ondelete="CASCADE",
        ),
        _actor_fk("created_by_user_id", "fk_cert_version_actor"),
        CheckConstraint("version > 0", name="ck_cert_version_positive"),
        CheckConstraint("length(content_hash) = 64", name="ck_cert_version_hash"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    framework_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DecisionThresholdVersionRecord(Base):
    __tablename__ = "certainty_threshold_versions"
    __table_args__ = (
        UniqueConstraint("outcome_version_id", "version", name="uq_cert_threshold_version"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_cert_threshold_tenant"),
        ForeignKeyConstraint(
            ["outcome_version_id", "organization_id", "review_id"],
            [
                "outcome_definition_versions.id",
                "outcome_definition_versions.organization_id",
                "outcome_definition_versions.review_id",
            ],
            name="fk_cert_threshold_outcome",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_cert_threshold_actor"),
        CheckConstraint("version > 0", name="ck_cert_threshold_version"),
        CheckConstraint("length(content_hash) = 64", name="ck_cert_threshold_hash"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    outcome_version_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CertaintyAssessmentRecord(Base):
    __tablename__ = "certainty_assessments"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_cert_assessment_tenant"),
        Index(
            "ix_certainty_assessments_review",
            "organization_id",
            "review_id",
            "outcome_version_id",
        ),
        UniqueConstraint(
            "review_id",
            "outcome_version_id",
            "framework_version_id",
            "assessor_user_id",
            "round_number",
            "revision",
            name="uq_cert_assessment_revision",
        ),
        _review_fk("fk_cert_assessment_review"),
        ForeignKeyConstraint(
            ["outcome_version_id", "organization_id", "review_id"],
            [
                "outcome_definition_versions.id",
                "outcome_definition_versions.organization_id",
                "outcome_definition_versions.review_id",
            ],
            name="fk_cert_assessment_outcome",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["timepoint_window_id", "organization_id", "review_id"],
            [
                "outcome_timepoint_windows.id",
                "outcome_timepoint_windows.organization_id",
                "outcome_timepoint_windows.review_id",
            ],
            name="fk_cert_assessment_timepoint",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["analysis_specification_version_id", "organization_id", "review_id"],
            [
                "analysis_specification_versions.id",
                "analysis_specification_versions.organization_id",
                "analysis_specification_versions.review_id",
            ],
            name="fk_cert_assessment_spec",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["meta_analysis_run_id", "organization_id", "review_id"],
            [
                "meta_analysis_runs.id",
                "meta_analysis_runs.organization_id",
                "meta_analysis_runs.review_id",
            ],
            name="fk_cert_assessment_run",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["framework_version_id", "organization_id", "review_id"],
            [
                "certainty_framework_versions.id",
                "certainty_framework_versions.organization_id",
                "certainty_framework_versions.review_id",
            ],
            name="fk_cert_assessment_framework",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["threshold_version_id", "organization_id", "review_id"],
            [
                "certainty_threshold_versions.id",
                "certainty_threshold_versions.organization_id",
                "certainty_threshold_versions.review_id",
            ],
            name="fk_cert_assessment_threshold",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["supersedes_assessment_id", "organization_id", "review_id"],
            [
                "certainty_assessments.id",
                "certainty_assessments.organization_id",
                "certainty_assessments.review_id",
            ],
            name="fk_cert_assessment_supersedes",
            ondelete="RESTRICT",
        ),
        _actor_fk("assessor_user_id", "fk_cert_assessment_assessor"),
        CheckConstraint("round_number > 0 AND revision > 0", name="ck_cert_assessment_numbers"),
        CheckConstraint("status IN ('IN_PROGRESS','SUBMITTED')", name="ck_cert_assessment_status"),
        CheckConstraint(
            "evidence_body_type IN ('RANDOMIZED','OBSERVATIONAL','MIXED','OTHER')",
            name="ck_cert_evidence_body_type",
        ),
        CheckConstraint(
            "starting_certainty IN ('HIGH','MODERATE','LOW','VERY_LOW')", name="ck_cert_starting"
        ),
        CheckConstraint(
            "candidate_certainty IS NULL OR "
            "candidate_certainty IN ('HIGH','MODERATE','LOW','VERY_LOW')",
            name="ck_cert_candidate",
        ),
        CheckConstraint(
            "final_certainty IS NULL OR final_certainty IN ('HIGH','MODERATE','LOW','VERY_LOW')",
            name="ck_cert_final",
        ),
        CheckConstraint(
            "evidence_hash IS NULL OR length(evidence_hash) = 64", name="ck_cert_evidence_hash"
        ),
        CheckConstraint(
            "(status = 'IN_PROGRESS' AND submitted_at IS NULL) OR "
            "(status = 'SUBMITTED' AND submitted_at IS NOT NULL "
            "AND candidate_certainty IS NOT NULL AND final_certainty IS NOT NULL "
            "AND final_rationale IS NOT NULL AND evidence_snapshot IS NOT NULL "
            "AND evidence_hash IS NOT NULL)",
            name="ck_cert_submission",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    outcome_version_id: Mapped[UUID] = mapped_column()
    timepoint_window_id: Mapped[UUID | None] = mapped_column()
    analysis_specification_version_id: Mapped[UUID | None] = mapped_column()
    meta_analysis_run_id: Mapped[UUID | None] = mapped_column()
    framework_version_id: Mapped[UUID] = mapped_column()
    threshold_version_id: Mapped[UUID | None] = mapped_column()
    assessor_user_id: Mapped[UUID] = mapped_column()
    round_number: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer)
    supersedes_assessment_id: Mapped[UUID | None] = mapped_column()
    evidence_body_type: Mapped[str] = mapped_column(String(30))
    evidence_body: Mapped[dict[str, Any]] = mapped_column(JSON)
    starting_certainty: Mapped[str] = mapped_column(String(20))
    starting_rationale: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))
    candidate_certainty: Mapped[str | None] = mapped_column(String(20))
    final_certainty: Mapped[str | None] = mapped_column(String(20))
    final_rationale: Mapped[str | None] = mapped_column(Text)
    override_reason: Mapped[str | None] = mapped_column(Text)
    evidence_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    evidence_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CertaintyDomainJudgmentRecord(Base):
    __tablename__ = "certainty_domain_judgments"
    __table_args__ = (
        UniqueConstraint("assessment_id", "domain_key", name="uq_cert_domain_assessment"),
        ForeignKeyConstraint(
            ["assessment_id", "organization_id", "review_id"],
            [
                "certainty_assessments.id",
                "certainty_assessments.organization_id",
                "certainty_assessments.review_id",
            ],
            name="fk_cert_domain_assessment",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["evidence_location_id", "organization_id", "review_id"],
            [
                "document_evidence_locations.id",
                "document_evidence_locations.organization_id",
                "document_evidence_locations.review_id",
            ],
            name="fk_cert_domain_evidence",
            ondelete="RESTRICT",
        ),
        CheckConstraint("direction IN ('DOWNGRADE','UPGRADE')", name="ck_cert_domain_direction"),
        CheckConstraint("magnitude >= 0 AND magnitude <= 2", name="ck_cert_domain_magnitude"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    assessment_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    domain_key: Mapped[str] = mapped_column(String(120))
    direction: Mapped[str] = mapped_column(String(20))
    magnitude: Mapped[int] = mapped_column(Integer)
    judgment: Mapped[str] = mapped_column(String(120))
    rationale: Mapped[str] = mapped_column(Text)
    evidence_location_id: Mapped[UUID | None] = mapped_column()
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CertaintyComparisonRecord(Base):
    __tablename__ = "certainty_comparisons"
    __table_args__ = (
        UniqueConstraint("assessment_a_id", "assessment_b_id", name="uq_cert_comparison_pair"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_cert_comparison_tenant"),
        Index("ix_certainty_comparisons_review", "organization_id", "review_id"),
        _review_fk("fk_cert_comparison_review"),
        ForeignKeyConstraint(
            ["outcome_version_id", "organization_id", "review_id"],
            [
                "outcome_definition_versions.id",
                "outcome_definition_versions.organization_id",
                "outcome_definition_versions.review_id",
            ],
            name="fk_cert_comparison_outcome",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["framework_version_id", "organization_id", "review_id"],
            [
                "certainty_framework_versions.id",
                "certainty_framework_versions.organization_id",
                "certainty_framework_versions.review_id",
            ],
            name="fk_cert_comparison_framework",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["adjudication_evidence_location_id", "organization_id", "review_id"],
            [
                "document_evidence_locations.id",
                "document_evidence_locations.organization_id",
                "document_evidence_locations.review_id",
            ],
            name="fk_cert_adjudication_evidence",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assessment_a_id", "organization_id", "review_id"],
            [
                "certainty_assessments.id",
                "certainty_assessments.organization_id",
                "certainty_assessments.review_id",
            ],
            name="fk_cert_comparison_a",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["assessment_b_id", "organization_id", "review_id"],
            [
                "certainty_assessments.id",
                "certainty_assessments.organization_id",
                "certainty_assessments.review_id",
            ],
            name="fk_cert_comparison_b",
            ondelete="RESTRICT",
        ),
        _actor_fk("compared_by_user_id", "fk_cert_comparison_actor"),
        _actor_fk("adjudicated_by_user_id", "fk_cert_adjudication_actor"),
        CheckConstraint(
            "status IN ('AGREEMENT','CONFLICT','ADJUDICATED')", name="ck_cert_comparison_status"
        ),
        CheckConstraint("assessment_a_id <> assessment_b_id", name="ck_cert_comparison_distinct"),
        CheckConstraint(
            "(status <> 'ADJUDICATED' AND adjudicated_by_user_id IS NULL "
            "AND adjudication_reason IS NULL "
            "AND adjudicated_at IS NULL) OR "
            "(status = 'ADJUDICATED' AND adjudicated_by_user_id IS NOT NULL "
            "AND adjudication_reason IS NOT NULL "
            "AND adjudicated_at IS NOT NULL)",
            name="ck_cert_adjudication_complete",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    outcome_version_id: Mapped[UUID] = mapped_column()
    framework_version_id: Mapped[UUID] = mapped_column()
    round_number: Mapped[int] = mapped_column(Integer)
    assessment_a_id: Mapped[UUID] = mapped_column()
    assessment_b_id: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(20))
    differences: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    compared_by_user_id: Mapped[UUID] = mapped_column()
    compared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    adjudicated_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    adjudicated_by_user_id: Mapped[UUID | None] = mapped_column()
    adjudication_reason: Mapped[str | None] = mapped_column(Text)
    adjudication_evidence_location_id: Mapped[UUID | None] = mapped_column()
    adjudicated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SummaryOfFindingsSnapshotRecord(Base):
    __tablename__ = "summary_of_findings_snapshots"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_sof_snapshot_tenant"),
        Index("ix_summary_of_findings_snapshots_review", "organization_id", "review_id"),
        ForeignKeyConstraint(
            ["assessment_id", "organization_id", "review_id"],
            [
                "certainty_assessments.id",
                "certainty_assessments.organization_id",
                "certainty_assessments.review_id",
            ],
            name="fk_sof_assessment",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_sof_actor"),
        CheckConstraint("length(content_hash) = 64", name="ck_sof_hash"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    assessment_id: Mapped[UUID] = mapped_column()
    model_version: Mapped[str] = mapped_column(String(100))
    row: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


IMMUTABLE = (
    CertaintyFrameworkVersionRecord,
    DecisionThresholdVersionRecord,
    SummaryOfFindingsSnapshotRecord,
)


@event.listens_for(Mapper, "before_update")
def _protect_certainty_history(_mapper: Mapper[Any], _connection: Any, target: object) -> None:
    if isinstance(target, IMMUTABLE):
        raise ValueError("certainty scientific versions and snapshots are immutable")
    if isinstance(target, CertaintyAssessmentRecord):
        state = inspect(target)
        old_status = state.attrs.status.history.deleted
        if old_status and old_status[0] == CertaintyAssessmentStatus.SUBMITTED.value:
            raise ValueError("submitted certainty assessments are immutable")
    if isinstance(target, CertaintyComparisonRecord):
        state = inspect(target)
        old_status = state.attrs.status.history.deleted
        if old_status and old_status[0] == CertaintyComparisonStatus.ADJUDICATED.value:
            raise ValueError("adjudicated certainty comparisons are immutable")


class SqlAlchemyCertaintyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_framework(self, **values: Any) -> CertaintyFramework:
        row = CertaintyFrameworkRecord(**values)
        self._session.add(row)
        await self._session.flush()
        return self._framework(row)

    async def get_framework(
        self, organization_id: UUID, review_id: UUID, framework_id: UUID
    ) -> CertaintyFramework | None:
        row = await self._session.scalar(
            select(CertaintyFrameworkRecord).where(
                CertaintyFrameworkRecord.organization_id == organization_id,
                CertaintyFrameworkRecord.review_id == review_id,
                CertaintyFrameworkRecord.id == framework_id,
            )
        )
        return self._framework(row) if row else None

    async def list_frameworks(
        self, organization_id: UUID, review_id: UUID
    ) -> list[CertaintyFramework]:
        rows = await self._session.scalars(
            select(CertaintyFrameworkRecord)
            .where(
                CertaintyFrameworkRecord.organization_id == organization_id,
                CertaintyFrameworkRecord.review_id == review_id,
            )
            .order_by(CertaintyFrameworkRecord.key, CertaintyFrameworkRecord.id)
        )
        return [self._framework(row) for row in rows]

    async def create_framework_version(self, **values: Any) -> CertaintyFrameworkVersion:
        async def read_next_version() -> int:
            latest = await self._session.scalar(
                select(func.max(CertaintyFrameworkVersionRecord.version)).where(
                    CertaintyFrameworkVersionRecord.framework_id == values["framework_id"]
                )
            )
            return int(latest or 0) + 1

        row = await insert_next_unique_integer(
            self._session,
            read_next_version,
            lambda version: CertaintyFrameworkVersionRecord(version=version, **values),
        )
        return self._framework_version(row)

    async def get_framework_version(
        self, organization_id: UUID, review_id: UUID, version_id: UUID
    ) -> CertaintyFrameworkVersion | None:
        row = await self._session.scalar(
            select(CertaintyFrameworkVersionRecord).where(
                CertaintyFrameworkVersionRecord.organization_id == organization_id,
                CertaintyFrameworkVersionRecord.review_id == review_id,
                CertaintyFrameworkVersionRecord.id == version_id,
            )
        )
        return self._framework_version(row) if row else None

    async def list_framework_versions(
        self, organization_id: UUID, review_id: UUID, framework_id: UUID | None = None
    ) -> list[CertaintyFrameworkVersion]:
        query = select(CertaintyFrameworkVersionRecord).where(
            CertaintyFrameworkVersionRecord.organization_id == organization_id,
            CertaintyFrameworkVersionRecord.review_id == review_id,
        )
        if framework_id is not None:
            query = query.where(CertaintyFrameworkVersionRecord.framework_id == framework_id)
        rows = await self._session.scalars(
            query.order_by(
                CertaintyFrameworkVersionRecord.framework_id,
                CertaintyFrameworkVersionRecord.version,
            )
        )
        return [self._framework_version(row) for row in rows]

    async def create_threshold_version(self, **values: Any) -> DecisionThresholdVersion:
        async def read_next_version() -> int:
            latest = await self._session.scalar(
                select(func.max(DecisionThresholdVersionRecord.version)).where(
                    DecisionThresholdVersionRecord.outcome_version_id
                    == values["outcome_version_id"]
                )
            )
            return int(latest or 0) + 1

        row = await insert_next_unique_integer(
            self._session,
            read_next_version,
            lambda version: DecisionThresholdVersionRecord(version=version, **values),
        )
        return self._threshold(row)

    async def get_threshold_version(
        self, organization_id: UUID, review_id: UUID, version_id: UUID
    ) -> DecisionThresholdVersion | None:
        row = await self._session.scalar(
            select(DecisionThresholdVersionRecord).where(
                DecisionThresholdVersionRecord.organization_id == organization_id,
                DecisionThresholdVersionRecord.review_id == review_id,
                DecisionThresholdVersionRecord.id == version_id,
            )
        )
        return self._threshold(row) if row else None

    async def list_threshold_versions(
        self, organization_id: UUID, review_id: UUID
    ) -> list[DecisionThresholdVersion]:
        rows = await self._session.scalars(
            select(DecisionThresholdVersionRecord)
            .where(
                DecisionThresholdVersionRecord.organization_id == organization_id,
                DecisionThresholdVersionRecord.review_id == review_id,
            )
            .order_by(
                DecisionThresholdVersionRecord.outcome_version_id,
                DecisionThresholdVersionRecord.version,
            )
        )
        return [self._threshold(row) for row in rows]

    async def create_assessment(self, **values: Any) -> CertaintyAssessment:
        row = CertaintyAssessmentRecord(**values)
        self._session.add(row)
        await self._session.flush()
        return await self._assessment(row)

    async def get_assessment(
        self, organization_id: UUID, review_id: UUID, assessment_id: UUID
    ) -> CertaintyAssessment | None:
        row = await self._session.scalar(
            select(CertaintyAssessmentRecord).where(
                CertaintyAssessmentRecord.organization_id == organization_id,
                CertaintyAssessmentRecord.review_id == review_id,
                CertaintyAssessmentRecord.id == assessment_id,
            )
        )
        return await self._assessment(row) if row else None

    async def list_assessments(
        self, organization_id: UUID, review_id: UUID, assessor_user_id: UUID | None = None
    ) -> list[CertaintyAssessment]:
        query = select(CertaintyAssessmentRecord).where(
            CertaintyAssessmentRecord.organization_id == organization_id,
            CertaintyAssessmentRecord.review_id == review_id,
        )
        if assessor_user_id is not None:
            query = query.where(CertaintyAssessmentRecord.assessor_user_id == assessor_user_id)
        rows = await self._session.scalars(
            query.order_by(CertaintyAssessmentRecord.created_at, CertaintyAssessmentRecord.id)
        )
        return [await self._assessment(row) for row in rows]

    async def save_domain(self, **values: Any) -> CertaintyAssessment:
        assessment: CertaintyAssessment = values.pop("assessment")
        row = await self._session.scalar(
            select(CertaintyDomainJudgmentRecord).where(
                CertaintyDomainJudgmentRecord.assessment_id == assessment.id,
                CertaintyDomainJudgmentRecord.domain_key == values["domain_key"],
            )
        )
        if row is None:
            row = CertaintyDomainJudgmentRecord(
                assessment_id=assessment.id,
                organization_id=assessment.organization_id,
                review_id=assessment.review_id,
                **values,
            )
            self._session.add(row)
        else:
            for key, value in values.items():
                setattr(row, key, value)
            row.updated_at = datetime.now(UTC)
        await self._session.flush()
        current = await self._session.get(CertaintyAssessmentRecord, assessment.id)
        assert current is not None
        return await self._assessment(current)

    async def save_final(self, **values: Any) -> CertaintyAssessment:
        assessment: CertaintyAssessment = values.pop("assessment")
        row = await self._session.get(CertaintyAssessmentRecord, assessment.id)
        assert row is not None
        for key, value in values.items():
            setattr(row, key, value)
        await self._session.flush()
        return await self._assessment(row)

    async def submit(self, **values: Any) -> CertaintyAssessment:
        assessment: CertaintyAssessment = values.pop("assessment")
        row = await self._session.get(CertaintyAssessmentRecord, assessment.id)
        assert row is not None
        for key, value in values.items():
            setattr(row, key, value)
        row.status = CertaintyAssessmentStatus.SUBMITTED.value
        row.submitted_at = datetime.now(UTC)
        await self._session.flush()
        return await self._assessment(row)

    async def create_comparison(self, **values: Any) -> CertaintyComparison:
        row = CertaintyComparisonRecord(**values)
        self._session.add(row)
        await self._session.flush()
        return self._comparison(row)

    async def get_comparison(
        self, organization_id: UUID, review_id: UUID, comparison_id: UUID
    ) -> CertaintyComparison | None:
        row = await self._session.scalar(
            select(CertaintyComparisonRecord).where(
                CertaintyComparisonRecord.organization_id == organization_id,
                CertaintyComparisonRecord.review_id == review_id,
                CertaintyComparisonRecord.id == comparison_id,
            )
        )
        return self._comparison(row) if row else None

    async def get_comparison_for_pair(
        self, organization_id: UUID, review_id: UUID, first_id: UUID, second_id: UUID
    ) -> CertaintyComparison | None:
        row = await self._session.scalar(
            select(CertaintyComparisonRecord).where(
                CertaintyComparisonRecord.organization_id == organization_id,
                CertaintyComparisonRecord.review_id == review_id,
                CertaintyComparisonRecord.assessment_a_id == first_id,
                CertaintyComparisonRecord.assessment_b_id == second_id,
            )
        )
        return self._comparison(row) if row else None

    async def list_comparisons(
        self, organization_id: UUID, review_id: UUID
    ) -> list[CertaintyComparison]:
        rows = await self._session.scalars(
            select(CertaintyComparisonRecord)
            .where(
                CertaintyComparisonRecord.organization_id == organization_id,
                CertaintyComparisonRecord.review_id == review_id,
            )
            .order_by(CertaintyComparisonRecord.compared_at, CertaintyComparisonRecord.id)
        )
        return [self._comparison(row) for row in rows]

    async def adjudicate(self, **values: Any) -> CertaintyComparison:
        comparison: CertaintyComparison = values.pop("comparison")
        row = await self._session.get(CertaintyComparisonRecord, comparison.id)
        assert row is not None
        row.status = CertaintyComparisonStatus.ADJUDICATED.value
        for key, value in values.items():
            setattr(row, key, value)
        row.adjudicated_at = datetime.now(UTC)
        await self._session.flush()
        return self._comparison(row)

    async def create_sof_snapshot(self, **values: Any) -> SummaryOfFindingsSnapshot:
        row = SummaryOfFindingsSnapshotRecord(**values)
        self._session.add(row)
        await self._session.flush()
        return self._sof(row)

    async def list_sof_snapshots(
        self, organization_id: UUID, review_id: UUID
    ) -> list[SummaryOfFindingsSnapshot]:
        rows = await self._session.scalars(
            select(SummaryOfFindingsSnapshotRecord)
            .where(
                SummaryOfFindingsSnapshotRecord.organization_id == organization_id,
                SummaryOfFindingsSnapshotRecord.review_id == review_id,
            )
            .order_by(
                SummaryOfFindingsSnapshotRecord.created_at, SummaryOfFindingsSnapshotRecord.id
            )
        )
        return [self._sof(row) for row in rows]

    async def evidence_location_exists(
        self, organization_id: UUID, review_id: UUID, evidence_location_id: UUID
    ) -> bool:
        return (
            await self._session.scalar(
                select(DocumentEvidenceLocationRecord.id).where(
                    DocumentEvidenceLocationRecord.organization_id == organization_id,
                    DocumentEvidenceLocationRecord.review_id == review_id,
                    DocumentEvidenceLocationRecord.id == evidence_location_id,
                )
            )
            is not None
        )

    async def _assessment(self, row: CertaintyAssessmentRecord) -> CertaintyAssessment:
        domains = await self._session.scalars(
            select(CertaintyDomainJudgmentRecord)
            .where(CertaintyDomainJudgmentRecord.assessment_id == row.id)
            .order_by(CertaintyDomainJudgmentRecord.domain_key)
        )
        return CertaintyAssessment(
            row.id,
            row.organization_id,
            row.review_id,
            row.outcome_version_id,
            row.timepoint_window_id,
            row.analysis_specification_version_id,
            row.meta_analysis_run_id,
            row.framework_version_id,
            row.threshold_version_id,
            row.assessor_user_id,
            row.round_number,
            row.revision,
            row.supersedes_assessment_id,
            EvidenceBodyType(row.evidence_body_type),
            row.evidence_body,
            CertaintyLevel(row.starting_certainty),
            row.starting_rationale,
            CertaintyAssessmentStatus(row.status),
            CertaintyLevel(row.candidate_certainty) if row.candidate_certainty else None,
            CertaintyLevel(row.final_certainty) if row.final_certainty else None,
            row.final_rationale,
            row.override_reason,
            row.evidence_snapshot,
            row.evidence_hash,
            _time(row.created_at),
            _time(row.submitted_at) if row.submitted_at else None,
            tuple(self._domain(item) for item in domains),
        )

    @staticmethod
    def _framework(row: CertaintyFrameworkRecord) -> CertaintyFramework:
        return CertaintyFramework(
            row.id,
            row.organization_id,
            row.review_id,
            row.key,
            row.name,
            row.description,
            row.created_by_user_id,
            _time(row.created_at),
        )

    @staticmethod
    def _framework_version(row: CertaintyFrameworkVersionRecord) -> CertaintyFrameworkVersion:
        return CertaintyFrameworkVersion(
            row.id,
            row.framework_id,
            row.organization_id,
            row.review_id,
            row.version,
            row.definition,
            row.content_hash,
            row.created_by_user_id,
            _time(row.created_at),
        )

    @staticmethod
    def _threshold(row: DecisionThresholdVersionRecord) -> DecisionThresholdVersion:
        return DecisionThresholdVersion(
            row.id,
            row.organization_id,
            row.review_id,
            row.outcome_version_id,
            row.version,
            row.definition,
            row.content_hash,
            row.created_by_user_id,
            _time(row.created_at),
        )

    @staticmethod
    def _domain(row: CertaintyDomainJudgmentRecord) -> CertaintyDomainJudgment:
        return CertaintyDomainJudgment(
            row.id,
            row.assessment_id,
            row.domain_key,
            AdjustmentDirection(row.direction),
            row.magnitude,
            row.judgment,
            row.rationale,
            row.evidence_location_id,
            row.evidence,
            _time(row.updated_at),
        )

    @staticmethod
    def _comparison(row: CertaintyComparisonRecord) -> CertaintyComparison:
        return CertaintyComparison(
            row.id,
            row.organization_id,
            row.review_id,
            row.outcome_version_id,
            row.framework_version_id,
            row.round_number,
            row.assessment_a_id,
            row.assessment_b_id,
            CertaintyComparisonStatus(row.status),
            tuple(row.differences),
            row.compared_by_user_id,
            _time(row.compared_at),
            row.adjudicated_snapshot,
            row.adjudicated_by_user_id,
            row.adjudication_reason,
            row.adjudication_evidence_location_id,
            _time(row.adjudicated_at) if row.adjudicated_at else None,
        )

    @staticmethod
    def _sof(row: SummaryOfFindingsSnapshotRecord) -> SummaryOfFindingsSnapshot:
        return SummaryOfFindingsSnapshot(
            row.id,
            row.organization_id,
            row.review_id,
            row.assessment_id,
            row.model_version,
            row.row,
            row.content_hash,
            row.created_by_user_id,
            _time(row.created_at),
        )


def _time(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
