from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class ExtractionFieldType(StrEnum):
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"
    CATEGORICAL = "CATEGORICAL"
    DATE = "DATE"
    ENUM = "ENUM"
    EFFECT_ESTIMATE = "EFFECT_ESTIMATE"
    CITATION = "CITATION"
    STRUCTURED = "STRUCTURED"


class MissingnessState(StrEnum):
    VALUE_REPORTED = "VALUE_REPORTED"
    NOT_REPORTED = "NOT_REPORTED"
    UNCLEAR = "UNCLEAR"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ExtractionRunStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    VERIFIED = "VERIFIED"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True)
class ExtractionSchema:
    id: UUID
    organization_id: UUID
    review_id: UUID
    name: str
    description: str | None
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ExtractionSchemaVersion:
    id: UUID
    schema_id: UUID
    organization_id: UUID
    review_id: UUID
    version: int
    content_hash: str
    fields: list[dict[str, Any]]
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ExtractionRun:
    id: UUID
    organization_id: UUID
    review_id: UUID
    study_id: UUID
    schema_version_id: UUID
    extractor_user_id: UUID
    status: ExtractionRunStatus
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ExtractionValue:
    id: UUID
    run_id: UUID
    field_key: str
    missingness: MissingnessState
    value_integer: int | None
    value_decimal: str | None
    value_text: str | None
    value_boolean: bool | None
    value_date: str | None
    value_json: dict[str, Any] | list[Any] | None
    unit: str | None
    source_article_id: UUID | None
    evidence_location_id: UUID | None
    evidence_text: str | None
    updated_at: datetime
