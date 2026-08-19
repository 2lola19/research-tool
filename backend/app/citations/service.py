from __future__ import annotations

from uuid import UUID

from backend.app.citations.contracts import CitationRepository
from backend.app.citations.domain import (
    Article,
    CitationFormat,
    CitationImportBatch,
    ParsedCitation,
    citation_content_hash,
)
from backend.app.citations.parsers import CitationParseError, parse_citations
from backend.app.core.errors import AuthorizationError, InvalidCitationImportError
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.provenance.contracts import ProvenanceRepository
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.service import ReviewService


class CitationImportService:
    def __init__(
        self,
        repository: CitationRepository,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
        provenance_repository: ProvenanceRepository,
    ) -> None:
        self._repository = repository
        self._review_service = ReviewService(review_repository, identity_repository)
        self._provenance_service = ProvenanceService(
            provenance_repository, review_repository, identity_repository
        )

    async def import_citations(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        source_format: CitationFormat,
        source_name: str,
        content: str,
    ) -> CitationImportBatch:
        review = await self._review_service.get(actor, review_id)
        if not actor.has_permission(Permission.IMPORT_CITATIONS):
            raise AuthorizationError("the current role cannot import citations")
        digest = citation_content_hash(content)
        existing = await self._repository.get_batch_by_hash(
            actor.organization_id, review.id, source_format, digest
        )
        if existing is not None:
            return existing
        try:
            records = parse_citations(source_format, content)
        except CitationParseError as exc:
            raise InvalidCitationImportError(str(exc)) from exc
        return await self.import_records(
            actor,
            review_id=review_id,
            source_format=source_format,
            source_name=source_name,
            source_content=content,
            records=records,
            provenance_method_name=f"{source_format.value.casefold()}-citation-parser",
        )

    async def import_records(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        source_format: CitationFormat,
        source_name: str,
        source_content: str,
        records: list[ParsedCitation],
        provenance_method_name: str,
    ) -> CitationImportBatch:
        review = await self._review_service.get(actor, review_id)
        if not actor.has_permission(Permission.IMPORT_CITATIONS):
            raise AuthorizationError("the current role cannot import citations")
        if not records:
            raise InvalidCitationImportError("citation import contained no records")
        digest = citation_content_hash(source_content)
        existing = await self._repository.get_batch_by_hash(
            actor.organization_id, review.id, source_format, digest
        )
        if existing is not None:
            return existing
        batch, created = await self._repository.create_import(
            organization_id=actor.organization_id,
            review_id=review.id,
            source_format=source_format,
            source_name=source_name.strip(),
            source_content=source_content,
            content_hash=digest,
            records=records,
            imported_by_user_id=actor.user_id,
        )
        for article, source in created:
            await self._provenance_service.record_provenance(
                actor,
                review_id=review.id,
                subject_type="article",
                subject_id=article.id,
                source_type="citation_source_record",
                source_id=source.id,
                source_locator={"batch_id": str(batch.id), "ordinal": source.ordinal},
                method_name=provenance_method_name,
                method_version="1",
                actor_kind=ProvenanceActorKind.HUMAN,
                ai_run_id=None,
                confidence=None,
                verification_state=VerificationState.UNVERIFIED,
            )
        await self._provenance_service.record_audit_event(
            actor,
            review_id=review.id,
            entity_type="citation_import_batch",
            entity_id=batch.id,
            action="imported",
            before_snapshot=None,
            after_snapshot={
                "source_format": batch.source_format.value,
                "content_hash": batch.content_hash,
                "record_count": batch.record_count,
            },
            reason=None,
        )
        return batch

    async def list_articles(self, actor: ActorContext, review_id: UUID) -> list[Article]:
        review = await self._review_service.get(actor, review_id)
        return await self._repository.list_articles(actor.organization_id, review.id)

    async def list_imports(self, actor: ActorContext, review_id: UUID) -> list[CitationImportBatch]:
        review = await self._review_service.get(actor, review_id)
        return await self._repository.list_batches(actor.organization_id, review.id)
