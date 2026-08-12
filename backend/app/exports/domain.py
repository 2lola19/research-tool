from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class ExportFormat(StrEnum):
    CSV = "CSV"
    XLSX = "XLSX"
    JSON = "JSON"
    RIS = "RIS"


@dataclass(frozen=True, slots=True)
class ExportArticle:
    id: UUID
    title: str
    abstract: str | None
    publication_year: int | None
    doi: str | None
    pmid: str | None
    authors: tuple[str, ...]
    journal: str | None
    source_record_ids: tuple[UUID, ...]
    study_keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExportStudy:
    id: UUID
    study_key: str
    label: str | None
    article_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class ExportSearchExecution:
    id: UUID
    source_name: str
    provider_name: str
    platform_name: str | None
    source_classification: str
    method: str
    executed_at: datetime
    search_strategy_version_id: UUID | None
    search_translation_id: UUID | None
    exact_query: str | None
    filters: tuple[tuple[str, str], ...]
    software_version: str | None
    status: str
    provider_result_count: int | None
    imported_record_count: int
    status_history: tuple[tuple[int, str, datetime, int | None, str | None], ...]


@dataclass(frozen=True, slots=True)
class ExportRiskOfBiasAssessment:
    id: UUID
    study_id: UUID
    instrument_version_id: UUID
    instrument_version: int
    instrument_content_hash: str
    assessor_user_id: UUID
    round_number: int
    revision: int
    supersedes_assessment_id: UUID | None
    status: str
    overall_suggested_judgment: str | None
    overall_final_judgment: str | None
    overall_rationale: str | None
    answers: tuple[tuple[str, str, str | None, UUID | None], ...]
    domain_judgments: tuple[tuple[str, str | None, str, str, str | None, UUID | None], ...]


@dataclass(frozen=True, slots=True)
class ExportRiskOfBiasComparison:
    id: UUID
    study_id: UUID
    instrument_version_id: UUID
    round_number: int
    assessment_a_id: UUID
    assessment_b_id: UUID
    status: str
    differences: tuple[dict[str, Any], ...]
    adjudicated_snapshot: dict[str, Any] | None
    adjudicated_by_user_id: UUID | None
    adjudication_reason: str | None


@dataclass(frozen=True, slots=True)
class ExportDataset:
    organization_id: UUID
    review_id: UUID
    review_title: str
    prisma_snapshot_id: UUID
    prisma_algorithm_version: str
    prisma_counts: dict[str, Any]
    prisma_readiness: dict[str, Any]
    prisma_source_references: dict[str, Any]
    articles: tuple[ExportArticle, ...]
    studies: tuple[ExportStudy, ...]
    search_executions: tuple[ExportSearchExecution, ...]
    risk_of_bias_assessments: tuple[ExportRiskOfBiasAssessment, ...]
    risk_of_bias_comparisons: tuple[ExportRiskOfBiasComparison, ...]
    outcome_versions: tuple[dict[str, Any], ...]
    outcome_mappings: tuple[dict[str, Any], ...]
    effect_estimates: tuple[dict[str, Any], ...]
    synthesis_candidate_sets: tuple[dict[str, Any], ...]
    analysis_readiness: tuple[dict[str, Any], ...]
    analysis_specification_versions: tuple[dict[str, Any], ...]
    analysis_sets: tuple[dict[str, Any], ...]
    meta_analysis_runs: tuple[dict[str, Any], ...]
    analysis_study_weights: tuple[dict[str, Any], ...]
    analysis_sensitivities: tuple[dict[str, Any], ...]
    analysis_artifacts: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class RenderedExport:
    content: bytes
    media_type: str
    filename_extension: str
    row_counts: dict[str, int]


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    id: UUID
    organization_id: UUID
    review_id: UUID
    prisma_snapshot_id: UUID
    created_by_user_id: UUID
    export_format: ExportFormat
    schema_version: str
    filename: str
    media_type: str
    sha256: str
    byte_size: int
    manifest: dict[str, Any]
    created_at: datetime
    content: bytes | None = None
