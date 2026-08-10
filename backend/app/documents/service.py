from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.app.citations.contracts import CitationRepository
from backend.app.core.config import Settings
from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.documents.contracts import DocumentParser, DocumentRepository
from backend.app.documents.domain import (
    CriterionDecision,
    Document,
    DocumentEvidenceLocation,
    DocumentRetrievalMethod,
    DocumentStatus,
    DocumentWarning,
    DocumentWarningKind,
    FullTextDecision,
    FullTextScreening,
    ProcessingRunStatus,
)
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.protocols.contracts import ProtocolRepository
from backend.app.protocols.domain import ProtocolDecisionKind
from backend.app.provenance.contracts import ProvenanceRepository
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.service import ReviewService
from backend.app.storage.contracts import ObjectStorageProvider


class DocumentService:
    def __init__(
        self,
        repository: DocumentRepository,
        review_repository: ReviewRepository,
        citation_repository: CitationRepository,
        protocol_repository: ProtocolRepository,
        identity_repository: IdentityRepository,
        provenance_repository: ProvenanceRepository,
        storage: ObjectStorageProvider,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._citation_repository = citation_repository
        self._protocol_repository = protocol_repository
        self._review_service = ReviewService(review_repository, identity_repository)
        self._provenance_service = ProvenanceService(
            provenance_repository, review_repository, identity_repository
        )
        self._storage = storage
        self._settings = settings

    async def upload_pdf(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        article_id: UUID,
        filename: str,
        media_type: str,
        content: bytes,
        source_name: str = "user-upload",
    ) -> Document:
        review = await self._review_service.get(actor, review_id)
        AuthorizationService.require(actor, Permission.MANAGE_DOCUMENTS)
        article = await self._citation_repository.get_article(
            actor.organization_id, review.id, article_id
        )
        if article is None:
            raise ResourceNotFoundError("article was not found")
        self._validate_upload(filename, media_type, content)
        checksum = hashlib.sha256(content).hexdigest()
        if (
            await self._repository.get_document_for_article_checksum(
                actor.organization_id, review.id, article.id, checksum
            )
            is not None
        ):
            raise ConflictError("an identical document already exists for this article")

        document_id = uuid4()
        storage_key = f"{actor.organization_id}/{review.id}/{article.id}/{document_id.hex}.pdf"
        await self._storage.put(storage_key, content)
        try:
            document = await self._repository.create_document(
                organization_id=actor.organization_id,
                review_id=review.id,
                article_id=article.id,
                status=DocumentStatus.USER_UPLOADED,
                retrieval_method=DocumentRetrievalMethod.USER_UPLOAD,
                source_name=source_name.strip() or "user-upload",
                source_identifier=None,
                source_url=None,
                license=None,
                access_classification="USER_UPLOADED",
                storage_key=storage_key,
                original_filename=filename,
                media_type="application/pdf",
                file_size=len(content),
                sha256=checksum,
                uploaded_by_user_id=actor.user_id,
            )
        except Exception:
            await self._storage.delete(storage_key)
            raise
        await self._audit(actor, review.id, document, "uploaded", {"sha256": checksum})
        return document

    async def create_retrieval_record(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        article_id: UUID,
        status: DocumentStatus,
        retrieval_method: DocumentRetrievalMethod,
        source_name: str,
        source_identifier: str | None,
        source_url: str | None,
        license: str | None,
        access_classification: str | None,
    ) -> Document:
        review = await self._review_service.get(actor, review_id)
        AuthorizationService.require(actor, Permission.MANAGE_DOCUMENTS)
        if status in {
            DocumentStatus.USER_UPLOADED,
            DocumentStatus.PROCESSING,
            DocumentStatus.PROCESSED,
            DocumentStatus.PROCESSING_FAILED,
            DocumentStatus.INVALID_FILE,
        }:
            raise ConflictError("retrieval records cannot use a file-processing status")
        if status == DocumentStatus.EXTERNAL_LINK_ONLY and not source_url:
            raise ConflictError("external link records require a source URL")
        article = await self._citation_repository.get_article(
            actor.organization_id, review.id, article_id
        )
        if article is None:
            raise ResourceNotFoundError("article was not found")
        document = await self._repository.create_document(
            organization_id=actor.organization_id,
            review_id=review.id,
            article_id=article.id,
            status=status,
            retrieval_method=retrieval_method,
            source_name=source_name.strip(),
            source_identifier=source_identifier.strip() if source_identifier else None,
            source_url=source_url.strip() if source_url else None,
            license=license.strip() if license else None,
            access_classification=access_classification.strip() if access_classification else None,
            storage_key=None,
            original_filename=None,
            media_type=None,
            file_size=None,
            sha256=None,
            uploaded_by_user_id=None,
        )
        await self._audit(
            actor,
            review.id,
            document,
            "retrieval_recorded",
            {"status": status.value, "source_name": document.source_name},
        )
        return document

    async def get(self, actor: ActorContext, document_id: UUID) -> Document:
        document = await self._repository.get_document(actor.organization_id, document_id)
        if document is None:
            raise ResourceNotFoundError("document was not found")
        await self._review_service.get(actor, document.review_id)
        return document

    async def process(
        self, actor: ActorContext, *, document_id: UUID, parser: DocumentParser
    ) -> Document:
        document = await self.get(actor, document_id)
        AuthorizationService.require(actor, Permission.MANAGE_DOCUMENTS)
        if document.storage_key is None:
            raise ConflictError("document has no stored full text")
        if document.status == DocumentStatus.PROCESSING:
            raise ConflictError("document is already being processed")
        storage_key = document.storage_key
        if document.status == DocumentStatus.PROCESSED:
            raise ConflictError("document has already been processed")
        document = await self._repository.update_document_status(
            actor.organization_id, document.id, DocumentStatus.PROCESSING
        )
        run = await self._repository.create_processing_run(
            document=document,
            parser_name=parser.name,
            parser_version=parser.version,
            status=ProcessingRunStatus.RUNNING,
            error_message=None,
            requested_by_user_id=actor.user_id,
            started_at=datetime.now(UTC),
            finished_at=None,
        )
        try:
            content = await self._storage.get(storage_key)
            canonical = parser.parse(content)
            await self._repository.replace_document_blocks(document, canonical)
        except Exception as exc:
            await self._repository.finish_processing_run(
                organization_id=actor.organization_id,
                run_id=run.id,
                status=ProcessingRunStatus.FAILED,
                error_message=str(exc)[:4000],
                finished_at=datetime.now(UTC),
            )
            failed = await self._repository.update_document_status(
                actor.organization_id, document.id, DocumentStatus.PROCESSING_FAILED
            )
            await self._audit(
                actor,
                document.review_id,
                failed,
                "processing_failed",
                {"parser": parser.name, "error": str(exc)[:500]},
            )
            return failed

        await self._repository.finish_processing_run(
            organization_id=actor.organization_id,
            run_id=run.id,
            status=ProcessingRunStatus.SUCCEEDED,
            error_message=None,
            finished_at=datetime.now(UTC),
        )
        processed = await self._repository.update_document_status(
            actor.organization_id, document.id, DocumentStatus.PROCESSED
        )
        await self._provenance_service.record_provenance(
            actor,
            review_id=document.review_id,
            subject_type="document",
            subject_id=document.id,
            source_type="document",
            source_id=document.id,
            source_locator={"storage_key": document.storage_key},
            method_name=parser.name,
            method_version=parser.version,
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=None,
            verification_state=VerificationState.UNVERIFIED,
        )
        await self._audit(
            actor,
            document.review_id,
            processed,
            "processed",
            {"parser": parser.name, "parser_version": parser.version},
        )
        return processed

    async def create_evidence_location(
        self,
        actor: ActorContext,
        *,
        document_id: UUID,
        block_id: UUID | None,
        page_number: int | None,
        section: str | None,
        source_text: str | None,
        table_id: str | None,
        figure_id: str | None,
        coordinates: dict[str, float] | None,
    ) -> DocumentEvidenceLocation:
        document = await self.get(actor, document_id)
        AuthorizationService.require(actor, Permission.SCREEN_ARTICLES)
        location = await self._repository.create_evidence_location(
            document=document,
            block_id=block_id,
            page_number=page_number,
            section=section.strip() if section else None,
            source_text=source_text,
            table_id=table_id,
            figure_id=figure_id,
            coordinates=coordinates,
        )
        await self._audit(
            actor,
            document.review_id,
            document,
            "evidence_location_created",
            {"location_id": str(location.id), "page_number": page_number},
        )
        return location

    async def add_warning(
        self,
        actor: ActorContext,
        *,
        document_id: UUID,
        kind: DocumentWarningKind,
        message: str,
    ) -> DocumentWarning:
        document = await self.get(actor, document_id)
        AuthorizationService.require(actor, Permission.MANAGE_DOCUMENTS)
        warning = await self._repository.create_warning(
            document=document,
            kind=kind,
            message=message.strip(),
            created_by_user_id=actor.user_id,
        )
        if kind == DocumentWarningKind.RETRACTION:
            await self._repository.update_document_status(
                actor.organization_id, document.id, DocumentStatus.RETRACTION_WARNING
            )
        elif kind == DocumentWarningKind.INVALID_FULL_TEXT:
            await self._repository.update_document_status(
                actor.organization_id, document.id, DocumentStatus.INVALID_FILE
            )
        await self._audit(
            actor,
            document.review_id,
            document,
            "warning_added",
            {"warning_kind": kind.value, "message": message.strip()},
        )
        return warning

    async def list_warnings(
        self, actor: ActorContext, *, document_id: UUID
    ) -> list[DocumentWarning]:
        document = await self.get(actor, document_id)
        return await self._repository.list_warnings(actor.organization_id, document.id)

    async def screen_full_text(
        self,
        actor: ActorContext,
        *,
        document_id: UUID,
        protocol_version_id: UUID,
        judgments: list[dict[str, object]],
        primary_reason: str | None,
    ) -> FullTextScreening:
        document = await self.get(actor, document_id)
        AuthorizationService.require(actor, Permission.SCREEN_ARTICLES)
        if document.status != DocumentStatus.PROCESSED:
            raise ConflictError("full-text screening requires a processed document")
        protocol = await self._protocol_repository.get_version(
            actor.organization_id, protocol_version_id
        )
        if protocol is None or protocol.review_id != document.review_id:
            raise ResourceNotFoundError("protocol version was not found")
        decision = await self._protocol_repository.get_decision(actor.organization_id, protocol.id)
        if decision is None or decision.decision != ProtocolDecisionKind.APPROVED:
            raise ConflictError("full-text screening requires an approved protocol version")
        if not judgments:
            raise ConflictError("at least one criterion judgment is required")
        normalized: list[tuple[str, CriterionDecision, str | None, UUID | None, str | None]] = []
        criterion_keys: set[str] = set()
        for item in judgments:
            criterion_key = str(item.get("criterion_key", "")).strip()
            if not criterion_key:
                raise ConflictError("criterion keys are required")
            if criterion_key in criterion_keys:
                raise ConflictError("criterion keys must be unique")
            criterion_keys.add(criterion_key)
            try:
                criterion_decision = CriterionDecision(str(item.get("decision", "")))
            except ValueError as exc:
                raise ConflictError("criterion decision is invalid") from exc
            reason = str(item["reason"]).strip() if item.get("reason") else None
            evidence_location_id = item.get("evidence_location_id")
            if evidence_location_id is not None and not isinstance(evidence_location_id, UUID):
                raise ConflictError("evidence location identifiers must be UUIDs")
            evidence_text = (
                str(item["evidence_text"]).strip() if item.get("evidence_text") else None
            )
            if criterion_decision == CriterionDecision.FAIL and reason is None:
                raise ConflictError("failed criteria require a reason")
            if (
                evidence_location_id is not None
                and await self._repository.get_evidence_location(
                    actor.organization_id, document.id, evidence_location_id
                )
                is None
            ):
                raise ResourceNotFoundError("evidence location was not found")
            normalized.append(
                (criterion_key, criterion_decision, reason, evidence_location_id, evidence_text)
            )
        if any(item[1] == CriterionDecision.FAIL for item in normalized):
            final_decision = FullTextDecision.EXCLUDE
        elif any(item[1] == CriterionDecision.UNCLEAR for item in normalized):
            final_decision = FullTextDecision.MAYBE
        else:
            final_decision = FullTextDecision.INCLUDE
        normalized_reason = primary_reason.strip() if primary_reason else None
        if final_decision == FullTextDecision.EXCLUDE and normalized_reason is None:
            normalized_reason = next(
                item[2] for item in normalized if item[1] == CriterionDecision.FAIL
            )
        screening = await self._repository.create_full_text_screening(
            document=document,
            protocol_version_id=protocol.id,
            final_decision=final_decision.value,
            primary_reason=normalized_reason,
            decided_by_user_id=actor.user_id,
        )
        for criterion_key, item_decision, reason, location_id, evidence_text in normalized:
            judgment = await self._repository.create_criterion_judgment(
                screening=screening,
                criterion_key=criterion_key,
                decision=item_decision,
                reason=reason,
                evidence_location_id=location_id,
                evidence_text=evidence_text,
                decided_by_user_id=actor.user_id,
            )
            await self._provenance_service.record_provenance(
                actor,
                review_id=document.review_id,
                subject_type="full_text_criterion_judgment",
                subject_id=judgment.id,
                source_type="document",
                source_id=document.id,
                source_locator={"evidence_location_id": str(location_id) if location_id else None},
                method_name="manual-full-text-screening",
                method_version="1",
                actor_kind=ProvenanceActorKind.HUMAN,
                ai_run_id=None,
                confidence=None,
                verification_state=VerificationState.HUMAN_VERIFIED,
            )
        await self._audit(
            actor,
            document.review_id,
            document,
            "full_text_screened",
            {"screening_id": str(screening.id), "decision": final_decision.value},
        )
        return screening

    async def _audit(
        self,
        actor: ActorContext,
        review_id: UUID,
        document: Document,
        action: str,
        after_snapshot: dict[str, object],
    ) -> None:
        await self._provenance_service.record_audit_event(
            actor,
            review_id=review_id,
            entity_type="document",
            entity_id=document.id,
            action=action,
            before_snapshot=None,
            after_snapshot=after_snapshot,
            reason=None,
        )

    def _validate_upload(self, filename: str, media_type: str, content: bytes) -> None:
        if not filename or len(filename) > 500 or "/" in filename or "\\" in filename:
            raise ConflictError("filename must be a simple PDF filename")
        if not re.fullmatch(r"[^\x00-\x1f]+\.pdf", filename, flags=re.IGNORECASE):
            raise ConflictError("filename must end with .pdf")
        if media_type.casefold() != "application/pdf":
            raise ConflictError("only application/pdf uploads are accepted")
        if len(content) > self._settings.max_document_file_size_bytes:
            raise ConflictError("document exceeds the configured size limit")
        if not content.startswith(b"%PDF-"):
            raise ConflictError("document does not have a valid PDF signature")
