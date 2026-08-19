from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from uuid import UUID

from backend.app.citations.contracts import CitationRepository
from backend.app.citations.domain import CitationFormat, CitationImportBatch, ParsedCitation
from backend.app.citations.service import CitationImportService
from backend.app.core.config import Settings
from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext
from backend.app.provenance.contracts import ProvenanceRepository
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.search.execution_contracts import SearchExecutionRepository
from backend.app.search.execution_domain import (
    SearchExecution,
    SearchExecutionArtifact,
    SearchExecutionStatus,
)
from backend.app.search.execution_service import SearchExecutionService
from backend.app.search.provider_adapters import ProviderRuntimeConfig, SearchProviderRegistry
from backend.app.search.provider_contracts import SearchProviderAttemptRepository
from backend.app.search.provider_domain import (
    ProviderAttemptSnapshot,
    ProviderFailureClass,
    SearchProviderAttempt,
    SearchProviderCapability,
    SearchProviderError,
)
from backend.app.storage.contracts import ObjectStorageProvider


@dataclass(frozen=True, slots=True)
class ProviderExecutionOutcome:
    execution: SearchExecution
    provider_key: str
    provider_version: str
    artifact: SearchExecutionArtifact | None
    import_batch: CitationImportBatch | None
    attempts: tuple[SearchProviderAttempt, ...]
    failure_class: ProviderFailureClass | None


class SearchProviderExecutionService:
    def __init__(
        self,
        execution_service: SearchExecutionService,
        execution_repository: SearchExecutionRepository,
        attempt_repository: SearchProviderAttemptRepository,
        citation_repository: CitationRepository,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
        provenance_repository: ProvenanceRepository,
        storage: ObjectStorageProvider,
        settings: Settings,
        registry: SearchProviderRegistry | None = None,
    ) -> None:
        self._execution_service = execution_service
        self._execution_repository = execution_repository
        self._attempt_repository = attempt_repository
        self._citation_import = CitationImportService(
            citation_repository,
            review_repository,
            identity_repository,
            provenance_repository,
        )
        self._provenance = ProvenanceService(
            provenance_repository,
            review_repository,
            identity_repository,
        )
        self._storage = storage
        self._settings = settings
        self._registry = registry or SearchProviderRegistry.default(
            ProviderRuntimeConfig(
                user_agent=settings.search_provider_user_agent,
                contact_email=settings.search_provider_contact_email,
                timeout_seconds=settings.search_provider_timeout_seconds,
                max_response_bytes=settings.search_provider_max_response_bytes,
                max_attempts=settings.search_provider_max_attempts,
                min_interval_seconds=settings.search_provider_rate_limit_seconds,
                pubmed_api_key=(
                    settings.search_pubmed_api_key.get_secret_value()
                    if settings.search_pubmed_api_key is not None
                    else None
                ),
            )
        )

    def capabilities(self) -> list[SearchProviderCapability]:
        return self._registry.capabilities()

    async def execute(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        execution_id: UUID,
        provider_key: str,
        max_pages: int | None = None,
        page_size: int | None = None,
    ) -> ProviderExecutionOutcome:
        execution = await self._execution_service.get_execution(
            actor, review_id=review_id, execution_id=execution_id
        )
        if execution.current_event.status not in {
            SearchExecutionStatus.PLANNED,
            SearchExecutionStatus.RUNNING,
        }:
            raise ConflictError("only planned or running search executions can invoke a provider")
        if not self._settings.search_provider_execution_enabled:
            raise ConflictError(
                "scholarly provider execution is disabled; enable it explicitly in configuration"
            )
        query = execution.exact_query
        if query is None or not query.strip():
            raise ConflictError("provider execution requires an exact query")
        provider = self._registry.get(provider_key)
        if provider is None:
            raise ResourceNotFoundError("scholarly search provider is not configured")
        resolved_max_pages = max_pages or self._settings.search_provider_max_pages
        resolved_page_size = page_size or self._settings.search_provider_page_size
        if resolved_max_pages > self._settings.search_provider_max_pages:
            raise ConflictError("provider max_pages exceeds the configured bound")
        if resolved_page_size > 1000:
            raise ConflictError("provider page_size exceeds the configured bound")

        if execution.current_event.status is SearchExecutionStatus.PLANNED:
            execution = await self._execution_service.transition(
                actor,
                review_id=review_id,
                execution_id=execution.id,
                status=SearchExecutionStatus.RUNNING,
                provider_result_count=None,
                note=f"provider {provider.provider_key} execution started",
            )
        try:
            result = await provider.execute_search(
                query,
                execution.filters,
                max_pages=resolved_max_pages,
                page_size=resolved_page_size,
            )
        except SearchProviderError as exc:
            await self._persist_attempts(actor, execution, exc.attempts)
            execution = await self._execution_service.transition(
                actor,
                review_id=review_id,
                execution_id=execution.id,
                status=SearchExecutionStatus.FAILED,
                provider_result_count=None,
                note=self._safe_failure_note(exc),
            )
            await self._record_provider_provenance(
                actor,
                execution,
                provider_key=provider.provider_key,
                provider_version=provider.version,
                attempt_count=len(exc.attempts),
                failure_class=exc.failure_class,
            )
            attempts = tuple(
                await self._attempt_repository.list_attempts(
                    actor.organization_id, review_id, execution.id
                )
            )
            return ProviderExecutionOutcome(
                execution=execution,
                provider_key=provider.provider_key,
                provider_version=provider.version,
                artifact=None,
                import_batch=None,
                attempts=attempts,
                failure_class=exc.failure_class,
            )

        await self._persist_attempts(actor, execution, result.attempts)
        artifact = None
        if result.raw_content:
            artifact = await self._execution_service.upload_artifact(
                actor,
                review_id=review_id,
                execution_id=execution.id,
                filename=f"{provider.provider_key}-{execution.id.hex}.raw",
                media_type=result.raw_media_type or provider.capability.default_media_type,
                content=result.raw_content,
            )
        import_batch = None
        if result.records:
            content = _serialize_records(result.records)
            import_batch = await self._citation_import.import_records(
                actor,
                review_id=review_id,
                source_format=CitationFormat.CSV,
                source_name=f"{provider.provider_key}-{execution.id.hex}.csv",
                source_content=content,
                records=list(result.records),
                provenance_method_name=(f"{provider.provider_key}-normalizer-{provider.version}"),
            )
            await self._execution_service.link_import(
                actor,
                review_id=review_id,
                execution_id=execution.id,
                import_batch_id=import_batch.id,
            )
        if result.provider_result_count < len(result.records):
            raise ConflictError("provider returned fewer total results than normalized records")
        final_status = (
            SearchExecutionStatus.COMPLETED
            if result.provider_result_count == len(result.records)
            else SearchExecutionStatus.PARTIAL
        )
        execution = await self._execution_service.transition(
            actor,
            review_id=review_id,
            execution_id=execution.id,
            status=final_status,
            provider_result_count=result.provider_result_count,
            note=(
                f"provider {provider.provider_key} returned "
                f"{len(result.records)} normalized records "
                f"from total {result.provider_result_count}"
            ),
        )
        await self._record_provider_provenance(
            actor,
            execution,
            provider_key=provider.provider_key,
            provider_version=provider.version,
            attempt_count=len(result.attempts),
            failure_class=None,
        )
        attempts = tuple(
            await self._attempt_repository.list_attempts(
                actor.organization_id, review_id, execution.id
            )
        )
        return ProviderExecutionOutcome(
            execution=execution,
            provider_key=provider.provider_key,
            provider_version=provider.version,
            artifact=artifact,
            import_batch=import_batch,
            attempts=attempts,
            failure_class=None,
        )

    async def list_attempts(
        self, actor: ActorContext, *, review_id: UUID, execution_id: UUID
    ) -> list[SearchProviderAttempt]:
        await self._execution_service.get_execution(
            actor, review_id=review_id, execution_id=execution_id
        )
        return await self._attempt_repository.list_attempts(
            actor.organization_id, review_id, execution_id
        )

    async def _persist_attempts(
        self,
        actor: ActorContext,
        execution: SearchExecution,
        snapshots: tuple[ProviderAttemptSnapshot, ...],
    ) -> None:
        for snapshot in snapshots:
            await self._attempt_repository.append_attempt(
                organization_id=actor.organization_id,
                review_id=execution.review_id,
                search_execution_id=execution.id,
                snapshot=snapshot,
                created_by_user_id=actor.user_id,
            )

    async def _record_provider_provenance(
        self,
        actor: ActorContext,
        execution: SearchExecution,
        *,
        provider_key: str,
        provider_version: str,
        attempt_count: int,
        failure_class: ProviderFailureClass | None,
    ) -> None:
        await self._provenance.record_provenance(
            actor,
            review_id=execution.review_id,
            subject_type="search_execution",
            subject_id=execution.id,
            source_type=None,
            source_id=None,
            source_locator={
                "provider_key": provider_key,
                "provider_version": provider_version,
                "exact_query": execution.exact_query,
                "attempt_count": attempt_count,
                "failure_class": failure_class.value if failure_class else None,
            },
            method_name="scholarly-provider-execution",
            method_version="1",
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=None,
            verification_state=VerificationState.UNVERIFIED,
        )

    @staticmethod
    def _safe_failure_note(error: SearchProviderError) -> str:
        return f"provider execution failed ({error.failure_class.value})"


def _serialize_records(records: tuple[ParsedCitation, ...]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "title",
            "abstract",
            "year",
            "doi",
            "pmid",
            "authors",
            "journal",
            "raw_metadata",
        ],
        lineterminator="\n",
    )
    writer.writeheader()
    for record in records:
        writer.writerow(
            {
                "id": record.source_key or "",
                "title": record.title,
                "abstract": record.abstract or "",
                "year": record.publication_year or "",
                "doi": record.doi or "",
                "pmid": record.pmid or "",
                "authors": ";".join(record.authors),
                "journal": record.journal or "",
                "raw_metadata": json.dumps(
                    record.raw_metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ),
            }
        )
    return output.getvalue()
