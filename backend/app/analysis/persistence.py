from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
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

from backend.app.analysis.domain import (
    AnalysisArtifact,
    AnalysisSet,
    AnalysisSpecification,
    AnalysisSpecificationVersion,
    MetaAnalysisRun,
    RunStatus,
)
from backend.app.db.base import Base
from backend.app.db.sequence import insert_next_unique_integer
from backend.app.outcomes.domain import (
    AdjustmentStatus,
    AnalysisPopulation,
    EffectEstimate,
    EffectMeasure,
    EstimateOrigin,
    OutcomeMapping,
    SynthesisCandidateSet,
    VarianceScale,
    ZeroEventPattern,
)
from backend.app.outcomes.persistence import (
    EffectEstimateRecord,
    OutcomeMappingRecord,
    SynthesisCandidateSetRecord,
)
from backend.app.studies.persistence import StudyRecord


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


class AnalysisSpecificationRecord(Base):
    __tablename__ = "analysis_specifications"
    __table_args__ = (
        UniqueConstraint("organization_id", "review_id", "key", name="uq_analysis_spec_key"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_analysis_spec_tenant"),
        _review_fk("fk_analysis_spec_review_tenant"),
        _actor_fk("created_by_user_id", "fk_analysis_spec_creator_membership"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    key: Mapped[str] = mapped_column(String(120))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisSpecificationVersionRecord(Base):
    __tablename__ = "analysis_specification_versions"
    __table_args__ = (
        UniqueConstraint("specification_id", "version", name="uq_analysis_spec_version"),
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_analysis_spec_version_tenant"
        ),
        CheckConstraint("version > 0", name="ck_analysis_spec_version_positive"),
        CheckConstraint("length(content_hash) = 64", name="ck_analysis_spec_version_hash"),
        CheckConstraint(
            "effect_measure IN ('RR','OR','RD','MD','SMD','HR','PROPORTION','MEAN','RATE')",
            name="ck_analysis_spec_effect_measure",
        ),
        CheckConstraint(
            "model IN ('FIXED_EFFECT','RANDOM_EFFECTS')", name="ck_analysis_spec_model"
        ),
        CheckConstraint(
            "heterogeneity_estimator IN ('NONE','DERSIMONIAN_LAIRD')",
            name="ck_analysis_spec_estimator",
        ),
        ForeignKeyConstraint(
            ["specification_id", "organization_id", "review_id"],
            [
                "analysis_specifications.id",
                "analysis_specifications.organization_id",
                "analysis_specifications.review_id",
            ],
            name="fk_analysis_spec_version_spec_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["outcome_version_id", "organization_id", "review_id"],
            [
                "outcome_definition_versions.id",
                "outcome_definition_versions.organization_id",
                "outcome_definition_versions.review_id",
            ],
            name="fk_analysis_spec_version_outcome_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["timepoint_window_id", "organization_id", "review_id"],
            [
                "outcome_timepoint_windows.id",
                "outcome_timepoint_windows.organization_id",
                "outcome_timepoint_windows.review_id",
            ],
            name="fk_analysis_spec_version_timepoint_tenant",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_analysis_spec_version_creator_membership"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    specification_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    outcome_version_id: Mapped[UUID] = mapped_column()
    timepoint_window_id: Mapped[UUID | None] = mapped_column()
    effect_measure: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(30))
    heterogeneity_estimator: Mapped[str] = mapped_column(String(40))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisSetRecord(Base):
    __tablename__ = "analysis_sets"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_analysis_set_tenant"),
        CheckConstraint("length(input_hash) = 64", name="ck_analysis_set_hash"),
        ForeignKeyConstraint(
            ["specification_version_id", "organization_id", "review_id"],
            [
                "analysis_specification_versions.id",
                "analysis_specification_versions.organization_id",
                "analysis_specification_versions.review_id",
            ],
            name="fk_analysis_set_spec_version_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["candidate_set_id", "organization_id", "review_id"],
            [
                "synthesis_candidate_sets.id",
                "synthesis_candidate_sets.organization_id",
                "synthesis_candidate_sets.review_id",
            ],
            name="fk_analysis_set_candidate_tenant",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_analysis_set_creator_membership"),
        Index("ix_analysis_set_spec", "organization_id", "review_id", "specification_version_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    specification_version_id: Mapped[UUID] = mapped_column()
    candidate_set_id: Mapped[UUID] = mapped_column()
    included_estimate_ids: Mapped[list[str]] = mapped_column(JSON)
    excluded_estimates: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    input_hash: Mapped[str] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisSetEstimateRecord(Base):
    __tablename__ = "analysis_set_estimates"
    __table_args__ = (
        UniqueConstraint("analysis_set_id", "estimate_id", name="uq_analysis_set_estimate"),
        UniqueConstraint("analysis_set_id", "ordinal", name="uq_analysis_set_estimate_ordinal"),
        CheckConstraint("ordinal > 0", name="ck_analysis_set_estimate_ordinal"),
        ForeignKeyConstraint(
            ["analysis_set_id", "organization_id", "review_id"],
            ["analysis_sets.id", "analysis_sets.organization_id", "analysis_sets.review_id"],
            name="fk_analysis_set_estimate_set_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["estimate_id", "organization_id", "review_id"],
            [
                "effect_estimates.id",
                "effect_estimates.organization_id",
                "effect_estimates.review_id",
            ],
            name="fk_analysis_set_estimate_effect_tenant",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    analysis_set_id: Mapped[UUID] = mapped_column()
    estimate_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    ordinal: Mapped[int] = mapped_column(Integer)


class MetaAnalysisRunRecord(Base):
    __tablename__ = "meta_analysis_runs"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_meta_run_tenant"),
        CheckConstraint(
            "status IN ('PLANNED','RUNNING','COMPLETED','FAILED')", name="ck_meta_run_status"
        ),
        CheckConstraint("length(input_hash) = 64", name="ck_meta_run_input_hash"),
        CheckConstraint(
            "result_hash IS NULL OR length(result_hash) = 64", name="ck_meta_run_result_hash"
        ),
        CheckConstraint(
            "(status = 'COMPLETED' AND result_hash IS NOT NULL "
            "AND completed_at IS NOT NULL AND failure_reason IS NULL) OR "
            "(status = 'FAILED' AND result_hash IS NULL "
            "AND completed_at IS NOT NULL AND failure_reason IS NOT NULL) OR "
            "(status IN ('PLANNED','RUNNING') AND result_hash IS NULL "
            "AND completed_at IS NULL)",
            name="ck_meta_run_terminal_state",
        ),
        ForeignKeyConstraint(
            ["specification_version_id", "organization_id", "review_id"],
            [
                "analysis_specification_versions.id",
                "analysis_specification_versions.organization_id",
                "analysis_specification_versions.review_id",
            ],
            name="fk_meta_run_spec_version_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["analysis_set_id", "organization_id", "review_id"],
            ["analysis_sets.id", "analysis_sets.organization_id", "analysis_sets.review_id"],
            name="fk_meta_run_analysis_set_tenant",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_meta_run_creator_membership"),
        Index("ix_meta_run_analysis_set", "organization_id", "review_id", "analysis_set_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    specification_version_id: Mapped[UUID] = mapped_column()
    analysis_set_id: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(20))
    algorithm_name: Mapped[str] = mapped_column(String(100))
    algorithm_version: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(100))
    provider_version: Mapped[str] = mapped_column(String(100))
    input_hash: Mapped[str] = mapped_column(String(64))
    result_hash: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    diagnostics: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MetaAnalysisStudyWeightRecord(Base):
    __tablename__ = "meta_analysis_study_weights"
    __table_args__ = (
        UniqueConstraint("run_id", "study_id", name="uq_meta_weight_study"),
        UniqueConstraint("run_id", "estimate_id", name="uq_meta_weight_estimate"),
        ForeignKeyConstraint(
            ["run_id", "organization_id", "review_id"],
            [
                "meta_analysis_runs.id",
                "meta_analysis_runs.organization_id",
                "meta_analysis_runs.review_id",
            ],
            name="fk_meta_weight_run_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_meta_weight_study_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["estimate_id", "organization_id", "review_id"],
            [
                "effect_estimates.id",
                "effect_estimates.organization_id",
                "effect_estimates.review_id",
            ],
            name="fk_meta_weight_estimate_tenant",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    study_id: Mapped[UUID] = mapped_column()
    estimate_id: Mapped[UUID] = mapped_column()
    analysis_estimate: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    presentation_estimate: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    ci_lower: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    ci_upper: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    raw_weight: Mapped[Decimal] = mapped_column(Numeric(38, 12))
    normalized_weight_percent: Mapped[Decimal] = mapped_column(Numeric(38, 12))


class MetaAnalysisSensitivityRecord(Base):
    __tablename__ = "meta_analysis_sensitivity_results"
    __table_args__ = (
        UniqueConstraint("run_id", "omitted_study_id", name="uq_meta_sensitivity_study"),
        CheckConstraint("length(result_hash) = 64", name="ck_meta_sensitivity_hash"),
        ForeignKeyConstraint(
            ["run_id", "organization_id", "review_id"],
            [
                "meta_analysis_runs.id",
                "meta_analysis_runs.organization_id",
                "meta_analysis_runs.review_id",
            ],
            name="fk_meta_sensitivity_run_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["omitted_study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_meta_sensitivity_study_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["omitted_estimate_id", "organization_id", "review_id"],
            [
                "effect_estimates.id",
                "effect_estimates.organization_id",
                "effect_estimates.review_id",
            ],
            name="fk_meta_sensitivity_estimate_tenant",
            ondelete="RESTRICT",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    omitted_study_id: Mapped[UUID] = mapped_column()
    omitted_estimate_id: Mapped[UUID] = mapped_column()
    result: Mapped[dict[str, Any]] = mapped_column(JSON)
    result_hash: Mapped[str] = mapped_column(String(64))


class AnalysisArtifactRecord(Base):
    __tablename__ = "analysis_artifacts"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_analysis_artifact_tenant"),
        UniqueConstraint(
            "run_id", "artifact_type", "renderer_version", name="uq_analysis_artifact_run"
        ),
        CheckConstraint("byte_size >= 0", name="ck_analysis_artifact_size"),
        CheckConstraint("length(sha256) = 64", name="ck_analysis_artifact_hash"),
        ForeignKeyConstraint(
            ["run_id", "organization_id", "review_id"],
            [
                "meta_analysis_runs.id",
                "meta_analysis_runs.organization_id",
                "meta_analysis_runs.review_id",
            ],
            name="fk_analysis_artifact_run_tenant",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_analysis_artifact_creator_membership"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    run_id: Mapped[UUID] = mapped_column()
    artifact_type: Mapped[str] = mapped_column(String(40))
    renderer_version: Mapped[str] = mapped_column(String(100))
    media_type: Mapped[str] = mapped_column(String(100))
    filename: Mapped[str] = mapped_column(String(255))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _reject_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("statistical scientific history is append-only")


def _protect_terminal_run(_: Mapper[Any], __: object, target: MetaAnalysisRunRecord) -> None:
    history = inspect(target).attrs.status.history
    old_status = history.deleted[0] if history.deleted else target.status
    if old_status in (RunStatus.COMPLETED.value, RunStatus.FAILED.value):
        raise TypeError("terminal meta-analysis runs are immutable")


for _immutable in (
    AnalysisSpecificationRecord,
    AnalysisSpecificationVersionRecord,
    AnalysisSetRecord,
    AnalysisSetEstimateRecord,
    MetaAnalysisStudyWeightRecord,
    MetaAnalysisSensitivityRecord,
    AnalysisArtifactRecord,
):
    event.listen(_immutable, "before_update", _reject_mutation)
    event.listen(_immutable, "before_delete", _reject_mutation)

event.listen(MetaAnalysisRunRecord, "before_update", _protect_terminal_run)
event.listen(MetaAnalysisRunRecord, "before_delete", _reject_mutation)


def _time(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class SqlAlchemyAnalysisRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_specification(self, **values: Any) -> AnalysisSpecification:
        row = AnalysisSpecificationRecord(**values)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._specification(row)

    async def get_specification(
        self, organization_id: UUID, review_id: UUID, specification_id: UUID
    ) -> AnalysisSpecification | None:
        row = await self._session.scalar(
            select(AnalysisSpecificationRecord).where(
                AnalysisSpecificationRecord.organization_id == organization_id,
                AnalysisSpecificationRecord.review_id == review_id,
                AnalysisSpecificationRecord.id == specification_id,
            )
        )
        return self._specification(row) if row else None

    async def list_specifications(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AnalysisSpecification]:
        rows = await self._session.scalars(
            select(AnalysisSpecificationRecord)
            .where(
                AnalysisSpecificationRecord.organization_id == organization_id,
                AnalysisSpecificationRecord.review_id == review_id,
            )
            .order_by(AnalysisSpecificationRecord.key, AnalysisSpecificationRecord.id)
        )
        return [self._specification(row) for row in rows]

    async def create_specification_version(self, **values: Any) -> AnalysisSpecificationVersion:
        async def next_version() -> int:
            latest = await self._session.scalar(
                select(func.max(AnalysisSpecificationVersionRecord.version)).where(
                    AnalysisSpecificationVersionRecord.specification_id
                    == values["specification_id"]
                )
            )
            return int(latest or 0) + 1

        row = await insert_next_unique_integer(
            self._session,
            next_version,
            lambda version: AnalysisSpecificationVersionRecord(version=version, **values),
        )
        result = await self.get_specification_version(row.organization_id, row.review_id, row.id)
        assert result is not None
        return result

    async def get_specification_version(
        self, organization_id: UUID, review_id: UUID, version_id: UUID
    ) -> AnalysisSpecificationVersion | None:
        row = await self._session.scalar(
            select(AnalysisSpecificationVersionRecord).where(
                AnalysisSpecificationVersionRecord.organization_id == organization_id,
                AnalysisSpecificationVersionRecord.review_id == review_id,
                AnalysisSpecificationVersionRecord.id == version_id,
            )
        )
        return self._version(row) if row else None

    async def list_specification_versions(
        self, organization_id: UUID, review_id: UUID, specification_id: UUID | None = None
    ) -> list[AnalysisSpecificationVersion]:
        statement = select(AnalysisSpecificationVersionRecord).where(
            AnalysisSpecificationVersionRecord.organization_id == organization_id,
            AnalysisSpecificationVersionRecord.review_id == review_id,
        )
        if specification_id is not None:
            statement = statement.where(
                AnalysisSpecificationVersionRecord.specification_id == specification_id
            )
        rows = await self._session.scalars(
            statement.order_by(
                AnalysisSpecificationVersionRecord.specification_id,
                AnalysisSpecificationVersionRecord.version,
            )
        )
        return [self._version(row) for row in rows]

    async def get_candidate_set(
        self, organization_id: UUID, review_id: UUID, candidate_set_id: UUID
    ) -> SynthesisCandidateSet | None:
        row = await self._session.scalar(
            select(SynthesisCandidateSetRecord).where(
                SynthesisCandidateSetRecord.organization_id == organization_id,
                SynthesisCandidateSetRecord.review_id == review_id,
                SynthesisCandidateSetRecord.id == candidate_set_id,
            )
        )
        return self._candidate(row) if row else None

    async def get_effect_estimate(
        self, organization_id: UUID, review_id: UUID, estimate_id: UUID
    ) -> EffectEstimate | None:
        row = await self._session.scalar(
            select(EffectEstimateRecord).where(
                EffectEstimateRecord.organization_id == organization_id,
                EffectEstimateRecord.review_id == review_id,
                EffectEstimateRecord.id == estimate_id,
            )
        )
        return self._estimate(row) if row else None

    async def get_mapping(
        self, organization_id: UUID, review_id: UUID, mapping_id: UUID
    ) -> OutcomeMapping | None:
        row = await self._session.scalar(
            select(OutcomeMappingRecord).where(
                OutcomeMappingRecord.organization_id == organization_id,
                OutcomeMappingRecord.review_id == review_id,
                OutcomeMappingRecord.id == mapping_id,
            )
        )
        return self._mapping(row) if row else None

    async def mapping_is_superseded(
        self, organization_id: UUID, review_id: UUID, mapping_id: UUID
    ) -> bool:
        return (
            await self._session.scalar(
                select(OutcomeMappingRecord.id).where(
                    OutcomeMappingRecord.organization_id == organization_id,
                    OutcomeMappingRecord.review_id == review_id,
                    OutcomeMappingRecord.supersedes_mapping_id == mapping_id,
                )
            )
            is not None
        )

    async def study_label(
        self, organization_id: UUID, review_id: UUID, study_id: UUID
    ) -> str | None:
        return await self._session.scalar(
            select(StudyRecord.label).where(
                StudyRecord.organization_id == organization_id,
                StudyRecord.review_id == review_id,
                StudyRecord.id == study_id,
            )
        )

    async def study_design(
        self, organization_id: UUID, review_id: UUID, study_id: UUID
    ) -> str | None:
        return await self._session.scalar(
            select(StudyRecord.study_design).where(
                StudyRecord.organization_id == organization_id,
                StudyRecord.review_id == review_id,
                StudyRecord.id == study_id,
            )
        )

    async def create_analysis_set(self, **values: Any) -> AnalysisSet:
        estimate_ids = [UUID(item) for item in values["included_estimate_ids"]]
        row = AnalysisSetRecord(**values)
        self._session.add(row)
        await self._session.flush()
        self._session.add_all(
            AnalysisSetEstimateRecord(
                analysis_set_id=row.id,
                estimate_id=estimate_id,
                organization_id=row.organization_id,
                review_id=row.review_id,
                ordinal=ordinal,
            )
            for ordinal, estimate_id in enumerate(estimate_ids, start=1)
        )
        await self._session.flush()
        await self._session.refresh(row)
        return self._analysis_set(row)

    async def get_analysis_set(
        self, organization_id: UUID, review_id: UUID, analysis_set_id: UUID
    ) -> AnalysisSet | None:
        row = await self._session.scalar(
            select(AnalysisSetRecord).where(
                AnalysisSetRecord.organization_id == organization_id,
                AnalysisSetRecord.review_id == review_id,
                AnalysisSetRecord.id == analysis_set_id,
            )
        )
        return self._analysis_set(row) if row else None

    async def list_analysis_sets(self, organization_id: UUID, review_id: UUID) -> list[AnalysisSet]:
        rows = await self._session.scalars(
            select(AnalysisSetRecord)
            .where(
                AnalysisSetRecord.organization_id == organization_id,
                AnalysisSetRecord.review_id == review_id,
            )
            .order_by(AnalysisSetRecord.created_at, AnalysisSetRecord.id)
        )
        return [self._analysis_set(row) for row in rows]

    async def create_run(self, **values: Any) -> MetaAnalysisRun:
        row = MetaAnalysisRunRecord(**values)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._run(row)

    async def mark_run_running(self, run_id: UUID) -> MetaAnalysisRun:
        row = await self._run_record(run_id)
        row.status = RunStatus.RUNNING.value
        row.started_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(row)
        return self._run(row)

    async def complete_run(
        self,
        run_id: UUID,
        *,
        result_hash: str,
        result: dict[str, Any],
        diagnostics: list[dict[str, Any]],
        weights: list[dict[str, Any]],
        sensitivities: list[dict[str, Any]],
    ) -> MetaAnalysisRun:
        row = await self._run_record(run_id)
        row.status = RunStatus.COMPLETED.value
        row.result_hash = result_hash
        row.result = result
        row.diagnostics = diagnostics
        row.completed_at = datetime.now(UTC)
        self._session.add_all(
            MetaAnalysisStudyWeightRecord(
                run_id=row.id,
                organization_id=row.organization_id,
                review_id=row.review_id,
                **weight,
            )
            for weight in weights
        )
        self._session.add_all(
            MetaAnalysisSensitivityRecord(
                run_id=row.id,
                organization_id=row.organization_id,
                review_id=row.review_id,
                **sensitivity,
            )
            for sensitivity in sensitivities
        )
        await self._session.flush()
        await self._session.refresh(row)
        return self._run(row)

    async def fail_run(
        self, run_id: UUID, *, failure_reason: str, diagnostics: list[dict[str, Any]]
    ) -> MetaAnalysisRun:
        row = await self._run_record(run_id)
        row.status = RunStatus.FAILED.value
        row.failure_reason = failure_reason
        row.diagnostics = diagnostics
        row.completed_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(row)
        return self._run(row)

    async def get_run(
        self, organization_id: UUID, review_id: UUID, run_id: UUID
    ) -> MetaAnalysisRun | None:
        row = await self._session.scalar(
            select(MetaAnalysisRunRecord).where(
                MetaAnalysisRunRecord.organization_id == organization_id,
                MetaAnalysisRunRecord.review_id == review_id,
                MetaAnalysisRunRecord.id == run_id,
            )
        )
        return self._run(row) if row else None

    async def list_runs(self, organization_id: UUID, review_id: UUID) -> list[MetaAnalysisRun]:
        rows = await self._session.scalars(
            select(MetaAnalysisRunRecord)
            .where(
                MetaAnalysisRunRecord.organization_id == organization_id,
                MetaAnalysisRunRecord.review_id == review_id,
            )
            .order_by(MetaAnalysisRunRecord.created_at, MetaAnalysisRunRecord.id)
        )
        return [self._run(row) for row in rows]

    async def create_artifact(self, **values: Any) -> AnalysisArtifact:
        row = AnalysisArtifactRecord(**values)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._artifact(row)

    async def get_artifact(
        self, organization_id: UUID, review_id: UUID, artifact_id: UUID
    ) -> AnalysisArtifact | None:
        row = await self._session.scalar(
            select(AnalysisArtifactRecord).where(
                AnalysisArtifactRecord.organization_id == organization_id,
                AnalysisArtifactRecord.review_id == review_id,
                AnalysisArtifactRecord.id == artifact_id,
            )
        )
        return self._artifact(row) if row else None

    async def list_artifacts(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AnalysisArtifact]:
        rows = await self._session.scalars(
            select(AnalysisArtifactRecord)
            .where(
                AnalysisArtifactRecord.organization_id == organization_id,
                AnalysisArtifactRecord.review_id == review_id,
            )
            .order_by(AnalysisArtifactRecord.created_at, AnalysisArtifactRecord.id)
        )
        return [self._artifact(row) for row in rows]

    async def _run_record(self, run_id: UUID) -> MetaAnalysisRunRecord:
        row = await self._session.get(MetaAnalysisRunRecord, run_id)
        if row is None:
            raise LookupError("meta-analysis run was not found")
        return row

    @staticmethod
    def _specification(row: AnalysisSpecificationRecord) -> AnalysisSpecification:
        return AnalysisSpecification(
            row.id,
            row.organization_id,
            row.review_id,
            row.key,
            row.created_by_user_id,
            _time(row.created_at),
        )

    @staticmethod
    def _version(row: AnalysisSpecificationVersionRecord) -> AnalysisSpecificationVersion:
        return AnalysisSpecificationVersion(
            row.id,
            row.specification_id,
            row.organization_id,
            row.review_id,
            row.version,
            row.definition,
            row.content_hash,
            row.created_by_user_id,
            _time(row.created_at),
        )

    @staticmethod
    def _analysis_set(row: AnalysisSetRecord) -> AnalysisSet:
        return AnalysisSet(
            row.id,
            row.organization_id,
            row.review_id,
            row.specification_version_id,
            row.candidate_set_id,
            tuple(UUID(item) for item in row.included_estimate_ids),
            tuple(row.excluded_estimates),
            row.input_hash,
            row.created_by_user_id,
            _time(row.created_at),
        )

    @staticmethod
    def _run(row: MetaAnalysisRunRecord) -> MetaAnalysisRun:
        return MetaAnalysisRun(
            row.id,
            row.organization_id,
            row.review_id,
            row.specification_version_id,
            row.analysis_set_id,
            RunStatus(row.status),
            row.algorithm_name,
            row.algorithm_version,
            row.provider,
            row.provider_version,
            row.input_hash,
            row.result_hash,
            row.result,
            tuple(row.diagnostics),
            row.failure_reason,
            row.created_by_user_id,
            _time(row.started_at) if row.started_at else None,
            _time(row.completed_at) if row.completed_at else None,
            _time(row.created_at),
        )

    @staticmethod
    def _artifact(row: AnalysisArtifactRecord) -> AnalysisArtifact:
        return AnalysisArtifact(
            row.id,
            row.organization_id,
            row.review_id,
            row.run_id,
            row.artifact_type,
            row.renderer_version,
            row.media_type,
            row.filename,
            bytes(row.content),
            row.sha256,
            row.byte_size,
            row.created_by_user_id,
            _time(row.created_at),
        )

    @staticmethod
    def _candidate(row: SynthesisCandidateSetRecord) -> SynthesisCandidateSet:
        return SynthesisCandidateSet(
            row.id,
            row.organization_id,
            row.review_id,
            row.outcome_version_id,
            EffectMeasure(row.effect_measure),
            row.timepoint_window_id,
            row.population_label,
            tuple(UUID(item) for item in row.estimate_ids),
            row.created_by_user_id,
            _time(row.created_at),
        )

    @staticmethod
    def _estimate(row: EffectEstimateRecord) -> EffectEstimate:
        return EffectEstimate(
            row.id,
            row.organization_id,
            row.review_id,
            row.study_id,
            row.outcome_version_id,
            EffectMeasure(row.effect_measure),
            EstimateOrigin(row.origin),
            str(row.estimate) if row.estimate is not None else None,
            str(row.standard_error) if row.standard_error is not None else None,
            str(row.variance) if row.variance is not None else None,
            VarianceScale(row.variance_scale),
            str(row.ci_lower) if row.ci_lower is not None else None,
            str(row.ci_upper) if row.ci_upper is not None else None,
            str(row.confidence_level) if row.confidence_level is not None else None,
            AdjustmentStatus(row.adjustment),
            AnalysisPopulation(row.analysis_population),
            row.covariates,
            row.model_description,
            row.timepoint_window_id,
            row.unit_id,
            row.measurement_scale_id,
            dict(row.components),
            tuple(UUID(item) for item in row.source_mapping_ids),
            row.source_evidence_location_id,
            row.calculation_version,
            ZeroEventPattern(row.zero_event_pattern),
            row.created_by_user_id,
            _time(row.created_at),
        )

    @staticmethod
    def _mapping(row: OutcomeMappingRecord) -> OutcomeMapping:
        from backend.app.outcomes.persistence import SqlAlchemyOutcomeRepository

        return SqlAlchemyOutcomeRepository._mapping(row)
