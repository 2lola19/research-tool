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
