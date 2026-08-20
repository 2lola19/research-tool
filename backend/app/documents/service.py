from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import re
from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import UUID, uuid4

from backend.app.citations.contracts import CitationRepository
from backend.app.core.config import Settings
from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.documents.contracts import DocumentParser, DocumentRepository
from backend.app.documents.domain import (
    CriterionDecision,
    Document,
    DocumentEvidenceLocation,
    DocumentMalwareScanAttempt,
    DocumentProcessingRun,
    DocumentRetrievalMethod,
    DocumentStatus,
    DocumentWarning,
    DocumentWarningKind,
    FullTextDecision,
    FullTextScreening,
    ProcessingFailureClass,
    ProcessingRunStatus,
)
from backend.app.documents.manifests import build_chunk_manifest
from backend.app.documents.parsers import (
    DocumentParseError,
    DocumentParserLimitError,
    DocumentParserLimits,
    DocumentParserProviderError,
    DocumentParserTimeoutError,
    DocumentParserUnavailableError,
    DocumentParserUnsupportedError,
    canonical_document_hash,
    validate_canonical_document,
)
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.malware.contracts import MalwareScanner
from backend.app.malware.domain import (
    MalwareScanErrorClass,
    MalwareScanOutcome,
    MalwareScanResult,
)
from backend.app.protocols.contracts import ProtocolRepository
from backend.app.protocols.domain import ProtocolDecisionKind
from backend.app.provenance.contracts import ProvenanceRepository
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.service import ReviewService
from backend.app.storage.contracts import (
    StorageIntegrityError,
    VerifiedObjectStorageProvider,
)

_RESTRICTED_ACCESS_CLASSIFICATIONS = {
    "RESTRICTED",
    "LICENSE_RESTRICTED",
    "PAYWALLED",
    "USER_UPLOADED",
}
_BLOCKED_SOURCE_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.google.com",
}


class DocumentService:
    def __init__(
        self,
        repository: DocumentRepository,
        review_repository: ReviewRepository,
        citation_repository: CitationRepository,
        protocol_repository: ProtocolRepository,
        identity_repository: IdentityRepository,
        provenance_repository: ProvenanceRepository,
        storage: VerifiedObjectStorageProvider,
        malware_scanner: MalwareScanner,
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
        self._malware_scanner = malware_scanner
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
        normalized_filename, normalized_media_type = self._validate_upload(
            filename, media_type, content
        )
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
        await self._storage.put_verified(
            storage_key,
            content,
            expected_sha256=checksum,
            expected_size=len(content),
            media_type=normalized_media_type,
        )
        try:
            document = await self._repository.create_document(
                id=document_id,
                organization_id=actor.organization_id,
                review_id=review.id,
                article_id=article.id,
                status=DocumentStatus.MALWARE_SCAN_PENDING,
                retrieval_method=DocumentRetrievalMethod.USER_UPLOAD,
                source_name=source_name.strip() or "user-upload",
                source_identifier=None,
                source_url=None,
                license=None,
                access_classification="USER_UPLOADED",
                storage_key=storage_key,
                original_filename=normalized_filename,
                media_type=normalized_media_type,
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
            DocumentStatus.MALWARE_SCAN_PENDING,
            DocumentStatus.MALWARE_CLEAN,
            DocumentStatus.MALWARE_INFECTED,
            DocumentStatus.MALWARE_SCAN_FAILED,
        }:
            raise ConflictError("retrieval records cannot use a file-processing status")
        if status == DocumentStatus.EXTERNAL_LINK_ONLY and not source_url:
            raise ConflictError("external link records require a source URL")
        if source_url:
            self._validate_source_url(source_url)
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
        if document.status == DocumentStatus.MALWARE_INFECTED:
            raise ConflictError("document is blocked by malware scanning")
        if document.sha256 is None or document.file_size is None:
            return await self._record_processing_failure(
                actor,
                document,
                parser,
                StorageIntegrityError("document has incomplete storage metadata"),
            )
        content_sha256 = document.sha256
        content_size = document.file_size
        try:
            content = await self._storage.get_verified(
                storage_key,
                expected_sha256=content_sha256,
                expected_size=content_size,
                max_bytes=self._settings.max_document_file_size_bytes,
            )
        except Exception as exc:
            return await self._record_processing_failure(actor, document, parser, exc)

        clean_scan = await self._repository.latest_clean_malware_scan(
            actor.organization_id,
            document.review_id,
            document.id,
            content_sha256,
            content_size,
        )
        if clean_scan is None:
            scan_attempts = await self._repository.count_malware_scan_attempts(
                actor.organization_id, document.review_id, document.id
            )
            if scan_attempts >= self._settings.max_malware_scan_attempts:
                await self._repository.update_document_status(
                    actor.organization_id, document.id, DocumentStatus.MALWARE_SCAN_FAILED
                )
                raise ConflictError("malware scanner retry limit has been reached")
            scan_started_at = datetime.now(UTC)
            scan_result = await self._run_malware_scan(content)
            scan_finished_at = datetime.now(UTC)
            scan_attempt = await self._repository.create_malware_scan_attempt(
                document=document,
                attempt_number=scan_attempts + 1,
                provider_type=scan_result.provider_type,
                scanner_version=scan_result.scanner_version,
                signature_database_version=scan_result.signature_database_version,
                content_sha256=content_sha256,
                content_size=content_size,
                outcome=scan_result.outcome.value,
                detection_name=scan_result.detection_name,
                error_class=scan_result.error_class.value if scan_result.error_class else None,
                error_message=scan_result.error_message,
                started_at=scan_started_at,
                finished_at=scan_finished_at,
            )
            if scan_result.outcome == MalwareScanOutcome.INFECTED:
                blocked = await self._repository.update_document_status(
                    actor.organization_id, document.id, DocumentStatus.MALWARE_INFECTED
                )
                await self._audit(
                    actor,
                    document.review_id,
                    blocked,
                    "malware_scan_blocked",
                    self._malware_scan_snapshot(scan_attempt),
                )
                return blocked
            if scan_result.outcome != MalwareScanOutcome.CLEAN:
                failed = await self._repository.update_document_status(
                    actor.organization_id, document.id, DocumentStatus.MALWARE_SCAN_FAILED
                )
                await self._audit(
                    actor,
                    document.review_id,
                    failed,
                    "malware_scan_failed",
                    self._malware_scan_snapshot(scan_attempt),
                )
                return failed
            document = await self._repository.update_document_status(
                actor.organization_id, document.id, DocumentStatus.MALWARE_CLEAN
            )
            await self._audit(
                actor,
                document.review_id,
                document,
                "malware_scan_clean",
                self._malware_scan_snapshot(scan_attempt),
            )
        elif document.status != DocumentStatus.MALWARE_CLEAN:
            document = await self._repository.update_document_status(
                actor.organization_id, document.id, DocumentStatus.MALWARE_CLEAN
            )

        attempts = await self._repository.count_processing_runs(
            actor.organization_id, document.review_id, document.id
        )
        if attempts >= self._settings.max_document_processing_attempts:
            raise ConflictError("document processing retry limit has been reached")
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
        manifest: list[dict[str, object]] = []
        manifest_hash = ""
        parsed_content_hash = ""
        text_byte_size = 0
        try:
            canonical = await asyncio.wait_for(
                asyncio.to_thread(parser.parse, content),
                timeout=self._settings.document_parser_timeout_seconds,
            )
            validate_canonical_document(canonical, self._parser_limits())
            parsed_content_hash = canonical_document_hash(canonical)
            manifest, manifest_hash, text_byte_size = build_chunk_manifest(
                canonical, content_sha256=content_sha256
            )
            await self._repository.replace_document_blocks(document, canonical)
        except Exception as exc:
            failure_class = self._processing_failure_class(exc)
            await self._repository.finish_processing_run(
                organization_id=actor.organization_id,
                run_id=run.id,
                status=ProcessingRunStatus.FAILED,
                error_message=self._safe_processing_error(exc),
                failure_class=failure_class.value,
                content_sha256=content_sha256 if content is not None else None,
                content_size=len(content) if content is not None else None,
                parsed_content_hash=None,
                chunk_manifest_hash=None,
                chunk_manifest=None,
                block_count=0,
                text_byte_size=0,
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
                {"parser": parser.name, "failure_class": failure_class.value},
            )
            return failed

        assert content is not None
        await self._repository.finish_processing_run(
            organization_id=actor.organization_id,
            run_id=run.id,
            status=ProcessingRunStatus.SUCCEEDED,
            error_message=None,
            failure_class=None,
            content_sha256=content_sha256,
            content_size=len(content),
            parsed_content_hash=parsed_content_hash,
            chunk_manifest_hash=manifest_hash,
            chunk_manifest=manifest,
            block_count=len(manifest),
            text_byte_size=text_byte_size,
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
            source_locator={
                "storage_key": document.storage_key,
                "document_sha256": content_sha256,
                "processing_run_id": str(run.id),
                "parsed_content_hash": parsed_content_hash,
                "chunk_manifest_hash": manifest_hash,
            },
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
            {
                "parser": parser.name,
                "parser_version": parser.version,
                "processing_run_id": str(run.id),
                "parsed_content_hash": parsed_content_hash,
                "chunk_manifest_hash": manifest_hash,
            },
        )
        return processed

    async def _run_malware_scan(self, content: bytes) -> MalwareScanResult:
        try:
            return await asyncio.wait_for(
                self._malware_scanner.scan(content),
                timeout=self._settings.malware_scanner_timeout_seconds,
            )
        except TimeoutError:
            return MalwareScanResult(
                provider_type=self._malware_scanner.provider_type,
                scanner_version=None,
                signature_database_version=None,
                outcome=MalwareScanOutcome.TIMEOUT,
                error_class=MalwareScanErrorClass.TIMEOUT,
                error_message="malware scanner timed out",
            )
        except (ConnectionError, OSError):
            return MalwareScanResult(
                provider_type=self._malware_scanner.provider_type,
                scanner_version=None,
                signature_database_version=None,
                outcome=MalwareScanOutcome.UNAVAILABLE,
                error_class=MalwareScanErrorClass.UNAVAILABLE,
                error_message="malware scanner endpoint is unavailable",
            )
        except Exception:
            return MalwareScanResult(
                provider_type=self._malware_scanner.provider_type,
                scanner_version=None,
                signature_database_version=None,
                outcome=MalwareScanOutcome.ERROR,
                error_class=MalwareScanErrorClass.SCANNER_ERROR,
                error_message="malware scanner returned an operational error",
            )

    async def _record_processing_failure(
        self,
        actor: ActorContext,
        document: Document,
        parser: DocumentParser,
        exc: Exception,
    ) -> Document:
        failure_class = self._processing_failure_class(exc)
        now = datetime.now(UTC)
        run = await self._repository.create_processing_run(
            document=document,
            parser_name=parser.name,
            parser_version=parser.version,
            status=ProcessingRunStatus.FAILED,
            error_message=self._safe_processing_error(exc),
            requested_by_user_id=actor.user_id,
            started_at=now,
            finished_at=now,
        )
        await self._repository.finish_processing_run(
            organization_id=actor.organization_id,
            run_id=run.id,
            status=ProcessingRunStatus.FAILED,
            error_message=self._safe_processing_error(exc),
            failure_class=failure_class.value,
            content_sha256=None,
            content_size=None,
            parsed_content_hash=None,
            chunk_manifest_hash=None,
            chunk_manifest=None,
            block_count=0,
            text_byte_size=0,
            finished_at=now,
        )
        failed = await self._repository.update_document_status(
            actor.organization_id, document.id, DocumentStatus.PROCESSING_FAILED
        )
        await self._audit(
            actor,
            document.review_id,
            failed,
            "processing_failed",
            {"parser": parser.name, "failure_class": failure_class.value},
        )
        return failed

    @staticmethod
    def _malware_scan_snapshot(scan: DocumentMalwareScanAttempt) -> dict[str, object]:
        return {
            "scan_attempt_id": str(scan.id),
            "attempt_number": scan.attempt_number,
            "provider_type": scan.provider_type,
            "scanner_version": scan.scanner_version,
            "signature_database_version": scan.signature_database_version,
            "content_sha256": scan.content_sha256,
            "content_size": scan.content_size,
            "outcome": scan.outcome.value,
            "detection_name": scan.detection_name,
            "error_class": scan.error_class.value if scan.error_class else None,
            "error_message": scan.error_message,
        }

    async def content(self, actor: ActorContext, document_id: UUID) -> tuple[Document, bytes]:
        document = await self.get(actor, document_id)
        if document.storage_key is None or document.sha256 is None or document.file_size is None:
            raise ResourceNotFoundError("document content was not found")
        if (
            document.access_classification or ""
        ).strip().upper() in _RESTRICTED_ACCESS_CLASSIFICATIONS:
            AuthorizationService.require(actor, Permission.SCREEN_ARTICLES)
        if document.status in {
            DocumentStatus.USER_UPLOADED,
            DocumentStatus.MALWARE_SCAN_PENDING,
            DocumentStatus.MALWARE_SCAN_FAILED,
            DocumentStatus.MALWARE_INFECTED,
        }:
            raise ConflictError("document content is unavailable until malware scanning succeeds")
        try:
            content = await self._storage.get_verified(
                document.storage_key,
                expected_sha256=document.sha256,
                expected_size=document.file_size,
                max_bytes=self._settings.max_document_file_size_bytes,
            )
        except FileNotFoundError as exc:
            raise ResourceNotFoundError("document content was not found") from exc
        except StorageIntegrityError as exc:
            raise ConflictError("document content checksum verification failed") from exc
        return document, content

    async def list_processing_runs(
        self, actor: ActorContext, *, document_id: UUID
    ) -> list[DocumentProcessingRun]:
        document = await self.get(actor, document_id)
        return await self._repository.list_processing_runs(
            actor.organization_id, document.review_id, document.id
        )

    async def list_malware_scan_attempts(
        self, actor: ActorContext, *, document_id: UUID
    ) -> list[DocumentMalwareScanAttempt]:
        document = await self.get(actor, document_id)
        AuthorizationService.require(actor, Permission.MANAGE_DOCUMENTS)
        return await self._repository.list_malware_scan_attempts(
            actor.organization_id, document.review_id, document.id
        )

    async def reconcile_storage(self, actor: ActorContext, *, review_id: UUID) -> dict[str, object]:
        review = await self._review_service.get(actor, review_id)
        AuthorizationService.require(actor, Permission.MANAGE_DOCUMENTS)
        documents = await self._repository.list_documents_for_review(
            actor.organization_id, review.id
        )
        expected_keys = {item.storage_key for item in documents if item.storage_key}
        prefix = f"{actor.organization_id}/{review.id}"
        actual_keys = set(await self._storage.list_keys(prefix))
        missing = sorted(
            str(item.id)
            for item in documents
            if item.storage_key and item.storage_key not in actual_keys
        )
        return {
            "review_id": review.id,
            "document_count": len(documents),
            "expected_object_count": len(expected_keys),
            "actual_object_count": len(actual_keys),
            "missing_document_ids": missing,
            "orphan_object_count": len(actual_keys - expected_keys),
            "status": "RECONCILIATION_ONLY",
        }

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

    def _validate_upload(self, filename: str, media_type: str, content: bytes) -> tuple[str, str]:
        normalized_filename = filename.strip()
        normalized_media_type = media_type.split(";", 1)[0].strip().casefold()
        if (
            not normalized_filename
            or len(normalized_filename) > 500
            or "/" in normalized_filename
            or "\\" in normalized_filename
        ):
            raise ConflictError("filename must be a simple PDF filename")
        if not re.fullmatch(r"[^\x00-\x1f]+\.pdf", normalized_filename, flags=re.IGNORECASE):
            raise ConflictError("filename must end with .pdf")
        if normalized_media_type != "application/pdf":
            raise ConflictError("only application/pdf uploads are accepted")
        if len(content) > self._settings.max_document_file_size_bytes:
            raise ConflictError("document exceeds the configured size limit")
        if not content.startswith(b"%PDF-"):
            raise ConflictError("document does not have a valid PDF signature")
        return normalized_filename, normalized_media_type

    def _parser_limits(self) -> DocumentParserLimits:
        return DocumentParserLimits(
            maximum_blocks=self._settings.max_document_parser_blocks,
            maximum_text_bytes=self._settings.max_document_parser_text_bytes,
            maximum_block_text_bytes=self._settings.max_document_parser_block_text_bytes,
            maximum_section_depth=self._settings.max_document_parser_section_depth,
        )

    @staticmethod
    def _processing_failure_class(exc: Exception) -> ProcessingFailureClass:
        if isinstance(exc, FileNotFoundError):
            return ProcessingFailureClass.STORAGE_MISSING
        if isinstance(exc, StorageIntegrityError):
            return ProcessingFailureClass.STORAGE_INTEGRITY
        if isinstance(exc, asyncio.TimeoutError):
            return ProcessingFailureClass.PARSER_TIMEOUT
        if isinstance(exc, DocumentParserTimeoutError):
            return ProcessingFailureClass.PARSER_TIMEOUT
        if isinstance(exc, DocumentParserLimitError):
            return ProcessingFailureClass.PARSER_LIMIT
        if isinstance(exc, DocumentParserUnavailableError):
            return ProcessingFailureClass.PARSER_UNAVAILABLE
        if isinstance(exc, DocumentParserProviderError):
            return ProcessingFailureClass.PARSER_ERROR
        if isinstance(exc, DocumentParserUnsupportedError):
            return ProcessingFailureClass.PARSER_UNSUPPORTED
        if isinstance(exc, DocumentParseError):
            return ProcessingFailureClass.PARSER_INVALID
        return ProcessingFailureClass.UNEXPECTED

    @staticmethod
    def _safe_processing_error(exc: Exception) -> str:
        if isinstance(exc, FileNotFoundError):
            return "document content is missing from object storage"
        if isinstance(exc, StorageIntegrityError):
            return "document content failed checksum or size verification"
        if isinstance(exc, asyncio.TimeoutError):
            return "document parser exceeded its time limit"
        if isinstance(exc, DocumentParserTimeoutError):
            return str(exc)[:4000]
        if isinstance(exc, DocumentParserLimitError):
            return str(exc)[:4000]
        if isinstance(exc, DocumentParseError):
            return str(exc)[:4000]
        return "document processing failed unexpectedly"

    @staticmethod
    def _validate_source_url(source_url: str) -> None:
        parsed = urlparse(source_url.strip())
        host = (parsed.hostname or "").casefold()
        if parsed.scheme.casefold() != "https" or not host:
            raise ConflictError("document source URLs must use HTTPS")
        try:
            _port = parsed.port
        except ValueError as exc:
            raise ConflictError("document source URL port is invalid") from exc
        if parsed.username or parsed.password or parsed.fragment:
            raise ConflictError("document source URLs cannot contain credentials or fragments")
        if host in _BLOCKED_SOURCE_HOSTS or host.endswith((".local", ".internal")):
            raise ConflictError("document source URL host is not allowed")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise ConflictError("document source URL host is not allowed")
