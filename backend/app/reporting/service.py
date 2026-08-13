from __future__ import annotations

import hashlib
import re
from typing import Any
from uuid import UUID

from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.prisma.service import PrismaService
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.provenance.service import ProvenanceService
from backend.app.reporting.contracts import ReportingRepository
from backend.app.reporting.domain import (
    REPORT_RENDERER_VERSION,
    ReportArtifact,
    ReportCurrency,
    ReportFormat,
    ReportingReadiness,
    ReportSnapshot,
    ReportSpecification,
    ReportStatus,
    ReportType,
    content_hash,
)
from backend.app.reporting.renderers import render_report
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.service import ReviewService

_COMPONENTS = (
    "protocol",
    "search",
    "citations",
    "screening",
    "prisma",
    "studies",
    "extraction",
    "risk_of_bias",
    "outcomes",
    "analysis",
    "certainty",
    "provenance",
)


class ReportingService:
    def __init__(
        self,
        repository: ReportingRepository,
        prisma: PrismaService,
        reviews: ReviewRepository,
        identity: IdentityRepository,
        provenance: SqlAlchemyProvenanceRepository,
    ) -> None:
        self._repository = repository
        self._prisma = prisma
        self._reviews = ReviewService(reviews, identity)
        self._provenance = ProvenanceService(provenance, reviews, identity)

    async def readiness(
        self, actor: ActorContext, *, review_id: UUID, report_type: ReportType
    ) -> ReportingReadiness:
        await self._reviews.get(actor, review_id)
        summary, prisma_readiness, _ = await self._prisma.summary(actor, review_id=review_id)
        blockers: list[dict[str, Any]] = []
        if report_type in {ReportType.STRUCTURED_REVIEW_REPORT, ReportType.SUMMARY_OF_FINDINGS}:
            blockers.extend(item.as_dict() for item in prisma_readiness.blockers)
        preview = {
            "prisma": summary.as_dict(),
            "ready_for_final": prisma_readiness.ready_for_final,
        }
        if report_type == ReportType.SUMMARY_OF_FINDINGS and summary.studies_included_review == 0:
            blockers.append(
                {
                    "code": "CERTAINTY_INCOMPLETE",
                    "message": "No included Study evidence is available.",
                    "count": 0,
                }
            )
        included = (
            _COMPONENTS
            if report_type == ReportType.REPRODUCIBILITY_PACKAGE
            else ("review", "prisma", "studies", "risk_of_bias", "analysis", "certainty")
        )
        return ReportingReadiness(
            report_type,
            not blockers,
            tuple(blockers),
            preview,
            tuple(included),
            ("full_text_binaries", "raw_provider_bytes", "secrets", "environment_files"),
        )

    async def create_specification(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        logical_key: str,
        report_type: ReportType,
        definition: dict[str, Any],
    ) -> ReportSpecification:
        AuthorizationService.require(actor, Permission.GENERATE_REPORT)
        await self._reviews.get(actor, review_id)
        normalized = _normalize_definition(report_type, definition)
        item = await self._repository.create_specification(
            organization_id=actor.organization_id,
            review_id=review_id,
            logical_key=_key(logical_key),
            report_type=report_type,
            definition=normalized,
            content_hash=content_hash(normalized),
            created_by_user_id=actor.user_id,
        )
        await self._audit(
            actor,
            review_id,
            "report_specification",
            item.id,
            "created",
            {
                "version": item.version,
                "report_type": report_type.value,
                "content_hash": item.content_hash,
            },
        )
        return item

    async def generate(
        self, actor: ActorContext, *, review_id: UUID, specification_id: UUID
    ) -> tuple[ReportSnapshot, list[ReportArtifact]]:
        AuthorizationService.require(actor, Permission.GENERATE_REPORT)
        review = await self._reviews.get(actor, review_id)
        specification = await self._repository.get_specification(
            actor.organization_id, review_id, specification_id
        )
        if specification is None:
            raise ResourceNotFoundError("Report specification was not found")
        ready = await self.readiness(
            actor, review_id=review_id, report_type=specification.report_type
        )
        if not ready.ready and not bool(specification.definition.get("allow_draft")):
            raise ConflictError(
                "Report is not ready: " + ", ".join(str(item["code"]) for item in ready.blockers)
            )
        prisma = await self._prisma.create_snapshot(actor, review_id=review_id)
        payload = await self._repository.build_source_payload(
            actor.organization_id, review_id, prisma.id
        )
        payload["report_type"] = specification.report_type.value
        payload["specification"] = {
            "id": str(specification.id),
            "version": specification.version,
            "definition": specification.definition,
        }
        source_hashes = await self._repository.current_source_hashes(
            actor.organization_id, review_id
        )
        scientific_hash = content_hash(payload)
        snapshot = await self._repository.create_snapshot(
            organization_id=actor.organization_id,
            review_id=review_id,
            specification_id=specification.id,
            status=ReportStatus.COMPLETED,
            source_references=payload["source_references"],
            source_hashes=source_hashes,
            structured_content=payload,
            scientific_content_hash=scientific_hash,
            renderer_version=REPORT_RENDERER_VERSION,
            created_by_user_id=actor.user_id,
        )
        artifacts: list[ReportArtifact] = []
        safe_slug = re.sub(r"[^a-z0-9]+", "-", review.project_slug.lower()).strip("-") or "review"
        for report_format in [ReportFormat(value) for value in specification.definition["formats"]]:
            rendered = render_report(report_format, payload)
            artifact = await self._repository.create_artifact(
                organization_id=actor.organization_id,
                review_id=review_id,
                report_snapshot_id=snapshot.id,
                report_format=report_format,
                filename=f"{safe_slug}-{snapshot.id}.{rendered.extension}",
                media_type=rendered.media_type,
                sha256=hashlib.sha256(rendered.content).hexdigest(),
                content=rendered.content,
                manifest={
                    **rendered.manifest,
                    "report_snapshot_id": str(snapshot.id),
                    "scientific_content_hash": scientific_hash,
                },
            )
            artifacts.append(artifact)
        await self._audit(
            actor,
            review_id,
            "report_snapshot",
            snapshot.id,
            "generated",
            {
                "scientific_content_hash": scientific_hash,
                "artifact_ids": [str(item.id) for item in artifacts],
            },
        )
        await self._provenance.record_provenance(
            actor,
            review_id=review_id,
            subject_type="report_snapshot",
            subject_id=snapshot.id,
            source_type="report_specification",
            source_id=specification.id,
            source_locator={
                "source_references": snapshot.source_references,
                "source_hashes": source_hashes,
            },
            method_name="deterministic_structured_reporting",
            method_version=REPORT_RENDERER_VERSION,
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=None,
            verification_state=VerificationState.HUMAN_VERIFIED,
        )
        return snapshot, artifacts

    async def list(self, actor: ActorContext, *, review_id: UUID) -> list[dict[str, Any]]:
        await self._reviews.get(actor, review_id)
        current = await self._repository.current_source_hashes(actor.organization_id, review_id)
        artifacts = await self._repository.list_artifacts(actor.organization_id, review_id)
        by_snapshot: dict[UUID, list[ReportArtifact]] = {}
        for artifact in artifacts:
            by_snapshot.setdefault(artifact.report_snapshot_id, []).append(artifact)
        return [
            {
                "snapshot": item,
                "currency": ReportCurrency.CURRENT
                if item.source_hashes == current
                else ReportCurrency.STALE,
                "stale_reasons": []
                if item.source_hashes == current
                else _stale_reasons(item.source_hashes, current),
                "artifacts": by_snapshot.get(item.id, []),
            }
            for item in await self._repository.list_snapshots(actor.organization_id, review_id)
        ]

    async def artifact(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        artifact_id: UUID,
        include_content: bool = False,
    ) -> ReportArtifact:
        await self._reviews.get(actor, review_id)
        item = await self._repository.get_artifact(
            actor.organization_id, review_id, artifact_id, include_content=include_content
        )
        if item is None:
            raise ResourceNotFoundError("Report artifact was not found")
        if include_content and (
            item.content is None or hashlib.sha256(item.content).hexdigest() != item.sha256
        ):
            raise ConflictError("Report artifact checksum verification failed")
        return item

    async def _audit(
        self,
        actor: ActorContext,
        review_id: UUID,
        entity_type: str,
        entity_id: UUID,
        action: str,
        after: dict[str, Any],
    ) -> None:
        await self._provenance.record_audit_event(
            actor,
            review_id=review_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_snapshot=None,
            after_snapshot=after,
            reason=None,
        )


def _normalize_definition(report_type: ReportType, value: dict[str, Any]) -> dict[str, Any]:
    formats = sorted(set(str(item).upper() for item in value.get("formats", ["JSON"])))
    allowed = {item.value for item in ReportFormat}
    if not formats or any(item not in allowed for item in formats):
        raise ConflictError("Report formats are invalid")
    if report_type == ReportType.REPRODUCIBILITY_PACKAGE and formats != ["ZIP"]:
        raise ConflictError("Reproducibility packages require ZIP as their sole format")
    return {
        "formats": formats,
        "sections": sorted(set(value.get("sections", _COMPONENTS))),
        "allow_draft": bool(value.get("allow_draft", False)),
        "baseline_risks": value.get("baseline_risks", []),
        "include_document_binaries": False,
        "include_raw_provider_bytes": False,
    }


def _key(value: str) -> str:
    key = value.strip().upper()
    if (
        not key
        or len(key) > 120
        or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for char in key)
    ):
        raise ConflictError("Report logical key is invalid")
    return key


def _stale_reasons(old: dict[str, Any], current: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"code": "REPORT_SOURCE_STALE", "source": key}
        for key in sorted(set(old) | set(current))
        if old.get(key) != current.get(key)
    ]
