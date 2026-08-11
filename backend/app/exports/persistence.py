from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    event,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from backend.app.citations.persistence import ArticleRecord, CitationSourceRecordRow
from backend.app.db.base import Base
from backend.app.exports.domain import (
    ExportArticle,
    ExportArtifact,
    ExportDataset,
    ExportFormat,
    ExportRiskOfBiasAssessment,
    ExportRiskOfBiasComparison,
    ExportSearchExecution,
    ExportStudy,
)
from backend.app.outcomes.persistence import SqlAlchemyOutcomeRepository
from backend.app.prisma.domain import PrismaSnapshot
from backend.app.reviews.persistence import ReviewRecord
from backend.app.risk_of_bias.domain import RiskOfBiasInstrumentVersion
from backend.app.risk_of_bias.persistence import SqlAlchemyRiskOfBiasRepository
from backend.app.search.execution_persistence import SqlAlchemySearchExecutionRepository
from backend.app.studies.persistence import StudyArticleLinkRecord, StudyRecord


class ExportArtifactRecord(Base):
    __tablename__ = "export_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "review_id", name="uq_export_artifacts_id_tenant"
        ),
        CheckConstraint("export_format IN ('CSV','XLSX','JSON','RIS')", name="ck_export_format"),
        CheckConstraint("length(sha256) = 64", name="ck_export_sha256_length"),
        CheckConstraint("byte_size >= 0", name="ck_export_byte_size"),
        ForeignKeyConstraint(
            ["review_id", "organization_id"],
            ["reviews.id", "reviews.organization_id"],
            name="fk_export_artifacts_review_tenant",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["prisma_snapshot_id", "organization_id", "review_id"],
            [
                "prisma_snapshots.id",
                "prisma_snapshots.organization_id",
                "prisma_snapshots.review_id",
            ],
            name="fk_export_artifacts_prisma_snapshot",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_export_artifacts_creator_membership",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column()
    review_id: Mapped[UUID] = mapped_column()
    prisma_snapshot_id: Mapped[UUID] = mapped_column()
    created_by_user_id: Mapped[UUID] = mapped_column()
    export_format: Mapped[str] = mapped_column(String(10))
    schema_version: Mapped[str] = mapped_column(String(80))
    filename: Mapped[str] = mapped_column(String(500))
    media_type: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(Integer)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _reject_artifact_mutation(_: Mapper[Any], __: object, ___: object) -> None:
    raise TypeError("export artifacts are immutable")


event.listen(ExportArtifactRecord, "before_update", _reject_artifact_mutation)
event.listen(ExportArtifactRecord, "before_delete", _reject_artifact_mutation)


def _artifact(row: ExportArtifactRecord, *, include_content: bool = False) -> ExportArtifact:
    return ExportArtifact(
        id=row.id,
        organization_id=row.organization_id,
        review_id=row.review_id,
        prisma_snapshot_id=row.prisma_snapshot_id,
        created_by_user_id=row.created_by_user_id,
        export_format=ExportFormat(row.export_format),
        schema_version=row.schema_version,
        filename=row.filename,
        media_type=row.media_type,
        sha256=row.sha256,
        byte_size=row.byte_size,
        manifest=row.manifest,
        created_at=row.created_at or datetime.now(UTC),
        content=row.content if include_content else None,
    )


class SqlAlchemyExportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def build_dataset(self, snapshot: PrismaSnapshot) -> ExportDataset:
        review = (
            await self._session.execute(
                select(ReviewRecord).where(
                    ReviewRecord.id == snapshot.review_id,
                    ReviewRecord.organization_id == snapshot.organization_id,
                )
            )
        ).scalar_one()
        articles = list(
            await self._session.scalars(
                select(ArticleRecord)
                .where(
                    ArticleRecord.organization_id == snapshot.organization_id,
                    ArticleRecord.review_id == snapshot.review_id,
                )
                .order_by(ArticleRecord.id)
            )
        )
        sources = list(
            await self._session.scalars(
                select(CitationSourceRecordRow)
                .where(
                    CitationSourceRecordRow.organization_id == snapshot.organization_id,
                    CitationSourceRecordRow.review_id == snapshot.review_id,
                )
                .order_by(
                    CitationSourceRecordRow.import_batch_id,
                    CitationSourceRecordRow.ordinal,
                    CitationSourceRecordRow.id,
                )
            )
        )
        studies = list(
            await self._session.scalars(
                select(StudyRecord)
                .where(
                    StudyRecord.organization_id == snapshot.organization_id,
                    StudyRecord.review_id == snapshot.review_id,
                )
                .order_by(StudyRecord.study_key, StudyRecord.id)
            )
        )
        links = list(
            await self._session.scalars(
                select(StudyArticleLinkRecord)
                .where(
                    StudyArticleLinkRecord.organization_id == snapshot.organization_id,
                    StudyArticleLinkRecord.review_id == snapshot.review_id,
                    StudyArticleLinkRecord.unlinked_at.is_(None),
                )
                .order_by(StudyArticleLinkRecord.id)
            )
        )
        executions = await SqlAlchemySearchExecutionRepository(self._session).list_executions(
            snapshot.organization_id, snapshot.review_id
        )
        risk_repository = SqlAlchemyRiskOfBiasRepository(self._session)
        risk_assessments = await risk_repository.list_assessments(
            snapshot.organization_id, snapshot.review_id
        )
        risk_comparisons = await risk_repository.list_comparisons(
            snapshot.organization_id, snapshot.review_id
        )
        outcome_repository = SqlAlchemyOutcomeRepository(self._session)
        outcome_definitions = await outcome_repository.list_outcomes(
            snapshot.organization_id, snapshot.review_id
        )
        outcome_versions = await outcome_repository.list_outcome_versions(
            snapshot.organization_id, snapshot.review_id
        )
        outcome_mappings = await outcome_repository.list_mappings(
            snapshot.organization_id, snapshot.review_id
        )
        effect_estimates = await outcome_repository.list_effect_estimates(
            snapshot.organization_id, snapshot.review_id
        )
        candidate_sets = await outcome_repository.list_candidate_sets(
            snapshot.organization_id, snapshot.review_id
        )
        readiness_snapshots = await outcome_repository.list_readiness_snapshots(
            snapshot.organization_id, snapshot.review_id
        )
        outcome_keys = {item.id: item.key for item in outcome_definitions}
        risk_versions = {
            item.instrument_version_id: cast(
                RiskOfBiasInstrumentVersion,
                await risk_repository.get_version(
                    snapshot.organization_id, snapshot.review_id, item.instrument_version_id
                ),
            )
            for item in risk_assessments
        }
        source_ids: dict[UUID, list[UUID]] = defaultdict(list)
        for source in sources:
            source_ids[source.article_id].append(source.id)
        study_by_id = {study.id: study for study in studies}
        study_keys: dict[UUID, list[str]] = defaultdict(list)
        article_ids: dict[UUID, list[UUID]] = defaultdict(list)
        for link in links:
            study = study_by_id[link.study_id]
            study_keys[link.article_id].append(study.study_key)
            article_ids[link.study_id].append(link.article_id)
        return ExportDataset(
            organization_id=snapshot.organization_id,
            review_id=snapshot.review_id,
            review_title=review.title,
            prisma_snapshot_id=snapshot.id,
            prisma_algorithm_version=snapshot.algorithm_version,
            prisma_counts=snapshot.counts,
            prisma_readiness=snapshot.readiness,
            prisma_source_references=snapshot.source_references,
            articles=tuple(
                ExportArticle(
                    id=article.id,
                    title=article.title,
                    abstract=article.abstract,
                    publication_year=article.publication_year,
                    doi=article.doi,
                    pmid=article.pmid,
                    authors=tuple(article.authors),
                    journal=article.journal,
                    source_record_ids=tuple(sorted(source_ids[article.id], key=str)),
                    study_keys=tuple(sorted(study_keys[article.id])),
                )
                for article in articles
            ),
            studies=tuple(
                ExportStudy(
                    id=study.id,
                    study_key=study.study_key,
                    label=study.label,
                    article_ids=tuple(sorted(article_ids[study.id], key=str)),
                )
                for study in studies
            ),
            search_executions=tuple(
                ExportSearchExecution(
                    id=execution.id,
                    source_name=execution.source.display_name,
                    provider_name=execution.source.provider_name,
                    platform_name=execution.source.platform_name,
                    source_classification=execution.source.classification.value,
                    method=execution.method.value,
                    executed_at=execution.executed_at,
                    search_strategy_version_id=execution.search_strategy_version_id,
                    search_translation_id=execution.search_translation_id,
                    exact_query=execution.exact_query,
                    filters=tuple(sorted(execution.filters.items())),
                    software_version=execution.software_version,
                    status=execution.current_event.status.value,
                    provider_result_count=execution.current_event.provider_result_count,
                    imported_record_count=execution.imported_record_count,
                    status_history=tuple(
                        (
                            event.sequence,
                            event.status.value,
                            event.occurred_at,
                            event.provider_result_count,
                            event.note,
                        )
                        for event in execution.events
                    ),
                )
                for execution in executions
            ),
            risk_of_bias_assessments=tuple(
                ExportRiskOfBiasAssessment(
                    id=assessment.id,
                    study_id=assessment.study_id,
                    instrument_version_id=assessment.instrument_version_id,
                    instrument_version=risk_versions[assessment.instrument_version_id].version,
                    instrument_content_hash=risk_versions[
                        assessment.instrument_version_id
                    ].content_hash,
                    assessor_user_id=assessment.assessor_user_id,
                    round_number=assessment.round_number,
                    revision=assessment.revision,
                    supersedes_assessment_id=assessment.supersedes_assessment_id,
                    status=assessment.status.value,
                    overall_suggested_judgment=assessment.overall_suggested_judgment,
                    overall_final_judgment=assessment.overall_final_judgment,
                    overall_rationale=assessment.overall_rationale,
                    answers=tuple(
                        (
                            answer.question_key,
                            answer.answer,
                            answer.rationale,
                            answer.evidence_location_id,
                        )
                        for answer in assessment.answers
                    ),
                    domain_judgments=tuple(
                        (
                            domain.domain_key,
                            domain.suggested_judgment,
                            domain.final_judgment,
                            domain.rationale,
                            domain.override_reason,
                            domain.evidence_location_id,
                        )
                        for domain in assessment.domain_judgments
                    ),
                )
                for assessment in risk_assessments
            ),
            risk_of_bias_comparisons=tuple(
                ExportRiskOfBiasComparison(
                    id=comparison.id,
                    study_id=comparison.study_id,
                    instrument_version_id=comparison.instrument_version_id,
                    round_number=comparison.round_number,
                    assessment_a_id=comparison.assessment_a_id,
                    assessment_b_id=comparison.assessment_b_id,
                    status=comparison.status.value,
                    differences=comparison.differences,
                    adjudicated_snapshot=comparison.adjudicated_snapshot,
                    adjudicated_by_user_id=comparison.adjudicated_by_user_id,
                    adjudication_reason=comparison.adjudication_reason,
                )
                for comparison in risk_comparisons
            ),
            outcome_versions=tuple(
                {
                    "id": str(item.id),
                    "outcome_id": str(item.outcome_id),
                    "outcome_key": outcome_keys[item.outcome_id],
                    "version": item.version,
                    "definition": item.definition,
                    "content_hash": item.content_hash,
                    "protocol_version_id": (
                        str(item.protocol_version_id) if item.protocol_version_id else None
                    ),
                }
                for item in outcome_versions
            ),
            outcome_mappings=tuple(
                {
                    "id": str(item.id),
                    "study_id": str(item.study_id),
                    "extraction_value_id": str(item.extraction_value_id),
                    "outcome_version_id": str(item.outcome_version_id),
                    "method": item.method.value,
                    "rationale": item.rationale,
                    "confidence": item.confidence,
                    "reported_value": item.reported_value,
                    "reported_unit": item.reported_unit,
                    "reported_unit_id": str(item.reported_unit_id)
                    if item.reported_unit_id
                    else None,
                    "normalized_value": item.normalized_value,
                    "normalized_unit_id": str(item.normalized_unit_id)
                    if item.normalized_unit_id
                    else None,
                    "conversion_rule_version": item.conversion_rule_version,
                    "reported_time_value": item.reported_time_value,
                    "reported_time_unit": item.reported_time_unit.value
                    if item.reported_time_unit
                    else None,
                    "reported_time_anchor": item.reported_time_anchor.value
                    if item.reported_time_anchor
                    else None,
                    "normalized_time_days": item.normalized_time_days,
                    "timepoint_window_id": str(item.timepoint_window_id)
                    if item.timepoint_window_id
                    else None,
                    "timepoint_rule_version": item.timepoint_rule_version,
                    "measurement_scale_id": str(item.measurement_scale_id)
                    if item.measurement_scale_id
                    else None,
                    "direction_transformation": item.direction_transformation.value,
                    "transformation_reason": item.transformation_reason,
                    "extraction_verified": item.extraction_verified,
                    "supersedes_mapping_id": str(item.supersedes_mapping_id)
                    if item.supersedes_mapping_id
                    else None,
                }
                for item in outcome_mappings
            ),
            effect_estimates=tuple(
                {
                    "id": str(item.id),
                    "study_id": str(item.study_id),
                    "outcome_version_id": str(item.outcome_version_id),
                    "effect_measure": item.effect_measure.value,
                    "origin": item.origin.value,
                    "estimate": item.estimate,
                    "standard_error": item.standard_error,
                    "variance": item.variance,
                    "variance_scale": item.variance_scale.value,
                    "ci_lower": item.ci_lower,
                    "ci_upper": item.ci_upper,
                    "confidence_level": item.confidence_level,
                    "adjustment": item.adjustment.value,
                    "analysis_population": item.analysis_population.value,
                    "covariates": item.covariates,
                    "model_description": item.model_description,
                    "timepoint_window_id": str(item.timepoint_window_id)
                    if item.timepoint_window_id
                    else None,
                    "unit_id": str(item.unit_id) if item.unit_id else None,
                    "measurement_scale_id": str(item.measurement_scale_id)
                    if item.measurement_scale_id
                    else None,
                    "components": item.components,
                    "source_mapping_ids": [str(value) for value in item.source_mapping_ids],
                    "source_evidence_location_id": str(item.source_evidence_location_id)
                    if item.source_evidence_location_id
                    else None,
                    "calculation_version": item.calculation_version,
                    "zero_event_pattern": item.zero_event_pattern.value,
                }
                for item in effect_estimates
            ),
            synthesis_candidate_sets=tuple(
                {
                    "id": str(item.id),
                    "outcome_version_id": str(item.outcome_version_id),
                    "effect_measure": item.effect_measure.value,
                    "timepoint_window_id": str(item.timepoint_window_id)
                    if item.timepoint_window_id
                    else None,
                    "population_label": item.population_label,
                    "estimate_ids": [str(value) for value in item.estimate_ids],
                }
                for item in candidate_sets
            ),
            analysis_readiness=tuple(
                {
                    "id": str(item.id),
                    "candidate_set_id": str(item.candidate_set_id),
                    "algorithm_version": item.algorithm_version,
                    "status": item.status.value,
                    "blockers": list(item.blockers),
                }
                for item in readiness_snapshots
            ),
        )

    async def create_artifact(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        prisma_snapshot_id: UUID,
        created_by_user_id: UUID,
        export_format: ExportFormat,
        schema_version: str,
        filename: str,
        media_type: str,
        sha256: str,
        content: bytes,
        manifest: dict[str, Any],
    ) -> ExportArtifact:
        row = ExportArtifactRecord(
            organization_id=organization_id,
            review_id=review_id,
            prisma_snapshot_id=prisma_snapshot_id,
            created_by_user_id=created_by_user_id,
            export_format=export_format.value,
            schema_version=schema_version,
            filename=filename,
            media_type=media_type,
            sha256=sha256,
            byte_size=len(content),
            manifest=manifest,
            content=content,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _artifact(row)

    async def get_artifact(
        self,
        organization_id: UUID,
        review_id: UUID,
        artifact_id: UUID,
        *,
        include_content: bool,
    ) -> ExportArtifact | None:
        row = (
            await self._session.execute(
                select(ExportArtifactRecord).where(
                    ExportArtifactRecord.organization_id == organization_id,
                    ExportArtifactRecord.review_id == review_id,
                    ExportArtifactRecord.id == artifact_id,
                )
            )
        ).scalar_one_or_none()
        return _artifact(row, include_content=include_content) if row else None

    async def list_artifacts(self, organization_id: UUID, review_id: UUID) -> list[ExportArtifact]:
        rows = await self._session.scalars(
            select(ExportArtifactRecord)
            .where(
                ExportArtifactRecord.organization_id == organization_id,
                ExportArtifactRecord.review_id == review_id,
            )
            .order_by(ExportArtifactRecord.created_at, ExportArtifactRecord.id)
        )
        return [_artifact(row) for row in rows]
