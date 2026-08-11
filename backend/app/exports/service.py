from __future__ import annotations

import hashlib
import re
from uuid import UUID

from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.exports.contracts import ExportRepository
from backend.app.exports.domain import ExportArtifact, ExportFormat
from backend.app.exports.renderers import EXPORT_SCHEMA_VERSION, render_export
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.prisma.service import PrismaService
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.service import ReviewService


class ExportService:
    def __init__(
        self,
        repository: ExportRepository,
        prisma_service: PrismaService,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
        provenance_repository: SqlAlchemyProvenanceRepository,
    ) -> None:
        self._repository = repository
        self._prisma = prisma_service
        self._review_service = ReviewService(review_repository, identity_repository)
        self._provenance = ProvenanceService(
            provenance_repository, review_repository, identity_repository
        )

    async def create(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        export_format: ExportFormat,
    ) -> ExportArtifact:
        AuthorizationService.require(actor, Permission.EXPORT_REVIEW)
        review = await self._review_service.get(actor, review_id)
        snapshot = await self._prisma.create_snapshot(actor, review_id=review.id)
        dataset = await self._repository.build_dataset(snapshot)
        rendered = render_export(export_format, dataset)
        checksum = hashlib.sha256(rendered.content).hexdigest()
        safe_slug = re.sub(r"[^a-z0-9]+", "-", review.project_slug.lower()).strip("-")
        filename = f"{safe_slug or 'review'}-{snapshot.id}.{rendered.filename_extension}"
        manifest = {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "format": export_format.value,
            "media_type": rendered.media_type,
            "prisma_snapshot_id": str(snapshot.id),
            "prisma_algorithm_version": snapshot.algorithm_version,
            "prisma_ready_for_final": bool(snapshot.readiness.get("ready_for_final")),
            "source_references": snapshot.source_references,
            "row_counts": rendered.row_counts,
            "sha256": checksum,
            "byte_size": len(rendered.content),
        }
        artifact = await self._repository.create_artifact(
            organization_id=actor.organization_id,
            review_id=review.id,
            prisma_snapshot_id=snapshot.id,
            created_by_user_id=actor.user_id,
            export_format=export_format,
            schema_version=EXPORT_SCHEMA_VERSION,
            filename=filename,
            media_type=rendered.media_type,
            sha256=checksum,
            content=rendered.content,
            manifest=manifest,
        )
        await self._provenance.record_audit_event(
            actor,
            review_id=review.id,
            entity_type="export_artifact",
            entity_id=artifact.id,
            action="created",
            before_snapshot=None,
            after_snapshot={
                "format": export_format.value,
                "sha256": checksum,
                "byte_size": len(rendered.content),
                "prisma_snapshot_id": str(snapshot.id),
            },
            reason=None,
        )
        await self._provenance.record_provenance(
            actor,
            review_id=review.id,
            subject_type="export_artifact",
            subject_id=artifact.id,
            source_type="prisma_snapshot",
            source_id=snapshot.id,
            source_locator={"manifest": manifest},
            method_name="deterministic_review_export",
            method_version=EXPORT_SCHEMA_VERSION,
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=None,
            verification_state=VerificationState.HUMAN_VERIFIED,
        )
        return artifact

    async def get(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        artifact_id: UUID,
        include_content: bool = False,
    ) -> ExportArtifact:
        await self._review_service.get(actor, review_id)
        artifact = await self._repository.get_artifact(
            actor.organization_id,
            review_id,
            artifact_id,
            include_content=include_content,
        )
        if artifact is None:
            raise ResourceNotFoundError("Export artifact was not found")
        if include_content:
            content = artifact.content
            if content is None or hashlib.sha256(content).hexdigest() != artifact.sha256:
                raise ConflictError("Export artifact checksum verification failed")
        return artifact

    async def list(self, actor: ActorContext, *, review_id: UUID) -> list[ExportArtifact]:
        await self._review_service.get(actor, review_id)
        return await self._repository.list_artifacts(actor.organization_id, review_id)
