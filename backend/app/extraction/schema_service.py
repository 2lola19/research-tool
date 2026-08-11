from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.extraction.domain import (
    ExtractionFieldType,
    ExtractionSchema,
    ExtractionSchemaVersion,
)
from backend.app.extraction.schema_contracts import ExtractionSchemaRepository
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.service import ReviewService


class ExtractionSchemaService:
    def __init__(
        self,
        repository: ExtractionSchemaRepository,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
        provenance_repository: SqlAlchemyProvenanceRepository,
    ) -> None:
        self._repository = repository
        self._review_service = ReviewService(review_repository, identity_repository)
        self._provenance = ProvenanceService(
            provenance_repository, review_repository, identity_repository
        )

    async def create_schema(
        self, actor: ActorContext, *, review_id: UUID, name: str, description: str | None
    ) -> ExtractionSchema:
        AuthorizationService.require(actor, Permission.MANAGE_EXTRACTION_SCHEMA)
        review = await self._review_service.get(actor, review_id)
        schema = await self._repository.create_schema(
            organization_id=actor.organization_id,
            review_id=review.id,
            name=name.strip(),
            description=description.strip() if description else None,
            created_by_user_id=actor.user_id,
        )
        await self._provenance.record_audit_event(
            actor,
            review_id=review.id,
            entity_type="extraction_schema",
            entity_id=schema.id,
            action="created",
            before_snapshot=None,
            after_snapshot={"name": schema.name},
            reason=None,
        )
        return schema

    async def create_version(
        self, actor: ActorContext, *, review_id: UUID, schema_id: UUID, fields: list[dict[str, Any]]
    ) -> ExtractionSchemaVersion:
        AuthorizationService.require(actor, Permission.MANAGE_EXTRACTION_SCHEMA)
        schema = await self._repository.get_schema(actor.organization_id, review_id, schema_id)
        if schema is None:
            await self._review_service.get(actor, review_id)
            raise ResourceNotFoundError("extraction schema was not found")
        normalized = self._validate_fields(fields)
        payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        version = await self._repository.create_version(
            schema=schema,
            fields=normalized,
            content_hash=hashlib.sha256(payload.encode()).hexdigest(),
            created_by_user_id=actor.user_id,
        )
        await self._provenance.record_audit_event(
            actor,
            review_id=review_id,
            entity_type="extraction_schema_version",
            entity_id=version.id,
            action="created",
            before_snapshot=None,
            after_snapshot={"schema_id": str(schema.id), "version": version.version},
            reason=None,
        )
        return version

    async def list_versions(
        self, actor: ActorContext, *, review_id: UUID, schema_id: UUID
    ) -> list[ExtractionSchemaVersion]:
        await self._review_service.get(actor, review_id)
        if await self._repository.get_schema(actor.organization_id, review_id, schema_id) is None:
            raise ResourceNotFoundError("extraction schema was not found")
        return await self._repository.list_versions(actor.organization_id, review_id, schema_id)

    async def get_version(
        self, actor: ActorContext, *, review_id: UUID, version_id: UUID
    ) -> ExtractionSchemaVersion:
        await self._review_service.get(actor, review_id)
        version = await self._repository.get_version(actor.organization_id, review_id, version_id)
        if version is None:
            raise ResourceNotFoundError("extraction schema version was not found")
        return version

    @staticmethod
    def _validate_fields(fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not fields:
            raise ConflictError("an extraction schema version requires fields")
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for position, item in enumerate(fields):
            key = str(item.get("key", "")).strip()
            label = str(item.get("label", "")).strip()
            try:
                field_type = ExtractionFieldType(str(item.get("field_type", "")))
            except ValueError as exc:
                raise ConflictError(f"field {key or position + 1} has an invalid type") from exc
            if not key or key in seen or not label:
                raise ConflictError("field keys and labels must be non-empty and keys unique")
            seen.add(key)
            options = item.get("allowed_options", [])
            if field_type in (ExtractionFieldType.CATEGORICAL, ExtractionFieldType.ENUM) and (
                not isinstance(options, list) or not options or len(options) != len(set(options))
            ):
                raise ConflictError(f"field {key} requires unique allowed options")
            normalized.append(
                {
                    "key": key,
                    "label": label,
                    "description": item.get("description"),
                    "section": item.get("section"),
                    "field_type": field_type.value,
                    "required": bool(item.get("required", False)),
                    "allowed_options": options,
                    "unit": item.get("unit"),
                    "instructions": item.get("instructions"),
                    "display_order": position,
                }
            )
        return normalized
