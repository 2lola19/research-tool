from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from backend.app.db.base import Base
from backend.app.db.sequence import insert_next_unique_integer
from backend.app.documents.persistence import DocumentEvidenceLocationRecord, DocumentRecord
from backend.app.extraction.manual_persistence import ExtractionRunRecord, ExtractionValueRecord
from backend.app.extraction.verification_persistence import ExtractionVerificationRecord
from backend.app.outcomes.domain import (
    AdjustmentStatus,
    AnalysisPopulation,
    AnalysisReadinessSnapshot,
    Directionality,
    DirectionTransformation,
    EffectEstimate,
    EffectMeasure,
    EstimateOrigin,
    MappingMethod,
    MeasurementScale,
    OutcomeDefinition,
    OutcomeDefinitionVersion,
    OutcomeMapping,
    ReadinessStatus,
    SynthesisCandidateSet,
    TimeAnchor,
    TimepointWindow,
    TimeUnit,
    UnitDefinition,
    VarianceScale,
    ZeroEventPattern,
)
from backend.app.protocols.persistence import ProtocolVersionRecord


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


class OutcomeDefinitionRecord(Base):
    __tablename__ = "outcome_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "review_id", "key", name="uq_outcome_key"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_outcome_id_tenant"),
        _review_fk("fk_outcome_review_tenant"),
        _actor_fk("created_by_user_id", "fk_outcome_creator_membership"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    key: Mapped[str] = mapped_column(String(120))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


class OutcomeDefinitionVersionRecord(Base):
    __tablename__ = "outcome_definition_versions"
    __table_args__ = (
        UniqueConstraint("outcome_id", "version", name="uq_outcome_version_number"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_outcome_version_tenant"),
        CheckConstraint("version > 0", name="ck_outcome_version_positive"),
        CheckConstraint("length(content_hash) = 64", name="ck_outcome_version_hash"),
        ForeignKeyConstraint(
            ["outcome_id", "organization_id", "review_id"],
            [
                "outcome_definitions.id",
                "outcome_definitions.organization_id",
                "outcome_definitions.review_id",
            ],
            name="fk_outcome_version_outcome_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["protocol_version_id", "organization_id", "review_id"],
            [
                "protocol_versions.id",
                "protocol_versions.organization_id",
                "protocol_versions.review_id",
            ],
            name="fk_outcome_version_protocol_tenant",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_outcome_version_creator_membership"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    outcome_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    protocol_version_id: Mapped[UUID | None] = mapped_column()
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


class TimepointWindowRecord(Base):
    __tablename__ = "outcome_timepoint_windows"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "review_id", "key", "rule_version", name="uq_timepoint_window_rule"
        ),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_timepoint_window_tenant"),
        CheckConstraint("minimum_days IS NULL OR minimum_days >= 0", name="ck_timepoint_minimum"),
        CheckConstraint("maximum_days IS NULL OR maximum_days >= 0", name="ck_timepoint_maximum"),
        CheckConstraint(
            "minimum_days IS NULL OR maximum_days IS NULL OR minimum_days <= maximum_days",
            name="ck_timepoint_range",
        ),
        CheckConstraint(
            "anchor IN ('BASELINE','RANDOMIZATION','INTERVENTION_START','DIAGNOSIS','OTHER')",
            name="ck_timepoint_anchor",
        ),
        _review_fk("fk_timepoint_window_review_tenant"),
        _actor_fk("created_by_user_id", "fk_timepoint_window_creator_membership"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    key: Mapped[str] = mapped_column(String(120))
    label: Mapped[str] = mapped_column(String(300))
    anchor: Mapped[str] = mapped_column(String(30))
    minimum_days: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    maximum_days: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    rule_version: Mapped[str] = mapped_column(String(100))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


class UnitDefinitionRecord(Base):
    __tablename__ = "outcome_unit_definitions"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "review_id", "key", "rule_version", name="uq_unit_rule"
        ),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_unit_id_tenant"),
        CheckConstraint("multiplier_to_base > 0", name="ck_unit_multiplier_positive"),
        CheckConstraint("precision >= 0 AND precision <= 18", name="ck_unit_precision"),
        _review_fk("fk_unit_review_tenant"),
        _actor_fk("created_by_user_id", "fk_unit_creator_membership"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    key: Mapped[str] = mapped_column(String(120))
    label: Mapped[str] = mapped_column(String(200))
    dimension: Mapped[str] = mapped_column(String(120))
    context_key: Mapped[str] = mapped_column(String(120))
    base_unit_key: Mapped[str] = mapped_column(String(120))
    multiplier_to_base: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    offset_to_base: Mapped[Decimal] = mapped_column(Numeric(38, 18))
    precision: Mapped[int] = mapped_column(Integer)
    rule_version: Mapped[str] = mapped_column(String(100))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


class MeasurementScaleRecord(Base):
    __tablename__ = "outcome_measurement_scales"
    __table_args__ = (
        UniqueConstraint("organization_id", "review_id", "key", name="uq_measurement_scale_key"),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_measurement_scale_tenant"),
        CheckConstraint(
            "minimum IS NULL OR maximum IS NULL OR minimum < maximum",
            name="ck_measurement_scale_range",
        ),
        CheckConstraint(
            "directionality IN "
            "('HIGHER_BETTER','HIGHER_WORSE','NEUTRAL','NOT_APPLICABLE','UNKNOWN')",
            name="ck_measurement_scale_direction",
        ),
        _review_fk("fk_measurement_scale_review_tenant"),
        _actor_fk("created_by_user_id", "fk_measurement_scale_creator_membership"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    key: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(300))
    minimum: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    maximum: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    directionality: Mapped[str] = mapped_column(String(30))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


class OutcomeMappingRecord(Base):
    __tablename__ = "outcome_mappings"
    __table_args__ = (
        Index(
            "ix_outcome_mappings_review_study",
            "organization_id",
            "review_id",
            "study_id",
            "outcome_version_id",
            "id",
        ),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_outcome_mapping_tenant"),
        UniqueConstraint("supersedes_mapping_id", name="uq_outcome_mapping_single_successor"),
        ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_outcome_mapping_study_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["extraction_value_id", "organization_id", "review_id"],
            [
                "extraction_values.id",
                "extraction_values.organization_id",
                "extraction_values.review_id",
            ],
            name="fk_outcome_mapping_extraction_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["outcome_version_id", "organization_id", "review_id"],
            [
                "outcome_definition_versions.id",
                "outcome_definition_versions.organization_id",
                "outcome_definition_versions.review_id",
            ],
            name="fk_outcome_mapping_version_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["reported_unit_id", "organization_id", "review_id"],
            [
                "outcome_unit_definitions.id",
                "outcome_unit_definitions.organization_id",
                "outcome_unit_definitions.review_id",
            ],
            name="fk_outcome_mapping_reported_unit_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["normalized_unit_id", "organization_id", "review_id"],
            [
                "outcome_unit_definitions.id",
                "outcome_unit_definitions.organization_id",
                "outcome_unit_definitions.review_id",
            ],
            name="fk_outcome_mapping_normalized_unit_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["timepoint_window_id", "organization_id", "review_id"],
            [
                "outcome_timepoint_windows.id",
                "outcome_timepoint_windows.organization_id",
                "outcome_timepoint_windows.review_id",
            ],
            name="fk_outcome_mapping_timepoint_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["measurement_scale_id", "organization_id", "review_id"],
            [
                "outcome_measurement_scales.id",
                "outcome_measurement_scales.organization_id",
                "outcome_measurement_scales.review_id",
            ],
            name="fk_outcome_mapping_scale_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["supersedes_mapping_id", "organization_id", "review_id"],
            [
                "outcome_mappings.id",
                "outcome_mappings.organization_id",
                "outcome_mappings.review_id",
            ],
            name="fk_outcome_mapping_successor_tenant",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_outcome_mapping_actor_membership"),
        CheckConstraint(
            "method IN ('MANUAL','DETERMINISTIC_RULE','IMPORTED')",
            name="ck_outcome_mapping_method",
        ),
        CheckConstraint(
            "reported_time_unit IS NULL OR reported_time_unit IN ('DAY','WEEK','MONTH','YEAR')",
            name="ck_outcome_mapping_time_unit",
        ),
        CheckConstraint(
            "reported_time_anchor IS NULL OR reported_time_anchor IN "
            "('BASELINE','RANDOMIZATION','INTERVENTION_START','DIAGNOSIS','OTHER')",
            name="ck_outcome_mapping_time_anchor",
        ),
        CheckConstraint(
            "direction_transformation IN ('NONE','SIGN_REVERSED')",
            name="ck_outcome_mapping_direction_transform",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    study_id: Mapped[UUID] = mapped_column()
    extraction_value_id: Mapped[UUID] = mapped_column()
    outcome_version_id: Mapped[UUID] = mapped_column()
    method: Mapped[str] = mapped_column(String(30))
    rationale: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    reported_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 12))
    reported_unit: Mapped[str | None] = mapped_column(String(120))
    reported_unit_id: Mapped[UUID | None] = mapped_column()
    normalized_value: Mapped[Decimal | None] = mapped_column(Numeric(38, 12))
    normalized_unit_id: Mapped[UUID | None] = mapped_column()
    conversion_rule_version: Mapped[str | None] = mapped_column(String(100))
    reported_time_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    reported_time_unit: Mapped[str | None] = mapped_column(String(20))
    reported_time_anchor: Mapped[str | None] = mapped_column(String(30))
    normalized_time_days: Mapped[Decimal | None] = mapped_column(Numeric(30, 12))
    timepoint_window_id: Mapped[UUID | None] = mapped_column()
    timepoint_rule_version: Mapped[str | None] = mapped_column(String(100))
    measurement_scale_id: Mapped[UUID | None] = mapped_column()
    direction_transformation: Mapped[str] = mapped_column(String(30))
    transformation_reason: Mapped[str | None] = mapped_column(Text)
    extraction_verified: Mapped[bool] = mapped_column(Boolean)
    supersedes_mapping_id: Mapped[UUID | None] = mapped_column()
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


class EffectEstimateRecord(Base):
    __tablename__ = "effect_estimates"
    __table_args__ = (
        Index(
            "ix_effect_estimates_review_outcome",
            "organization_id",
            "review_id",
            "outcome_version_id",
            "study_id",
            "effect_measure",
            "id",
        ),
        UniqueConstraint("id", "organization_id", "review_id", name="uq_effect_estimate_tenant"),
        ForeignKeyConstraint(
            ["study_id", "organization_id", "review_id"],
            ["studies.id", "studies.organization_id", "studies.review_id"],
            name="fk_effect_estimate_study_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["outcome_version_id", "organization_id", "review_id"],
            [
                "outcome_definition_versions.id",
                "outcome_definition_versions.organization_id",
                "outcome_definition_versions.review_id",
            ],
            name="fk_effect_estimate_outcome_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["timepoint_window_id", "organization_id", "review_id"],
            [
                "outcome_timepoint_windows.id",
                "outcome_timepoint_windows.organization_id",
                "outcome_timepoint_windows.review_id",
            ],
            name="fk_effect_estimate_timepoint_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["unit_id", "organization_id", "review_id"],
            [
                "outcome_unit_definitions.id",
                "outcome_unit_definitions.organization_id",
                "outcome_unit_definitions.review_id",
            ],
            name="fk_effect_estimate_unit_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["measurement_scale_id", "organization_id", "review_id"],
            [
                "outcome_measurement_scales.id",
                "outcome_measurement_scales.organization_id",
                "outcome_measurement_scales.review_id",
            ],
            name="fk_effect_estimate_scale_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["source_evidence_location_id", "organization_id", "review_id"],
            [
                "document_evidence_locations.id",
                "document_evidence_locations.organization_id",
                "document_evidence_locations.review_id",
            ],
            name="fk_effect_estimate_evidence_tenant",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_effect_estimate_actor_membership"),
        CheckConstraint(
            "effect_measure IN ('RR','OR','RD','MD','SMD','HR','PROPORTION','MEAN','RATE')",
            name="ck_effect_measure",
        ),
        CheckConstraint("origin IN ('REPORTED','DERIVED')", name="ck_effect_origin"),
        CheckConstraint("variance_scale IN ('NATURAL','LOG')", name="ck_effect_variance_scale"),
        CheckConstraint("adjustment IN ('UNADJUSTED','ADJUSTED')", name="ck_effect_adjustment"),
        CheckConstraint(
            "analysis_population IN "
            "('INTENTION_TO_TREAT','PER_PROTOCOL','MODIFIED_ITT','SAFETY','UNCLEAR','OTHER')",
            name="ck_effect_population",
        ),
        CheckConstraint(
            "zero_event_pattern IN "
            "('NONE','INTERVENTION_ONLY','COMPARATOR_ONLY','DOUBLE_ZERO','BOUNDARY_CELL')",
            name="ck_effect_zero_pattern",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    study_id: Mapped[UUID] = mapped_column()
    outcome_version_id: Mapped[UUID] = mapped_column()
    effect_measure: Mapped[str] = mapped_column(String(30))
    origin: Mapped[str] = mapped_column(String(20))
    estimate: Mapped[Decimal | None] = mapped_column(Numeric(38, 12))
    standard_error: Mapped[Decimal | None] = mapped_column(Numeric(38, 12))
    variance: Mapped[Decimal | None] = mapped_column(Numeric(38, 12))
    variance_scale: Mapped[str] = mapped_column(String(20))
    ci_lower: Mapped[Decimal | None] = mapped_column(Numeric(38, 12))
    ci_upper: Mapped[Decimal | None] = mapped_column(Numeric(38, 12))
    confidence_level: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    adjustment: Mapped[str] = mapped_column(String(20))
    analysis_population: Mapped[str] = mapped_column(String(30))
    covariates: Mapped[str | None] = mapped_column(Text)
    model_description: Mapped[str | None] = mapped_column(Text)
    timepoint_window_id: Mapped[UUID | None] = mapped_column()
    unit_id: Mapped[UUID | None] = mapped_column()
    measurement_scale_id: Mapped[UUID | None] = mapped_column()
    components: Mapped[dict[str, str]] = mapped_column(JSON)
    source_mapping_ids: Mapped[list[str]] = mapped_column(JSON)
    source_evidence_location_id: Mapped[UUID | None] = mapped_column()
    calculation_version: Mapped[str | None] = mapped_column(String(100))
    zero_event_pattern: Mapped[str] = mapped_column(String(30))
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


class EffectEstimateSourceRecord(Base):
    __tablename__ = "effect_estimate_sources"
    __table_args__ = (
        UniqueConstraint("effect_estimate_id", "mapping_id", name="uq_effect_source_mapping"),
        ForeignKeyConstraint(
            ["effect_estimate_id", "organization_id", "review_id"],
            [
                "effect_estimates.id",
                "effect_estimates.organization_id",
                "effect_estimates.review_id",
            ],
            name="fk_effect_source_estimate_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["mapping_id", "organization_id", "review_id"],
            [
                "outcome_mappings.id",
                "outcome_mappings.organization_id",
                "outcome_mappings.review_id",
            ],
            name="fk_effect_source_mapping_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint("ordinal > 0", name="ck_effect_source_ordinal"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    effect_estimate_id: Mapped[UUID] = mapped_column()
    mapping_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    ordinal: Mapped[int] = mapped_column(Integer)


class SynthesisCandidateSetRecord(Base):
    __tablename__ = "synthesis_candidate_sets"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_candidate_set_tenant"),
        ForeignKeyConstraint(
            ["outcome_version_id", "organization_id", "review_id"],
            [
                "outcome_definition_versions.id",
                "outcome_definition_versions.organization_id",
                "outcome_definition_versions.review_id",
            ],
            name="fk_candidate_set_outcome_tenant",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["timepoint_window_id", "organization_id", "review_id"],
            [
                "outcome_timepoint_windows.id",
                "outcome_timepoint_windows.organization_id",
                "outcome_timepoint_windows.review_id",
            ],
            name="fk_candidate_set_timepoint_tenant",
            ondelete="RESTRICT",
        ),
        _actor_fk("created_by_user_id", "fk_candidate_set_actor_membership"),
        CheckConstraint(
            "effect_measure IN ('RR','OR','RD','MD','SMD','HR','PROPORTION','MEAN','RATE')",
            name="ck_candidate_effect_measure",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    outcome_version_id: Mapped[UUID] = mapped_column()
    effect_measure: Mapped[str] = mapped_column(String(30))
    timepoint_window_id: Mapped[UUID | None] = mapped_column()
    population_label: Mapped[str | None] = mapped_column(String(300))
    estimate_ids: Mapped[list[str]] = mapped_column(JSON)
    created_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


class SynthesisCandidateEstimateRecord(Base):
    __tablename__ = "synthesis_candidate_estimates"
    __table_args__ = (
        UniqueConstraint("candidate_set_id", "estimate_id", name="uq_candidate_estimate"),
        ForeignKeyConstraint(
            ["candidate_set_id", "organization_id", "review_id"],
            [
                "synthesis_candidate_sets.id",
                "synthesis_candidate_sets.organization_id",
                "synthesis_candidate_sets.review_id",
            ],
            name="fk_candidate_estimate_set_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["estimate_id", "organization_id", "review_id"],
            [
                "effect_estimates.id",
                "effect_estimates.organization_id",
                "effect_estimates.review_id",
            ],
            name="fk_candidate_estimate_effect_tenant",
            ondelete="RESTRICT",
        ),
        CheckConstraint("ordinal > 0", name="ck_candidate_estimate_ordinal"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_set_id: Mapped[UUID] = mapped_column()
    estimate_id: Mapped[UUID] = mapped_column()
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    ordinal: Mapped[int] = mapped_column(Integer)


class AnalysisReadinessSnapshotRecord(Base):
    __tablename__ = "analysis_readiness_snapshots"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "review_id", name="uq_readiness_snapshot_tenant"),
        ForeignKeyConstraint(
            ["candidate_set_id", "organization_id", "review_id"],
            [
                "synthesis_candidate_sets.id",
                "synthesis_candidate_sets.organization_id",
                "synthesis_candidate_sets.review_id",
            ],
            name="fk_readiness_candidate_tenant",
            ondelete="RESTRICT",
        ),
        _actor_fk("evaluated_by_user_id", "fk_readiness_actor_membership"),
        CheckConstraint(
            "status IN ('READY','NOT_READY','NEEDS_HARMONIZATION','NEEDS_REVIEW')",
            name="ck_readiness_status",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    candidate_set_id: Mapped[UUID] = mapped_column()
    algorithm_version: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))
    blockers: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    evaluated_by_user_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )


def _reject_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("outcome harmonization scientific history is append-only")


for _immutable in (
    OutcomeDefinitionRecord,
    OutcomeDefinitionVersionRecord,
    TimepointWindowRecord,
    UnitDefinitionRecord,
    MeasurementScaleRecord,
    OutcomeMappingRecord,
    EffectEstimateRecord,
    EffectEstimateSourceRecord,
    SynthesisCandidateSetRecord,
    SynthesisCandidateEstimateRecord,
    AnalysisReadinessSnapshotRecord,
):
    event.listen(_immutable, "before_update", _reject_mutation)
    event.listen(_immutable, "before_delete", _reject_mutation)


def _time(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _number(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


class SqlAlchemyOutcomeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_outcome(self, **values: Any) -> OutcomeDefinition:
        row = OutcomeDefinitionRecord(**values)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._outcome(row)

    async def get_outcome(
        self, organization_id: UUID, review_id: UUID, outcome_id: UUID
    ) -> OutcomeDefinition | None:
        row = await self._session.scalar(
            select(OutcomeDefinitionRecord).where(
                OutcomeDefinitionRecord.organization_id == organization_id,
                OutcomeDefinitionRecord.review_id == review_id,
                OutcomeDefinitionRecord.id == outcome_id,
            )
        )
        return self._outcome(row) if row else None

    async def list_outcomes(
        self, organization_id: UUID, review_id: UUID
    ) -> list[OutcomeDefinition]:
        rows = await self._session.scalars(
            select(OutcomeDefinitionRecord)
            .where(
                OutcomeDefinitionRecord.organization_id == organization_id,
                OutcomeDefinitionRecord.review_id == review_id,
            )
            .order_by(OutcomeDefinitionRecord.key, OutcomeDefinitionRecord.id)
        )
        return [self._outcome(row) for row in rows]

    async def create_outcome_version(self, **values: Any) -> OutcomeDefinitionVersion:
        async def next_version() -> int:
            latest = await self._session.scalar(
                select(func.max(OutcomeDefinitionVersionRecord.version)).where(
                    OutcomeDefinitionVersionRecord.outcome_id == values["outcome_id"]
                )
            )
            return int(latest or 0) + 1

        row = await insert_next_unique_integer(
            self._session,
            next_version,
            lambda version: OutcomeDefinitionVersionRecord(version=version, **values),
        )
        result = await self.get_outcome_version(row.organization_id, row.review_id, row.id)
        assert result is not None
        return result

    async def get_outcome_version(
        self, organization_id: UUID, review_id: UUID, version_id: UUID
    ) -> OutcomeDefinitionVersion | None:
        row = await self._session.scalar(
            select(OutcomeDefinitionVersionRecord).where(
                OutcomeDefinitionVersionRecord.organization_id == organization_id,
                OutcomeDefinitionVersionRecord.review_id == review_id,
                OutcomeDefinitionVersionRecord.id == version_id,
            )
        )
        return self._version(row) if row else None

    async def list_outcome_versions(
        self, organization_id: UUID, review_id: UUID, outcome_id: UUID | None = None
    ) -> list[OutcomeDefinitionVersion]:
        query = select(OutcomeDefinitionVersionRecord).where(
            OutcomeDefinitionVersionRecord.organization_id == organization_id,
            OutcomeDefinitionVersionRecord.review_id == review_id,
        )
        if outcome_id is not None:
            query = query.where(OutcomeDefinitionVersionRecord.outcome_id == outcome_id)
        rows = await self._session.scalars(
            query.order_by(
                OutcomeDefinitionVersionRecord.outcome_id,
                OutcomeDefinitionVersionRecord.version,
                OutcomeDefinitionVersionRecord.id,
            )
        )
        return [self._version(row) for row in rows]

    async def protocol_version_exists(
        self, organization_id: UUID, review_id: UUID, protocol_version_id: UUID
    ) -> bool:
        return (
            await self._session.scalar(
                select(ProtocolVersionRecord.id).where(
                    ProtocolVersionRecord.organization_id == organization_id,
                    ProtocolVersionRecord.review_id == review_id,
                    ProtocolVersionRecord.id == protocol_version_id,
                )
            )
            is not None
        )

    async def create_timepoint_window(self, **values: Any) -> TimepointWindow:
        row = TimepointWindowRecord(**values)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._window(row)

    async def get_timepoint_window(
        self, organization_id: UUID, review_id: UUID, window_id: UUID
    ) -> TimepointWindow | None:
        row = await self._session.scalar(
            select(TimepointWindowRecord).where(
                TimepointWindowRecord.organization_id == organization_id,
                TimepointWindowRecord.review_id == review_id,
                TimepointWindowRecord.id == window_id,
            )
        )
        return self._window(row) if row else None

    async def list_timepoint_windows(
        self, organization_id: UUID, review_id: UUID
    ) -> list[TimepointWindow]:
        rows = await self._session.scalars(
            select(TimepointWindowRecord)
            .where(
                TimepointWindowRecord.organization_id == organization_id,
                TimepointWindowRecord.review_id == review_id,
            )
            .order_by(
                TimepointWindowRecord.key,
                TimepointWindowRecord.rule_version,
                TimepointWindowRecord.id,
            )
        )
        return [self._window(row) for row in rows]

    async def create_unit(self, **values: Any) -> UnitDefinition:
        row = UnitDefinitionRecord(**values)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._unit(row)

    async def get_unit(
        self, organization_id: UUID, review_id: UUID, unit_id: UUID
    ) -> UnitDefinition | None:
        row = await self._session.scalar(
            select(UnitDefinitionRecord).where(
                UnitDefinitionRecord.organization_id == organization_id,
                UnitDefinitionRecord.review_id == review_id,
                UnitDefinitionRecord.id == unit_id,
            )
        )
        return self._unit(row) if row else None

    async def list_units(self, organization_id: UUID, review_id: UUID) -> list[UnitDefinition]:
        rows = await self._session.scalars(
            select(UnitDefinitionRecord)
            .where(
                UnitDefinitionRecord.organization_id == organization_id,
                UnitDefinitionRecord.review_id == review_id,
            )
            .order_by(
                UnitDefinitionRecord.dimension,
                UnitDefinitionRecord.context_key,
                UnitDefinitionRecord.key,
                UnitDefinitionRecord.rule_version,
            )
        )
        return [self._unit(row) for row in rows]

    async def create_scale(self, **values: Any) -> MeasurementScale:
        row = MeasurementScaleRecord(**values)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._scale(row)

    async def get_scale(
        self, organization_id: UUID, review_id: UUID, scale_id: UUID
    ) -> MeasurementScale | None:
        row = await self._session.scalar(
            select(MeasurementScaleRecord).where(
                MeasurementScaleRecord.organization_id == organization_id,
                MeasurementScaleRecord.review_id == review_id,
                MeasurementScaleRecord.id == scale_id,
            )
        )
        return self._scale(row) if row else None

    async def list_scales(self, organization_id: UUID, review_id: UUID) -> list[MeasurementScale]:
        rows = await self._session.scalars(
            select(MeasurementScaleRecord)
            .where(
                MeasurementScaleRecord.organization_id == organization_id,
                MeasurementScaleRecord.review_id == review_id,
            )
            .order_by(MeasurementScaleRecord.key, MeasurementScaleRecord.id)
        )
        return [self._scale(row) for row in rows]

    async def extraction_value_context(
        self, organization_id: UUID, review_id: UUID, extraction_value_id: UUID
    ) -> dict[str, Any] | None:
        value = await self._session.scalar(
            select(ExtractionValueRecord).where(
                ExtractionValueRecord.organization_id == organization_id,
                ExtractionValueRecord.review_id == review_id,
                ExtractionValueRecord.id == extraction_value_id,
            )
        )
        if value is None:
            return None
        run = await self._session.scalar(
            select(ExtractionRunRecord).where(
                ExtractionRunRecord.id == value.run_id,
                ExtractionRunRecord.organization_id == organization_id,
                ExtractionRunRecord.review_id == review_id,
            )
        )
        assert run is not None
        statuses = list(
            await self._session.scalars(
                select(ExtractionVerificationRecord.status).where(
                    ExtractionVerificationRecord.organization_id == organization_id,
                    ExtractionVerificationRecord.review_id == review_id,
                    ExtractionVerificationRecord.field_key == value.field_key,
                    (
                        (ExtractionVerificationRecord.run_a_id == value.run_id)
                        | (ExtractionVerificationRecord.run_b_id == value.run_id)
                    ),
                )
            )
        )
        typed = value.value_decimal if value.value_decimal is not None else value.value_integer
        return {
            "study_id": run.study_id,
            "field_key": value.field_key,
            "reported_value": str(typed) if typed is not None else None,
            "reported_unit": value.unit,
            "evidence_location_id": value.evidence_location_id,
            "verified": any(item in ("MATCHED", "ADJUDICATED") for item in statuses),
        }

    async def create_mapping(self, **values: Any) -> OutcomeMapping:
        row = OutcomeMappingRecord(**values)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._mapping(row)

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

    async def list_mappings(self, organization_id: UUID, review_id: UUID) -> list[OutcomeMapping]:
        rows = await self._session.scalars(
            select(OutcomeMappingRecord)
            .where(
                OutcomeMappingRecord.organization_id == organization_id,
                OutcomeMappingRecord.review_id == review_id,
            )
            .order_by(
                OutcomeMappingRecord.study_id,
                OutcomeMappingRecord.outcome_version_id,
                OutcomeMappingRecord.extraction_value_id,
                OutcomeMappingRecord.created_at,
                OutcomeMappingRecord.id,
            )
        )
        return [self._mapping(row) for row in rows]

    async def create_effect_estimate(self, **values: Any) -> EffectEstimate:
        source_ids = [UUID(value) for value in values["source_mapping_ids"]]
        row = EffectEstimateRecord(**values)
        self._session.add(row)
        await self._session.flush()
        self._session.add_all(
            EffectEstimateSourceRecord(
                effect_estimate_id=row.id,
                mapping_id=mapping_id,
                organization_id=row.organization_id,
                review_id=row.review_id,
                ordinal=ordinal,
            )
            for ordinal, mapping_id in enumerate(source_ids, start=1)
        )
        await self._session.flush()
        await self._session.refresh(row)
        return self._estimate(row)

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

    async def list_effect_estimates(
        self, organization_id: UUID, review_id: UUID
    ) -> list[EffectEstimate]:
        rows = await self._session.scalars(
            select(EffectEstimateRecord)
            .where(
                EffectEstimateRecord.organization_id == organization_id,
                EffectEstimateRecord.review_id == review_id,
            )
            .order_by(
                EffectEstimateRecord.outcome_version_id,
                EffectEstimateRecord.study_id,
                EffectEstimateRecord.timepoint_window_id,
                EffectEstimateRecord.effect_measure,
                EffectEstimateRecord.id,
            )
        )
        return [self._estimate(row) for row in rows]

    async def evidence_article(
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

    async def create_candidate_set(self, **values: Any) -> SynthesisCandidateSet:
        estimate_ids = [UUID(value) for value in values["estimate_ids"]]
        row = SynthesisCandidateSetRecord(**values)
        self._session.add(row)
        await self._session.flush()
        self._session.add_all(
            SynthesisCandidateEstimateRecord(
                candidate_set_id=row.id,
                estimate_id=estimate_id,
                organization_id=row.organization_id,
                review_id=row.review_id,
                ordinal=ordinal,
            )
            for ordinal, estimate_id in enumerate(estimate_ids, start=1)
        )
        await self._session.flush()
        await self._session.refresh(row)
        return self._candidate(row)

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

    async def list_candidate_sets(
        self, organization_id: UUID, review_id: UUID
    ) -> list[SynthesisCandidateSet]:
        rows = await self._session.scalars(
            select(SynthesisCandidateSetRecord)
            .where(
                SynthesisCandidateSetRecord.organization_id == organization_id,
                SynthesisCandidateSetRecord.review_id == review_id,
            )
            .order_by(
                SynthesisCandidateSetRecord.outcome_version_id,
                SynthesisCandidateSetRecord.timepoint_window_id,
                SynthesisCandidateSetRecord.effect_measure,
                SynthesisCandidateSetRecord.id,
            )
        )
        return [self._candidate(row) for row in rows]

    async def create_readiness_snapshot(self, **values: Any) -> AnalysisReadinessSnapshot:
        row = AnalysisReadinessSnapshotRecord(**values)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return self._readiness(row)

    async def list_readiness_snapshots(
        self, organization_id: UUID, review_id: UUID
    ) -> list[AnalysisReadinessSnapshot]:
        rows = await self._session.scalars(
            select(AnalysisReadinessSnapshotRecord)
            .where(
                AnalysisReadinessSnapshotRecord.organization_id == organization_id,
                AnalysisReadinessSnapshotRecord.review_id == review_id,
            )
            .order_by(
                AnalysisReadinessSnapshotRecord.created_at, AnalysisReadinessSnapshotRecord.id
            )
        )
        return [self._readiness(row) for row in rows]

    @staticmethod
    def _outcome(row: OutcomeDefinitionRecord) -> OutcomeDefinition:
        return OutcomeDefinition(
            row.id,
            row.organization_id,
            row.review_id,
            row.key,
            row.created_by_user_id,
            _time(row.created_at),
        )

    @staticmethod
    def _version(row: OutcomeDefinitionVersionRecord) -> OutcomeDefinitionVersion:
        return OutcomeDefinitionVersion(
            row.id,
            row.outcome_id,
            row.organization_id,
            row.review_id,
            row.version,
            row.definition,
            row.content_hash,
            row.protocol_version_id,
            row.created_by_user_id,
            _time(row.created_at),
        )

    @staticmethod
    def _window(row: TimepointWindowRecord) -> TimepointWindow:
        return TimepointWindow(
            row.id,
            row.organization_id,
            row.review_id,
            row.key,
            row.label,
            TimeAnchor(row.anchor),
            _number(row.minimum_days),
            _number(row.maximum_days),
            row.rule_version,
            row.created_by_user_id,
            _time(row.created_at),
        )

    @staticmethod
    def _unit(row: UnitDefinitionRecord) -> UnitDefinition:
        return UnitDefinition(
            row.id,
            row.organization_id,
            row.review_id,
            row.key,
            row.label,
            row.dimension,
            row.context_key,
            row.base_unit_key,
            str(row.multiplier_to_base),
            str(row.offset_to_base),
            row.precision,
            row.rule_version,
            row.created_by_user_id,
            _time(row.created_at),
        )

    @staticmethod
    def _scale(row: MeasurementScaleRecord) -> MeasurementScale:
        return MeasurementScale(
            row.id,
            row.organization_id,
            row.review_id,
            row.key,
            row.name,
            _number(row.minimum),
            _number(row.maximum),
            Directionality(row.directionality),
            row.created_by_user_id,
            _time(row.created_at),
        )

    @staticmethod
    def _mapping(row: OutcomeMappingRecord) -> OutcomeMapping:
        return OutcomeMapping(
            row.id,
            row.organization_id,
            row.review_id,
            row.study_id,
            row.extraction_value_id,
            row.outcome_version_id,
            MappingMethod(row.method),
            row.rationale,
            _number(row.confidence),
            _number(row.reported_value),
            row.reported_unit,
            row.reported_unit_id,
            _number(row.normalized_value),
            row.normalized_unit_id,
            row.conversion_rule_version,
            _number(row.reported_time_value),
            TimeUnit(row.reported_time_unit) if row.reported_time_unit else None,
            TimeAnchor(row.reported_time_anchor) if row.reported_time_anchor else None,
            _number(row.normalized_time_days),
            row.timepoint_window_id,
            row.timepoint_rule_version,
            row.measurement_scale_id,
            DirectionTransformation(row.direction_transformation),
            row.transformation_reason,
            row.extraction_verified,
            row.supersedes_mapping_id,
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
            _number(row.estimate),
            _number(row.standard_error),
            _number(row.variance),
            VarianceScale(row.variance_scale),
            _number(row.ci_lower),
            _number(row.ci_upper),
            _number(row.confidence_level),
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
    def _readiness(row: AnalysisReadinessSnapshotRecord) -> AnalysisReadinessSnapshot:
        return AnalysisReadinessSnapshot(
            row.id,
            row.organization_id,
            row.review_id,
            row.candidate_set_id,
            row.algorithm_version,
            ReadinessStatus(row.status),
            tuple(row.blockers),
            row.evaluated_by_user_id,
            _time(row.created_at),
        )
