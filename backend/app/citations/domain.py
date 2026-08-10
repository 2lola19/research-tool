from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class CitationFormat(StrEnum):
    RIS = "RIS"
    BIBTEX = "BIBTEX"
    CSV = "CSV"


def citation_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ParsedCitation:
    source_key: str | None
    title: str
    abstract: str | None
    publication_year: int | None
    doi: str | None
    pmid: str | None
    authors: list[str]
    journal: str | None
    raw_metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class CitationImportBatch:
    id: UUID
    organization_id: UUID
    review_id: UUID
    source_format: CitationFormat
    source_name: str
    content_hash: str
    record_count: int
    imported_by_user_id: UUID
    imported_at: datetime


@dataclass(frozen=True, slots=True)
class Article:
    id: UUID
    organization_id: UUID
    review_id: UUID
    title: str
    abstract: str | None
    publication_year: int | None
    doi: str | None
    pmid: str | None
    authors: list[str]
    journal: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class CitationSourceRecord:
    id: UUID
    import_batch_id: UUID
    article_id: UUID
    organization_id: UUID
    review_id: UUID
    ordinal: int
    source_key: str | None
    raw_metadata: dict[str, object]
