from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from backend.app.citations.contracts import CitationRepository
from backend.app.core.errors import (
    AuthorizationError,
    ConflictError,
    InvalidStateTransitionError,
    ResourceNotFoundError,
)
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.provenance.contracts import ProvenanceRepository
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.domain import ReviewProject
from backend.app.reviews.service import ReviewService
from backend.app.search.contracts import SearchRepository
from backend.app.search.execution_contracts import SearchExecutionRepository
from backend.app.search.execution_domain import (
    ALLOWED_EXECUTION_TRANSITIONS,
    IdentificationSource,
    IdentificationSourceClassification,
    SearchExecution,
    SearchExecutionArtifact,
    SearchExecutionCitationLink,
    SearchExecutionMethod,
    SearchExecutionStatus,
)
from backend.app.storage.contracts import ObjectStorageProvider

MAX_RAW_ARTIFACT_BYTES = 10_000_000


class SearchExecutionService:
    def __init__(
        self,
        repository: SearchExecutionRepository,
        search_repository: SearchRepository,
        citation_repository: CitationRepository,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
        provenance_repository: ProvenanceRepository,
        storage: ObjectStorageProvider,
    ) -> None:
        self._repository = repository
        self._search_repository = search_repository
        self._citation_repository = citation_repository
        self._review_service = ReviewService(review_repository, identity_repository)
        self._provenance = ProvenanceService(
            provenance_repository, review_repository, identity_repository
        )
        self._storage = storage

    async def create_source(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        source_key: str,
        display_name: str,
        classification: IdentificationSourceClassification,
        provider_name: str,
        platform_name: str | None,
    ) -> IdentificationSource:
        review = await self._review_service.get(actor, review_id)
        self._require_manager(actor, review)
        normalized_key = "-".join(source_key.strip().casefold().replace("_", "-").split())
        if not normalized_key or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in normalized_key
        ):
            raise ConflictError(
                "source key must contain only lowercase letters, digits, and hyphens"
            )
        source = await self._repository.create_source(
            organization_id=actor.organization_id,
            review_id=review.id,
            source_key=normalized_key,
            display_name=self._required_text(display_name, "source display name"),
            classification=classification,
            provider_name=self._required_text(provider_name, "provider name"),
            platform_name=self._optional_text(platform_name),
            created_by_user_id=actor.user_id,
        )
        await self._provenance.record_audit_event(
            actor,
            review_id=review.id,
            entity_type="identification_source",
            entity_id=source.id,
            action="created",
            before_snapshot=None,
            after_snapshot={
                "source_key": source.source_key,
                "classification": source.classification.value,
                "provider_name": source.provider_name,
            },
            reason=None,
        )
        return source

    async def list_sources(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[IdentificationSource]:
        review = await self._review_service.get(actor, review_id)
        return await self._repository.list_sources(actor.organization_id, review.id)

    async def create_execution(
        self,
        actor: ActorContext,
        *,
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
    ) -> SearchExecution:
        review = await self._review_service.get(actor, review_id)
        self._require_manager(actor, review)
        source = await self._repository.get_source(actor.organization_id, review.id, source_id)
        if source is None:
            raise ResourceNotFoundError("identification source was not found")
        strategy = None
        if strategy_version_id is not None:
            strategy = await self._search_repository.get_version(
                actor.organization_id, strategy_version_id
            )
            if strategy is None or strategy.review_id != review.id:
                raise ResourceNotFoundError("search strategy version was not found")
        if translation_id is not None:
            translation = await self._search_repository.get_translation_by_id(
                actor.organization_id, translation_id
            )
            if (
                translation is None
                or strategy is None
                or translation.review_id != review.id
                or translation.search_strategy_version_id != strategy.id
            ):
                raise ResourceNotFoundError("search translation was not found for the strategy")
        if supersedes_execution_id is not None:
            superseded = await self._repository.get_execution(
                actor.organization_id, review.id, supersedes_execution_id
            )
            if superseded is None:
                raise ResourceNotFoundError("superseded search execution was not found")
            if not superseded.current_event.status.terminal:
                raise ConflictError("only a terminal search execution can be superseded")
            correction = await self._repository.get_correction_for(
                actor.organization_id, review.id, superseded.id
            )
            if correction is not None:
                raise ConflictError("the search execution already has a correction")
        if executed_at.tzinfo is None or executed_at.utcoffset() is None:
            raise ConflictError("execution timestamp must include a timezone")
        self._validate_result_count(initial_status, provider_result_count)
        cleaned_filters = {
            self._required_text(key, "filter key"): self._required_text(value, "filter value")
            for key, value in sorted(filters.items())
        }
        execution = await self._repository.create_execution(
            organization_id=actor.organization_id,
            review_id=review.id,
            source_id=source.id,
            strategy_version_id=strategy.id if strategy else None,
            translation_id=translation_id,
            supersedes_execution_id=supersedes_execution_id,
            method=method,
            exact_query=self._optional_text(exact_query),
            filters=cleaned_filters,
            executed_at=executed_at.astimezone(UTC),
            software_version=self._optional_text(software_version),
            initial_status=initial_status,
            provider_result_count=provider_result_count,
            note=self._optional_text(note),
            created_by_user_id=actor.user_id,
        )
        await self._provenance.record_provenance(
            actor,
            review_id=review.id,
            subject_type="search_execution",
            subject_id=execution.id,
            source_type="search_strategy_version" if strategy else None,
            source_id=strategy.id if strategy else None,
            source_locator={
                "identification_source_id": str(source.id),
                "exact_query_sha256": self._query_hash(execution.exact_query),
                "method": method.value,
            },
            method_name="search-execution-recording",
            method_version="1",
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=None,
            verification_state=VerificationState.HUMAN_VERIFIED,
        )
        await self._audit_execution(actor, execution, "created")
        if initial_status is not SearchExecutionStatus.PLANNED:
            await self._audit_execution(actor, execution, initial_status.value.casefold())
        return execution

    async def transition(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        execution_id: UUID,
        status: SearchExecutionStatus,
        provider_result_count: int | None,
        note: str | None,
    ) -> SearchExecution:
        review = await self._review_service.get(actor, review_id)
        self._require_manager(actor, review)
        current = await self._repository.get_execution(
            actor.organization_id, review.id, execution_id
        )
        if current is None:
            raise ResourceNotFoundError("search execution was not found")
        if status not in ALLOWED_EXECUTION_TRANSITIONS[current.current_event.status]:
            raise InvalidStateTransitionError(
                "cannot transition search execution from "
                f"{current.current_event.status} to {status}"
            )
        self._validate_result_count(status, provider_result_count)
        execution = await self._repository.append_event(
            organization_id=actor.organization_id,
            review_id=review.id,
            execution_id=current.id,
            status=status,
            provider_result_count=provider_result_count,
            note=self._optional_text(note),
            recorded_by_user_id=actor.user_id,
        )
        await self._audit_execution(actor, execution, status.value.casefold())
        return execution

    async def get_execution(
        self, actor: ActorContext, *, review_id: UUID, execution_id: UUID
    ) -> SearchExecution:
        review = await self._review_service.get(actor, review_id)
        execution = await self._repository.get_execution(
            actor.organization_id, review.id, execution_id
        )
        if execution is None:
            raise ResourceNotFoundError("search execution was not found")
        return execution

    async def list_executions(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[SearchExecution]:
        review = await self._review_service.get(actor, review_id)
        return await self._repository.list_executions(actor.organization_id, review.id)

    async def link_import(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        execution_id: UUID,
        import_batch_id: UUID,
    ) -> list[SearchExecutionCitationLink]:
        review = await self._review_service.get(actor, review_id)
        self._require_manager(actor, review)
        execution = await self._repository.get_execution(
            actor.organization_id, review.id, execution_id
        )
        if execution is None:
            raise ResourceNotFoundError("search execution was not found")
        batch = await self._citation_repository.get_batch(actor.organization_id, import_batch_id)
        if batch is None or batch.review_id != review.id:
            raise ResourceNotFoundError("citation import batch was not found")
        links = await self._repository.link_import_batch(
            organization_id=actor.organization_id,
            review_id=review.id,
            execution_id=execution.id,
            import_batch_id=batch.id,
            linked_by_user_id=actor.user_id,
        )
        if links:
            await self._provenance.record_provenance(
                actor,
                review_id=review.id,
                subject_type="search_execution",
                subject_id=execution.id,
                source_type="citation_import_batch",
                source_id=batch.id,
                source_locator={
                    "content_hash": batch.content_hash,
                    "linked_record_count": len(links),
                },
                method_name="search-import-linkage",
                method_version="1",
                actor_kind=ProvenanceActorKind.HUMAN,
                ai_run_id=None,
                confidence=None,
                verification_state=VerificationState.HUMAN_VERIFIED,
            )
            await self._provenance.record_audit_event(
                actor,
                review_id=review.id,
                entity_type="search_execution",
                entity_id=execution.id,
                action="import_linked",
                before_snapshot=None,
                after_snapshot={
                    "import_batch_id": str(batch.id),
                    "linked_record_count": len(links),
                },
                reason=None,
            )
        return links

    async def upload_artifact(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        execution_id: UUID,
        filename: str,
        media_type: str,
        content: bytes,
    ) -> SearchExecutionArtifact:
        review = await self._review_service.get(actor, review_id)
        self._require_manager(actor, review)
        execution = await self._repository.get_execution(
            actor.organization_id, review.id, execution_id
        )
        if execution is None:
            raise ResourceNotFoundError("search execution was not found")
        self._validate_artifact(filename, media_type, content)
        checksum = hashlib.sha256(content).hexdigest()
        existing = await self._repository.get_artifact_by_checksum(
            actor.organization_id, review.id, execution.id, checksum
        )
        if existing is not None:
            raise ConflictError("an identical raw search artifact already exists")
        artifact_id = uuid4()
        storage_key = (
            f"{actor.organization_id}/{review.id}/search-executions/"
            f"{execution.id}/{artifact_id.hex}.raw"
        )
        await self._storage.put(storage_key, content)
        try:
            artifact = await self._repository.create_artifact(
                artifact_id=artifact_id,
                organization_id=actor.organization_id,
                review_id=review.id,
                execution_id=execution.id,
                storage_key=storage_key,
                original_filename=filename,
                media_type=media_type,
                byte_size=len(content),
                sha256=checksum,
                created_by_user_id=actor.user_id,
            )
        except Exception:
            await self._storage.delete(storage_key)
            raise
        await self._provenance.record_audit_event(
            actor,
            review_id=review.id,
            entity_type="search_execution_artifact",
            entity_id=artifact.id,
            action="uploaded",
            before_snapshot=None,
            after_snapshot={"search_execution_id": str(execution.id), "sha256": checksum},
            reason=None,
        )
        return artifact

    async def get_artifact_content(
        self, actor: ActorContext, *, review_id: UUID, artifact_id: UUID
    ) -> tuple[SearchExecutionArtifact, bytes]:
        review = await self._review_service.get(actor, review_id)
        found = await self._repository.get_artifact(actor.organization_id, review.id, artifact_id)
        if found is None:
            raise ResourceNotFoundError("search execution artifact was not found")
        artifact, storage_key = found
        try:
            content = await self._storage.get(storage_key)
        except FileNotFoundError as exc:
            raise ResourceNotFoundError("search execution artifact content was not found") from exc
        if (
            len(content) != artifact.byte_size
            or hashlib.sha256(content).hexdigest() != artifact.sha256
        ):
            raise ConflictError("search execution artifact checksum verification failed")
        return artifact, content

    async def list_artifacts(
        self, actor: ActorContext, *, review_id: UUID, execution_id: UUID
    ) -> list[SearchExecutionArtifact]:
        execution = await self.get_execution(actor, review_id=review_id, execution_id=execution_id)
        return await self._repository.list_artifacts(
            actor.organization_id, execution.review_id, execution.id
        )

    async def _audit_execution(
        self, actor: ActorContext, execution: SearchExecution, action: str
    ) -> None:
        await self._provenance.record_audit_event(
            actor,
            review_id=execution.review_id,
            entity_type="search_execution",
            entity_id=execution.id,
            action=action,
            before_snapshot=None,
            after_snapshot={
                "status": execution.current_event.status.value,
                "source_id": str(execution.source.id),
                "provider_result_count": execution.current_event.provider_result_count,
                "imported_record_count": execution.imported_record_count,
            },
            reason=execution.current_event.note,
        )

    @staticmethod
    def _validate_result_count(
        status: SearchExecutionStatus, provider_result_count: int | None
    ) -> None:
        if provider_result_count is not None and provider_result_count < 0:
            raise ConflictError("provider result count cannot be negative")
        if status is SearchExecutionStatus.COMPLETED and provider_result_count is None:
            raise ConflictError("completed search executions require a provider result count")

    @staticmethod
    def _validate_artifact(filename: str, media_type: str, content: bytes) -> None:
        if (
            not filename
            or Path(filename).name != filename
            or "/" in filename
            or "\\" in filename
            or len(filename) > 500
        ):
            raise ConflictError("raw search artifact filename is invalid")
        if (
            not media_type.strip()
            or len(media_type) > 200
            or "\r" in media_type
            or "\n" in media_type
        ):
            raise ConflictError("raw search artifact media type is invalid")
        if not content or len(content) > MAX_RAW_ARTIFACT_BYTES:
            raise ConflictError("raw search artifact size is invalid")

    @staticmethod
    def _required_text(value: str, label: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ConflictError(f"{label} is required")
        return cleaned

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        cleaned = value.strip() if value else ""
        return cleaned or None

    @staticmethod
    def _query_hash(query: str | None) -> str | None:
        return hashlib.sha256(query.encode()).hexdigest() if query is not None else None

    @staticmethod
    def _require_manager(actor: ActorContext, review: ReviewProject) -> None:
        if not actor.has_permission(Permission.MANAGE_SEARCH):
            raise AuthorizationError("the current role cannot manage search executions")
        if (
            not actor.has_permission(Permission.VIEW_ALL_REVIEWS)
            and review.owner_user_id != actor.user_id
        ):
            raise AuthorizationError("only the review owner may manage search executions")
