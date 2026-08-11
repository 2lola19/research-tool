from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class IdentificationSourceClassification(StrEnum):
    BIBLIOGRAPHIC_DATABASE = "BIBLIOGRAPHIC_DATABASE"
    TRIAL_REGISTER = "TRIAL_REGISTER"
    OTHER_REGISTER = "OTHER_REGISTER"
    WEBSITE = "WEBSITE"
    ORGANIZATION = "ORGANIZATION"
    CITATION_SEARCHING = "CITATION_SEARCHING"
    REFERENCE_LIST = "REFERENCE_LIST"
    AUTHOR_CONTACT = "AUTHOR_CONTACT"
    MANUAL_IMPORT = "MANUAL_IMPORT"
    OTHER_SOURCE = "OTHER_SOURCE"

    @property
    def prisma_group(self) -> str:
        if self in {
            self.BIBLIOGRAPHIC_DATABASE,
            self.TRIAL_REGISTER,
            self.OTHER_REGISTER,
        }:
            return "DATABASES_AND_REGISTERS"
        return "OTHER_METHODS"

    @property
    def requires_reproducible_query(self) -> bool:
        return self.prisma_group == "DATABASES_AND_REGISTERS"


class SearchExecutionMethod(StrEnum):
    API = "API"
    FILE_IMPORT = "FILE_IMPORT"
    MANUAL_RECORD = "MANUAL_RECORD"
    FIXTURE = "FIXTURE"
    MOCK = "MOCK"
    CONNECTOR = "CONNECTOR"


class SearchExecutionStatus(StrEnum):
    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def terminal(self) -> bool:
        return self in {self.COMPLETED, self.PARTIAL, self.FAILED, self.CANCELLED}


ALLOWED_EXECUTION_TRANSITIONS: dict[SearchExecutionStatus, frozenset[SearchExecutionStatus]] = {
    SearchExecutionStatus.PLANNED: frozenset(
        {
            SearchExecutionStatus.RUNNING,
            SearchExecutionStatus.COMPLETED,
            SearchExecutionStatus.PARTIAL,
            SearchExecutionStatus.FAILED,
            SearchExecutionStatus.CANCELLED,
        }
    ),
    SearchExecutionStatus.RUNNING: frozenset(
        {
            SearchExecutionStatus.COMPLETED,
            SearchExecutionStatus.PARTIAL,
            SearchExecutionStatus.FAILED,
            SearchExecutionStatus.CANCELLED,
        }
    ),
    SearchExecutionStatus.COMPLETED: frozenset(),
    SearchExecutionStatus.PARTIAL: frozenset(),
    SearchExecutionStatus.FAILED: frozenset(),
    SearchExecutionStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class IdentificationSource:
    id: UUID
    organization_id: UUID
    review_id: UUID
    source_key: str
    display_name: str
    classification: IdentificationSourceClassification
    provider_name: str
    platform_name: str | None
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SearchExecutionEvent:
    id: UUID
    search_execution_id: UUID
    sequence: int
    status: SearchExecutionStatus
    provider_result_count: int | None
    note: str | None
    recorded_by_user_id: UUID
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class SearchExecution:
    id: UUID
    organization_id: UUID
    review_id: UUID
    source: IdentificationSource
    search_strategy_version_id: UUID | None
    search_translation_id: UUID | None
    supersedes_execution_id: UUID | None
    method: SearchExecutionMethod
    exact_query: str | None
    filters: dict[str, str]
    executed_at: datetime
    software_version: str | None
    created_by_user_id: UUID
    created_at: datetime
    events: tuple[SearchExecutionEvent, ...]
    current_event: SearchExecutionEvent
    imported_record_count: int


@dataclass(frozen=True, slots=True)
class SearchExecutionCitationLink:
    id: UUID
    search_execution_id: UUID
    citation_source_record_id: UUID
    linked_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SearchExecutionArtifact:
    id: UUID
    search_execution_id: UUID
    original_filename: str
    media_type: str
    byte_size: int
    sha256: str
    created_by_user_id: UUID
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SearchProviderResult:
    exact_query: str
    filters: dict[str, str]
    provider_result_count: int
    raw_content: bytes | None = None
    raw_media_type: str | None = None


class SearchProvider(Protocol):
    provider_key: str
    version: str

    async def execute_search(self, query: str, filters: dict[str, str]) -> SearchProviderResult: ...


@dataclass(frozen=True, slots=True)
class IdentificationContribution:
    execution_id: UUID
    classification: IdentificationSourceClassification
    citation_source_record_ids: frozenset[UUID]


@dataclass(frozen=True, slots=True)
class IdentificationRecordGroups:
    databases_and_registers: frozenset[UUID]
    other_methods: frozenset[UUID]
    conflicting_records: frozenset[UUID]


def group_identification_records(
    contributions: Iterable[IdentificationContribution],
) -> IdentificationRecordGroups:
    """Group discovery events without deduplicating distinct imported records."""
    database_records: set[UUID] = set()
    other_records: set[UUID] = set()
    for contribution in contributions:
        target = (
            database_records
            if contribution.classification.prisma_group == "DATABASES_AND_REGISTERS"
            else other_records
        )
        target.update(contribution.citation_source_record_ids)
    conflicts = database_records & other_records
    return IdentificationRecordGroups(
        databases_and_registers=frozenset(database_records - conflicts),
        other_methods=frozenset(other_records - conflicts),
        conflicting_records=frozenset(conflicts),
    )
