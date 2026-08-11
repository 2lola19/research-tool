from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.extraction.domain import (
    ExtractionFieldType,
    ExtractionRun,
    ExtractionRunStatus,
    ExtractionSchemaVersion,
    ExtractionValue,
    MissingnessState,
)
from backend.app.extraction.manual_contracts import ManualExtractionRepository
from backend.app.extraction.schema_contracts import ExtractionSchemaRepository
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.service import ReviewService
from backend.app.studies.contracts import StudyRepository


class ManualExtractionService:
    def __init__(
        self,
        repository: ManualExtractionRepository,
        schema_repository: ExtractionSchemaRepository,
        study_repository: StudyRepository,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
        provenance_repository: SqlAlchemyProvenanceRepository,
    ) -> None:
        self._repository = repository
        self._schemas = schema_repository
        self._studies = study_repository
        self._review_service = ReviewService(review_repository, identity_repository)
        self._provenance = ProvenanceService(
            provenance_repository, review_repository, identity_repository
        )

    async def create_run(
        self, actor: ActorContext, *, review_id: UUID, study_id: UUID, schema_version_id: UUID
    ) -> ExtractionRun:
        AuthorizationService.require(actor, Permission.PERFORM_EXTRACTION)
        review = await self._review_service.get(actor, review_id)
        if await self._studies.get_study(actor.organization_id, review.id, study_id) is None:
            raise ResourceNotFoundError("study was not found")
        if (
            await self._schemas.get_version(actor.organization_id, review.id, schema_version_id)
            is None
        ):
            raise ResourceNotFoundError("extraction schema version was not found")
        run = await self._repository.create_run(
            organization_id=actor.organization_id,
            review_id=review.id,
            study_id=study_id,
            schema_version_id=schema_version_id,
            extractor_user_id=actor.user_id,
        )
        await self._provenance.record_audit_event(
            actor,
            review_id=review.id,
            entity_type="extraction_run",
            entity_id=run.id,
            action="created",
            before_snapshot=None,
            after_snapshot={"study_id": str(study_id), "schema_version_id": str(schema_version_id)},
            reason=None,
        )
        return run

    async def get_run(
        self, actor: ActorContext, *, review_id: UUID, run_id: UUID
    ) -> tuple[ExtractionRun, list[ExtractionValue]]:
        await self._review_service.get(actor, review_id)
        run = await self._repository.get_run(actor.organization_id, review_id, run_id)
        if run is None:
            raise ResourceNotFoundError("extraction run was not found")
        return run, await self._repository.list_values(actor.organization_id, review_id, run.id)

    async def save_values(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        run_id: UUID,
        values: list[dict[str, Any]],
        status: ExtractionRunStatus,
    ) -> tuple[ExtractionRun, list[ExtractionValue]]:
        AuthorizationService.require(actor, Permission.PERFORM_EXTRACTION)
        await self._review_service.get(actor, review_id)
        run = await self._repository.get_run(actor.organization_id, review_id, run_id)
        if run is None:
            raise ResourceNotFoundError("extraction run was not found")
        if run.extractor_user_id != actor.user_id and not actor.has_permission(
            Permission.MANAGE_EXTRACTION_SCHEMA
        ):
            raise ResourceNotFoundError("extraction run was not found")
        schema = await self._schemas.get_version(
            actor.organization_id, review_id, run.schema_version_id
        )
        if schema is None:
            raise ConflictError("the extraction schema version is unavailable")
        normalized = await self._validate_values(
            actor,
            review_id=review_id,
            study_id=run.study_id,
            schema=schema,
            values=values,
        )
        if status == ExtractionRunStatus.COMPLETED:
            field_keys = {item["key"] for item in schema.fields}
            supplied = {item["field_key"] for item in normalized}
            required = {item["key"] for item in schema.fields if item.get("required")}
            if not required <= supplied:
                raise ConflictError("all required fields must be saved before completion")
            if not supplied <= field_keys:
                raise ConflictError("unknown extraction field")
        saved = await self._repository.save_values(run=run, values=normalized, status=status)
        for value in saved:
            source_type = "document" if value.evidence_location_id else "article"
            source_id = value.evidence_location_id or value.source_article_id
            if source_id is None:
                raise ConflictError("each extracted value requires Article or Document evidence")
            await self._provenance.record_provenance(
                actor,
                review_id=review_id,
                subject_type="extraction_value",
                subject_id=value.id,
                source_type=source_type,
                source_id=source_id,
                source_locator={"field_key": value.field_key, "evidence_text": value.evidence_text},
                method_name="manual_extraction",
                method_version="1",
                actor_kind=ProvenanceActorKind.HUMAN,
                ai_run_id=None,
                confidence=None,
                verification_state=VerificationState.UNVERIFIED,
            )
        await self._provenance.record_audit_event(
            actor,
            review_id=review_id,
            entity_type="extraction_run",
            entity_id=run.id,
            action="values_saved",
            before_snapshot={"status": run.status.value},
            after_snapshot={"status": status.value, "value_count": len(saved)},
            reason=None,
        )
        updated = await self._repository.get_run(actor.organization_id, review_id, run.id)
        if updated is None:
            raise ConflictError("extraction run disappeared during save")
        return updated, saved

    async def _validate_values(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        study_id: UUID,
        schema: ExtractionSchemaVersion,
        values: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        fields = {str(item["key"]): item for item in schema.fields}
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in values:
            key = str(item.get("field_key", "")).strip()
            if key in seen or key not in fields:
                raise ConflictError("extraction fields must be known and unique")
            seen.add(key)
            try:
                missingness = MissingnessState(str(item.get("missingness", "")))
            except ValueError as exc:
                raise ConflictError(f"field {key} has invalid missingness") from exc
            field = fields[key]
            typed = self._typed_value(field, item.get("value"), missingness)
            source_article_id = (
                UUID(str(item["source_article_id"])) if item.get("source_article_id") else None
            )
            evidence_id = (
                UUID(str(item["evidence_location_id"]))
                if item.get("evidence_location_id")
                else None
            )
            if evidence_id:
                evidence = await self._repository.get_evidence_source(
                    actor.organization_id, review_id, evidence_id
                )
                if evidence is None:
                    raise ResourceNotFoundError("evidence location was not found")
                if source_article_id is not None and source_article_id != evidence[1]:
                    raise ConflictError("evidence location does not belong to the source Article")
                source_article_id = evidence[1]
            if source_article_id is None:
                raise ConflictError(f"field {key} requires Article or Document evidence")
            if not await self._studies.article_linked(
                actor.organization_id, review_id, study_id, source_article_id
            ):
                raise ConflictError("source Article is not linked to the extraction Study")
            normalized.append(
                {
                    "field_key": key,
                    "missingness": missingness.value,
                    "value_integer": typed.get("value_integer"),
                    "value_decimal": typed.get("value_decimal"),
                    "value_text": typed.get("value_text"),
                    "value_boolean": typed.get("value_boolean"),
                    "value_date": typed.get("value_date"),
                    "value_json": typed.get("value_json"),
                    "unit": item.get("unit"),
                    "source_article_id": source_article_id,
                    "evidence_location_id": evidence_id,
                    "evidence_text": item.get("evidence_text"),
                }
            )
        return normalized

    @staticmethod
    def _typed_value(
        field: dict[str, Any], value: Any, missingness: MissingnessState
    ) -> dict[str, Any]:
        if missingness != MissingnessState.VALUE_REPORTED:
            if value is not None:
                raise ConflictError("scientific missingness states cannot carry a typed value")
            return {
                "value_integer": None,
                "value_decimal": None,
                "value_text": None,
                "value_boolean": None,
                "value_date": None,
                "value_json": None,
            }
        field_type = ExtractionFieldType(str(field["field_type"]))
        if value is None:
            raise ConflictError("VALUE_REPORTED requires a typed value")
        empty: dict[str, Any] = {
            "value_integer": None,
            "value_decimal": None,
            "value_text": None,
            "value_boolean": None,
            "value_date": None,
            "value_json": None,
        }
        try:
            if field_type == ExtractionFieldType.INTEGER:
                if isinstance(value, bool):
                    raise ValueError
                empty["value_integer"] = int(value)
                if (
                    str(empty["value_integer"]) != str(value).strip()
                    if isinstance(value, str)
                    else False
                ):
                    raise ValueError
            elif field_type == ExtractionFieldType.DECIMAL:
                empty["value_decimal"] = Decimal(str(value))
            elif field_type == ExtractionFieldType.BOOLEAN:
                if not isinstance(value, bool):
                    raise ValueError
                empty["value_boolean"] = value
            elif field_type == ExtractionFieldType.DATE:
                empty["value_date"] = date.fromisoformat(str(value))
            elif field_type in (ExtractionFieldType.CATEGORICAL, ExtractionFieldType.ENUM):
                if value not in field.get("allowed_options", []):
                    raise ValueError
                empty["value_text"] = str(value)
            elif (
                field_type == ExtractionFieldType.TEXT or field_type == ExtractionFieldType.CITATION
            ):
                empty["value_text"] = str(value)
            else:
                if not isinstance(value, (dict, list)):
                    raise ValueError
                empty["value_json"] = value
        except (ValueError, InvalidOperation, TypeError) as exc:
            raise ConflictError(f"value does not match field type {field_type.value}") from exc
        return empty
