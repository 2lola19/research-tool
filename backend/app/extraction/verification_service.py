from __future__ import annotations

import re
from decimal import Decimal
from typing import Any
from uuid import UUID

from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.extraction.domain import (
    ConflictResolution,
    ConflictStatus,
    ExtractionConflict,
    ExtractionValue,
    VerificationStatus,
)
from backend.app.extraction.manual_contracts import ManualExtractionRepository
from backend.app.extraction.verification_contracts import ExtractionVerificationRepository
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.service import ReviewService


class ExtractionVerificationService:
    def __init__(
        self,
        repository: ExtractionVerificationRepository,
        manual_repository: ManualExtractionRepository,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
        provenance_repository: SqlAlchemyProvenanceRepository,
    ) -> None:
        self._repository = repository
        self._manual = manual_repository
        self._review_service = ReviewService(review_repository, identity_repository)
        self._provenance = ProvenanceService(
            provenance_repository, review_repository, identity_repository
        )

    async def compare(
        self, actor: ActorContext, *, review_id: UUID, run_a_id: UUID, run_b_id: UUID
    ) -> list[dict[str, Any]]:
        AuthorizationService.require(actor, Permission.PERFORM_EXTRACTION)
        await self._review_service.get(actor, review_id)
        run_a = await self._manual.get_run(actor.organization_id, review_id, run_a_id)
        run_b = await self._manual.get_run(actor.organization_id, review_id, run_b_id)
        if run_a is None or run_b is None:
            raise ResourceNotFoundError("extraction run was not found")
        values_a_list = await self._manual.list_values(actor.organization_id, review_id, run_a_id)
        values_b_list = await self._manual.list_values(actor.organization_id, review_id, run_b_id)
        if run_a.study_id != run_b.study_id or run_a.schema_version_id != run_b.schema_version_id:
            raise ConflictError("extraction runs must use the same Study and schema version")
        values_a = {item.field_key: item for item in values_a_list}
        values_b = {item.field_key: item for item in values_b_list}
        comparisons = [
            self._compare_field(key, values_a.get(key), values_b.get(key))
            for key in sorted(values_a.keys() | values_b.keys())
        ]
        await self._repository.create_comparison(
            organization_id=actor.organization_id,
            review_id=review_id,
            study_id=run_a.study_id,
            schema_version_id=run_a.schema_version_id,
            run_a_id=run_a_id,
            run_b_id=run_b_id,
            comparisons=comparisons,
        )
        return comparisons

    async def resolve(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        conflict_id: UUID,
        resolution: ConflictResolution,
        adjudicated_value: dict[str, Any] | None,
        reason: str,
    ) -> ExtractionConflict:
        AuthorizationService.require(actor, Permission.ADJUDICATE_EXTRACTION)
        await self._review_service.get(actor, review_id)
        conflict = await self._repository.get_conflict(
            actor.organization_id, review_id, conflict_id
        )
        if conflict is None:
            raise ResourceNotFoundError("extraction conflict was not found")
        if conflict.status != ConflictStatus.OPEN:
            raise ConflictError("extraction conflict is already resolved")
        final_value = adjudicated_value
        if resolution == ConflictResolution.ACCEPT_A:
            final_value = conflict.value_a
        elif resolution == ConflictResolution.ACCEPT_B:
            final_value = conflict.value_b
        elif not final_value:
            raise ConflictError("an adjudicated replacement value is required")
        resolved = await self._repository.resolve_conflict(
            conflict=conflict,
            resolution=resolution.value,
            adjudicated_value=final_value,
            adjudicated_by_user_id=actor.user_id,
            reason=reason.strip(),
        )
        await self._provenance.record_provenance(
            actor,
            review_id=review_id,
            subject_type="extraction_conflict",
            subject_id=resolved.id,
            source_type=None,
            source_id=None,
            source_locator={
                "field_key": resolved.field_key,
                "resolution": resolved.resolution.value if resolved.resolution else None,
            },
            method_name="manual_adjudication",
            method_version="1",
            actor_kind=ProvenanceActorKind.HUMAN,
            ai_run_id=None,
            confidence=None,
            verification_state=VerificationState.HUMAN_VERIFIED,
        )
        await self._provenance.record_audit_event(
            actor,
            review_id=review_id,
            entity_type="extraction_conflict",
            entity_id=resolved.id,
            action="resolved",
            before_snapshot={"status": conflict.status.value},
            after_snapshot={
                "status": resolved.status.value,
                "resolution": resolved.resolution.value if resolved.resolution else None,
            },
            reason=reason,
        )
        return resolved

    @staticmethod
    def _compare_field(
        field_key: str, value_a: ExtractionValue | None, value_b: ExtractionValue | None
    ) -> dict[str, Any]:
        snapshot_a = _snapshot(value_a)
        snapshot_b = _snapshot(value_b)
        same_value = (
            snapshot_a is not None
            and snapshot_b is not None
            and snapshot_a["missingness"] == snapshot_b["missingness"]
            and _canonical(snapshot_a.get("value")) == _canonical(snapshot_b.get("value"))
        )
        same_evidence = (
            snapshot_a is not None
            and snapshot_b is not None
            and snapshot_a.get("evidence") == snapshot_b.get("evidence")
        )
        status = (
            VerificationStatus.MATCHED
            if same_value and same_evidence
            else VerificationStatus.NEEDS_ADJUDICATION
        )
        return {
            "field_key": field_key,
            "status": status.value,
            "value_a": snapshot_a,
            "value_b": snapshot_b,
            "evidence_a": snapshot_a.get("evidence") if snapshot_a else None,
            "evidence_b": snapshot_b.get("evidence") if snapshot_b else None,
        }


def _snapshot(value: ExtractionValue | None) -> dict[str, Any] | None:
    if value is None:
        return None
    typed: Any = value.value_integer
    if value.value_decimal is not None:
        typed = value.value_decimal
    elif value.value_text is not None:
        typed = value.value_text
    elif value.value_boolean is not None:
        typed = value.value_boolean
    elif value.value_date is not None:
        typed = value.value_date
    elif value.value_json is not None:
        typed = value.value_json
    return {
        "missingness": value.missingness.value,
        "value": typed,
        "unit": value.unit,
        "evidence": {
            "article_id": str(value.source_article_id) if value.source_article_id else None,
            "location_id": str(value.evidence_location_id) if value.evidence_location_id else None,
            "text": value.evidence_text,
        },
    }


def _canonical(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return Decimal(str(value)).normalize()
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    return value
