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
