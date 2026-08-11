from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from backend.app.search.execution_domain import (
    IdentificationSource,
    IdentificationSourceClassification,
    SearchExecution,
    SearchExecutionArtifact,
    SearchExecutionCitationLink,
    SearchExecutionMethod,
    SearchExecutionStatus,
)


class SearchExecutionRepository(Protocol):
    async def create_source(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        source_key: str,
        display_name: str,
        classification: IdentificationSourceClassification,
        provider_name: str,
        platform_name: str | None,
        created_by_user_id: UUID,
    ) -> IdentificationSource: ...

    async def get_source(
        self, organization_id: UUID, review_id: UUID, source_id: UUID
    ) -> IdentificationSource | None: ...

    async def list_sources(
        self, organization_id: UUID, review_id: UUID
    ) -> list[IdentificationSource]: ...

    async def create_execution(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        source_id: UUID,
        strategy_version_id: UUID | None,
        translation_id: UUID | None,
        supersedes_execution_id: UUID | None,
        method: SearchExecutionMethod,
        exact_query: str | None,
        filters: dict[str, str],
        executed_at: datetime,
        software_version: str | None,
        initial_status: SearchExecutionStatus,
        provider_result_count: int | None,
        note: str | None,
        created_by_user_id: UUID,
    ) -> SearchExecution: ...

    async def get_execution(
        self, organization_id: UUID, review_id: UUID, execution_id: UUID
    ) -> SearchExecution | None: ...

    async def list_executions(
        self, organization_id: UUID, review_id: UUID
    ) -> list[SearchExecution]: ...

    async def get_correction_for(
        self, organization_id: UUID, review_id: UUID, execution_id: UUID
    ) -> SearchExecution | None: ...

    async def append_event(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        execution_id: UUID,
        status: SearchExecutionStatus,
        provider_result_count: int | None,
        note: str | None,
        recorded_by_user_id: UUID,
    ) -> SearchExecution: ...

    async def link_import_batch(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        execution_id: UUID,
        import_batch_id: UUID,
        linked_by_user_id: UUID,
    ) -> list[SearchExecutionCitationLink]: ...

    async def get_artifact_by_checksum(
        self, organization_id: UUID, review_id: UUID, execution_id: UUID, sha256: str
    ) -> SearchExecutionArtifact | None: ...

    async def create_artifact(
        self,
        *,
        artifact_id: UUID,
        organization_id: UUID,
        review_id: UUID,
        execution_id: UUID,
        storage_key: str,
        original_filename: str,
        media_type: str,
        byte_size: int,
        sha256: str,
        created_by_user_id: UUID,
    ) -> SearchExecutionArtifact: ...

    async def get_artifact(
        self, organization_id: UUID, review_id: UUID, artifact_id: UUID
    ) -> tuple[SearchExecutionArtifact, str] | None: ...

    async def list_artifacts(
        self, organization_id: UUID, review_id: UUID, execution_id: UUID
    ) -> list[SearchExecutionArtifact]: ...
