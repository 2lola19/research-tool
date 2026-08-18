from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from backend.app.ai.domain import AIOutputProposal, AITaskType, content_hash
from backend.app.ai.extraction_domain import (
    SAFE_AI_FIELD_TYPES,
    AIExtractionErrorCategory,
    AIExtractionEvaluationDataset,
    AIExtractionFieldReviewAction,
    AIExtractionFieldStatus,
    AIExtractionMatchClass,
    AIExtractionProposalLink,
    AIExtractionReadiness,
    AIExtractionReferenceStandard,
    ExtractionSource,
    field_validation,
    manual_missingness,
    ordered_field_hash,
    prepare_extraction_input,
    validate_extraction_output,
)
from backend.app.ai.extraction_metrics import aggregate_metrics, evaluate_field
from backend.app.ai.extraction_persistence import (
    AIExtractionEvaluationResultRecord,
    SqlAlchemyAIExtractionRepository,
)
from backend.app.ai.full_text_domain import FullTextDocumentRole
from backend.app.ai.persistence import SqlAlchemyAIRepository
from backend.app.ai.screening_domain import AIScreeningMode
from backend.app.ai.service import AIExecutionService
from backend.app.ai.tasks import STRUCTURED_EXTRACTION_TASK
from backend.app.core.errors import AuthorizationError, ConflictError, ResourceNotFoundError
from backend.app.documents.domain import DocumentStatus
from backend.app.documents.persistence import SqlAlchemyDocumentRepository
from backend.app.extraction.domain import (
    ExtractionFieldType,
    ExtractionRun,
    ExtractionRunStatus,
    ExtractionSchemaVersion,
    MissingnessState,
)
from backend.app.extraction.manual_persistence import SqlAlchemyManualExtractionRepository
from backend.app.extraction.manual_service import ManualExtractionService
from backend.app.extraction.schema_persistence import SqlAlchemyExtractionSchemaRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.service import ReviewService
from backend.app.studies.persistence import SqlAlchemyStudyRepository


@dataclass(frozen=True, slots=True)
class AIExtractionReadinessView:
    assignment_id: UUID
    schema_version_id: UUID | None
    state: AIExtractionReadiness
    reason: str | None
    unsupported_field_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AIExtractionProposalView:
    assignment_id: UUID
    study_id: UUID
    schema_version_id: UUID
    proposal_id: UUID | None
    ai_run_id: UUID | None
    mode: AIScreeningMode
    readiness: AIExtractionReadiness
    status: str
    failure_reason: str | None
    is_revealed: bool
    structured_value: dict[str, Any] | None
    validation_results: dict[str, Any] | None
    stale: bool
    stale_reasons: tuple[str, ...]
    source_manifest: tuple[dict[str, Any], ...]
    selected_chunk_ids: tuple[str, ...]
    omitted_chunk_count: int
    selection_method: str


class AIExtractionService:
    """Schema-pinned advisory extraction; canonical values remain human-owned."""

    def __init__(
        self,
        repository: SqlAlchemyAIExtractionRepository,
        ai_repository: SqlAlchemyAIRepository,
        manual_repository: SqlAlchemyManualExtractionRepository,
        schema_repository: SqlAlchemyExtractionSchemaRepository,
        study_repository: SqlAlchemyStudyRepository,
        document_repository: SqlAlchemyDocumentRepository,
        review_service: ReviewService,
        provenance_repository: SqlAlchemyProvenanceRepository,
        execution_service: AIExecutionService,
        manual_service: ManualExtractionService,
    ) -> None:
        self._repository = repository
        self._ai_repository = ai_repository
        self._manual_repository = manual_repository
        self._schemas = schema_repository
        self._studies = study_repository
        self._documents = document_repository
        self._reviews = review_service
        self._provenance = provenance_repository
        self._execution = execution_service
        self._manual = manual_service

    async def create_policy(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        mode: AIScreeningMode,
        maximum_batch_size: int,
    ) -> Any:
        AuthorizationService.require(actor, Permission.MANAGE_AI)
        await self._reviews.get(actor, review_id)
        if not 1 <= maximum_batch_size <= 100:
            raise ValueError("maximum batch size must be from 1 through 100")
        policy = await self._repository.create_policy(
            organization_id=actor.organization_id,
            review_id=review_id,
            mode=mode.value,
            maximum_batch_size=maximum_batch_size,
            created_by_user_id=actor.user_id,
        )
        await self._audit(
            actor,
            review_id,
            policy.id,
            "AI_EXTRACTION_POLICY_CREATED",
            {"mode": mode.value, "maximum_batch_size": maximum_batch_size},
        )
        return policy

    async def readiness(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assignment_id: UUID,
        documents: list[dict[str, Any]],
    ) -> AIExtractionReadinessView:
        await self._reviews.get(actor, review_id)
        run = await self._manual_repository.get_run(actor.organization_id, review_id, assignment_id)
        if run is None or run.extractor_user_id != actor.user_id:
            return AIExtractionReadinessView(
                assignment_id,
                None,
                AIExtractionReadiness.BLOCKED_NO_ASSIGNMENT,
                "the human extraction assignment was not found",
            )
        schema = await self._schemas.get_version(
            actor.organization_id, review_id, run.schema_version_id
        )
        if schema is None:
            return AIExtractionReadinessView(
                assignment_id,
                run.schema_version_id,
                AIExtractionReadiness.BLOCKED_NO_SCHEMA,
                "the pinned extraction schema version was not found",
            )
        unsupported = tuple(
            str(field["key"])
            for field in schema.fields
            if _field_type(field) not in SAFE_AI_FIELD_TYPES
        )
        if unsupported:
            return AIExtractionReadinessView(
                assignment_id,
                schema.id,
                AIExtractionReadiness.BLOCKED_UNSUPPORTED_FIELD_TYPE,
                "one or more schema field types are not safe for AI extraction",
                unsupported,
            )
        if not documents:
            return AIExtractionReadinessView(
                assignment_id,
                schema.id,
                AIExtractionReadiness.BLOCKED_NO_DOCUMENT,
                "at least one explicit source document is required",
            )
        if len(documents) > 8:
            return AIExtractionReadinessView(
                assignment_id,
                schema.id,
                AIExtractionReadiness.BLOCKED_SOURCE_SCOPE,
                "at most eight explicit source documents are allowed",
            )
        seen: set[UUID] = set()
        for requested in documents:
            try:
                document_id = UUID(str(requested.get("document_id")))
                FullTextDocumentRole(
                    str(
                        requested.get("document_role", FullTextDocumentRole.PRIMARY_FULL_TEXT.value)
                    )
                )
            except (ValueError, TypeError):
                return AIExtractionReadinessView(
                    assignment_id,
                    schema.id,
                    AIExtractionReadiness.BLOCKED_SOURCE_SCOPE,
                    "source document identity or role is invalid",
                )
            if document_id in seen:
                return AIExtractionReadinessView(
                    assignment_id,
                    schema.id,
                    AIExtractionReadiness.BLOCKED_SOURCE_SCOPE,
                    "source documents must be unique",
                )
            seen.add(document_id)
            document = await self._documents.get_document(actor.organization_id, document_id)
            if document is None or document.review_id != review_id:
                return AIExtractionReadinessView(
                    assignment_id,
                    schema.id,
                    AIExtractionReadiness.BLOCKED_SOURCE_SCOPE,
                    "a source document was not found in this review",
                )
            if not await self._studies.article_linked(
                actor.organization_id, review_id, run.study_id, document.article_id
            ):
                return AIExtractionReadinessView(
                    assignment_id,
                    schema.id,
                    AIExtractionReadiness.BLOCKED_SOURCE_SCOPE,
                    "every source report must be canonically linked to the extraction Study",
                )
            if document.status is not DocumentStatus.PROCESSED:
                return AIExtractionReadinessView(
                    assignment_id,
                    schema.id,
                    AIExtractionReadiness.BLOCKED_DOCUMENT_PROCESSING,
                    f"document {document.id} is not processed",
                )
            processing = await self._documents.latest_successful_processing_run(
                actor.organization_id, review_id, document.id
            )
            if processing is None:
                return AIExtractionReadinessView(
                    assignment_id,
                    schema.id,
                    AIExtractionReadiness.BLOCKED_DOCUMENT_PROCESSING,
                    f"document {document.id} has no successful parser run",
                )
            blocks = await self._documents.list_blocks(
                actor.organization_id, review_id, document.id
            )
            if not any(block.text.strip() for block in blocks):
                return AIExtractionReadinessView(
                    assignment_id,
                    schema.id,
                    AIExtractionReadiness.BLOCKED_NO_PARSED_TEXT,
                    f"document {document.id} has no parsed scientific text",
                )
        return AIExtractionReadinessView(
            assignment_id, schema.id, AIExtractionReadiness.READY, None
        )

    async def create_suggestions(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        requests: list[dict[str, Any]],
        model_version_id: UUID | None = None,
        prompt_version_id: UUID | None = None,
        maximum_attempts: int = 3,
        timeout_seconds: int = 30,
        per_run_token_ceiling: int | None = 16_384,
    ) -> list[AIExtractionProposalView]:
        if not actor.has_permission(Permission.PERFORM_EXTRACTION):
            raise AuthorizationError("the current role cannot request extraction assistance")
        await self._reviews.get(actor, review_id)
        policy = await self._repository.current_policy(actor.organization_id, review_id)
        if policy is None or policy.mode is AIScreeningMode.OFF:
            raise ConflictError("AI extraction assistance is disabled for this review")
        if not requests or len(requests) > policy.maximum_batch_size:
            raise ConflictError("the extraction batch is empty or exceeds the active policy")
        ids = [str(item.get("assignment_id")) for item in requests]
        if len(ids) != len(set(ids)):
            raise ConflictError("batch extraction assignments must be unique")
        results: list[AIExtractionProposalView] = []
        for request in requests:
            assignment_id = _optional_uuid(request.get("assignment_id"))
            try:
                if assignment_id is None:
                    raise ValueError("assignment_id is required")
                results.append(
                    await self._create_one(
                        actor,
                        review_id=review_id,
                        assignment_id=assignment_id,
                        documents=list(request.get("documents") or []),
                        mode=policy.mode,
                        model_version_id=model_version_id,
                        prompt_version_id=prompt_version_id,
                        maximum_attempts=maximum_attempts,
                        timeout_seconds=timeout_seconds,
                        per_run_token_ceiling=per_run_token_ceiling,
                    )
                )
            except (ValueError, ConflictError, ResourceNotFoundError, AuthorizationError) as exc:
                results.append(
                    AIExtractionProposalView(
                        assignment_id or UUID(int=0),
                        UUID(int=0),
                        UUID(int=0),
                        None,
                        None,
                        policy.mode,
                        AIExtractionReadiness.BLOCKED_OTHER,
                        "FAILED",
                        str(exc),
                        False,
                        None,
                        None,
                        False,
                        (),
                        (),
                        (),
                        0,
                        "field-aware-structured-bounded-v1",
                    )
                )
        return results

    async def _create_one(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assignment_id: UUID,
        documents: list[dict[str, Any]],
        mode: AIScreeningMode,
        model_version_id: UUID | None,
        prompt_version_id: UUID | None,
        maximum_attempts: int,
        timeout_seconds: int,
        per_run_token_ceiling: int | None,
    ) -> AIExtractionProposalView:
        ready = await self.readiness(
            actor, review_id=review_id, assignment_id=assignment_id, documents=documents
        )
        if ready.state is not AIExtractionReadiness.READY:
            candidate_run = await self._manual_repository.get_run(
                actor.organization_id, review_id, assignment_id
            )
            return AIExtractionProposalView(
                assignment_id,
                candidate_run.study_id if candidate_run else UUID(int=0),
                ready.schema_version_id or UUID(int=0),
                None,
                None,
                mode,
                ready.state,
                "BLOCKED",
                ready.reason,
                False,
                None,
                None,
                False,
                (),
                (),
                (),
                0,
                "field-aware-structured-bounded-v1",
            )
        run = await self._authorized_assignment(actor, review_id, assignment_id)
        schema = await self._schema(actor, review_id, run.schema_version_id)
        sources = await self._load_sources(actor, review_id, documents)
        prepared = prepare_extraction_input(schema.fields, sources)
        if not prepared.chunks:
            raise ConflictError("the source set contains no AI-consumable parsed text")
        source_manifest = [_source_manifest(source) for source in sources]
        input_data = {
            "review_id": str(review_id),
            "study_id": str(run.study_id),
            "assignment_id": str(run.id),
            "schema_version_id": str(schema.id),
            "schema_identity": {
                "schema_version_id": str(schema.id),
                "schema_id": str(schema.schema_id),
                "schema_hash": schema.content_hash,
                "ordered_field_hash": ordered_field_hash(schema.fields),
            },
            "schema_fields": [_schema_field(item) for item in schema.fields],
            "source_documents": source_manifest,
            "chunks": list(prepared.chunks),
            "input_preparation": {
                "method": prepared.selection_method,
                "candidate_chunk_ids": [str(item["chunk_id"]) for item in prepared.chunks]
                + [str(item["chunk_id"]) for item in prepared.omitted_chunks],
                "selected_chunk_ids": list(prepared.selected_chunk_ids),
                "omitted_chunks": list(prepared.omitted_chunks),
                "field_targets": {
                    key: list(value) for key, value in prepared.field_targets.items()
                },
                "chunk_manifest_hash": prepared.chunk_manifest_hash,
                "selected_text_hash": prepared.selected_text_hash,
            },
            "references": [
                {"type": "extraction_schema_version", "id": str(schema.id)},
                {"type": "extraction_assignment", "id": str(run.id)},
                {"type": "study", "id": str(run.study_id)},
                *[
                    {"type": "document_processing_run", "id": str(source.processing.id)}
                    for source in sources
                ],
            ],
        }
        ai_run, proposal = await self._execution.create_and_execute(
            actor,
            review_id=review_id,
            task_type=AITaskType.EXTRACTION_SUGGESTION,
            input_data=input_data,
            model_version_id=model_version_id,
            prompt_version_id=prompt_version_id,
            maximum_attempts=maximum_attempts,
            timeout_seconds=timeout_seconds,
            per_run_token_ceiling=per_run_token_ceiling,
            target_type="EXTRACTION_ASSIGNMENT",
            target_id=run.id,
        )
        if proposal is None:
            return AIExtractionProposalView(
                run.id,
                run.study_id,
                schema.id,
                None,
                ai_run.id,
                mode,
                AIExtractionReadiness.READY,
                "FAILED",
                f"AI run ended in {ai_run.state.value}; no proposal was created",
                False,
                None,
                None,
                False,
                (),
                tuple(source_manifest),
                prepared.selected_chunk_ids,
                len(prepared.omitted_chunks),
                prepared.selection_method,
            )
        validation = validate_extraction_output(
            proposal.structured_value, schema.fields, input_data
        )
        evidence = _evidence_rows(proposal, prepared.chunks)
        link = await self._repository.create_proposal_link(
            organization_id=actor.organization_id,
            review_id=review_id,
            proposal_id=proposal.id,
            ai_run_id=ai_run.id,
            assignment_id=run.id,
            study_id=run.study_id,
            schema_version_id=schema.id,
            schema_hash=schema.content_hash,
            ordered_field_hash=ordered_field_hash(schema.fields),
            task_definition_version=STRUCTURED_EXTRACTION_TASK.version,
            assistance_mode=mode.value,
            source_manifest=source_manifest,
            selected_chunk_ids=list(prepared.selected_chunk_ids),
            omitted_chunks=list(prepared.omitted_chunks),
            field_targets={key: list(value) for key, value in prepared.field_targets.items()},
            selection_method=prepared.selection_method,
            chunk_manifest_hash=prepared.chunk_manifest_hash,
            selected_text_hash=prepared.selected_text_hash,
            validation_results=validation,
            sources=[_source_row(source) for source in sources],
            evidence=evidence,
        )
        await self._audit(
            actor,
            review_id,
            proposal.id,
            "AI_EXTRACTION_PROPOSAL_CREATED",
            {
                "assignment_id": str(run.id),
                "schema_version_id": str(schema.id),
                "source_document_ids": [str(source.document.id) for source in sources],
                "valid_field_count": validation["valid_field_count"],
                "canonical_extraction_mutated": False,
            },
        )
        return await self._view(actor, run, proposal, link)

    async def get_suggestion(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assignment_id: UUID | None = None,
        proposal_id: UUID | None = None,
    ) -> AIExtractionProposalView:
        await self._reviews.get(actor, review_id)
        if (assignment_id is None) == (proposal_id is None):
            raise ValueError("exactly one assignment or proposal ID is required")
        if proposal_id is not None:
            link = await self._repository.get_link(actor.organization_id, review_id, proposal_id)
        else:
            assert assignment_id is not None
            link = await self._repository.latest_assignment_link(
                actor.organization_id, review_id, assignment_id
            )
        if link is None:
            raise ResourceNotFoundError("AI extraction proposal was not found")
        run = await self._authorized_assignment(actor, review_id, link.assignment_id)
        proposal = await self._ai_repository.get_proposal(
            actor.organization_id, review_id, link.proposal_id
        )
        if proposal is None:
            raise ResourceNotFoundError("AI extraction proposal was not found")
        return await self._view(actor, run, proposal, link)

    async def list_suggestions(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[AIExtractionProposalView]:
        await self._reviews.get(actor, review_id)
        views: list[AIExtractionProposalView] = []
        for link in await self._repository.list_links(actor.organization_id, review_id):
            if link.assignment_id not in {item.assignment_id for item in views}:
                try:
                    views.append(
                        await self.get_suggestion(
                            actor, review_id=review_id, proposal_id=link.proposal_id
                        )
                    )
                except ResourceNotFoundError:
                    continue
        return views

    async def review_field(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        proposal_id: UUID,
        field_id: str,
        action: AIExtractionFieldReviewAction,
        human_value: dict[str, Any] | None,
        reason: str | None,
    ) -> dict[str, Any]:
        AuthorizationService.require(actor, Permission.PERFORM_EXTRACTION)
        view = await self.get_suggestion(actor, review_id=review_id, proposal_id=proposal_id)
        if view.stale and action in {
            AIExtractionFieldReviewAction.ACCEPTED,
            AIExtractionFieldReviewAction.EDITED,
        }:
            raise ConflictError("a stale AI extraction field cannot be accepted or edited")
        if not view.is_revealed or view.structured_value is None:
            raise ConflictError("the blinded AI extraction proposal is not yet revealed")
        field = _find_field(view.structured_value, field_id)
        validation = field_validation(view.validation_results or {}, field_id)
        if action is AIExtractionFieldReviewAction.ACCEPTED and not (
            validation and validation.get("valid")
        ):
            raise ConflictError("an invalid AI extraction field cannot be accepted")
        run = await self._authorized_assignment(actor, review_id, view.assignment_id)
        if view.mode is AIScreeningMode.BLINDED_AI and action in {
            AIExtractionFieldReviewAction.ACCEPTED,
            AIExtractionFieldReviewAction.EDITED,
        }:
            raise ConflictError("blinded proposals are comparison-only after human submission")
        canonical_value_id: UUID | None = None
        human_snapshot: dict[str, Any] | None = human_value
        if action in {
            AIExtractionFieldReviewAction.ACCEPTED,
            AIExtractionFieldReviewAction.EDITED,
        }:
            payload = (
                await self._accepted_manual_payload(actor, review_id, view, field)
                if action is AIExtractionFieldReviewAction.ACCEPTED
                else _edited_manual_payload(field_id, human_value)
            )
            updated, values = await self._manual.save_values(
                actor,
                review_id=review_id,
                run_id=run.id,
                values=[payload],
                status=ExtractionRunStatus.IN_PROGRESS,
            )
            canonical = next(item for item in values if item.field_key == field_id)
            canonical_value_id = canonical.id
            human_snapshot = payload
            await self._provenance.append_provenance(
                organization_id=actor.organization_id,
                review_id=review_id,
                subject_type="extraction_value",
                subject_id=canonical.id,
                source_type="ai_extraction_proposal",
                source_id=proposal_id,
                source_locator={
                    "field_id": field_id,
                    "action": action.value,
                    "ai_run_id": str(view.ai_run_id),
                    "human_extraction_run_id": str(updated.id),
                },
                method_name="human-reviewed-ai-extraction-assistance",
                method_version="1",
                actor_kind=ProvenanceActorKind.HUMAN,
                actor_user_id=actor.user_id,
                ai_run_id=None,
                confidence=None,
                verification_state=VerificationState.UNVERIFIED,
            )
        record = await self._repository.record_field_review(
            organization_id=actor.organization_id,
            review_id=review_id,
            proposal_id=proposal_id,
            assignment_id=run.id,
            field_key=field_id,
            reviewer_user_id=actor.user_id,
            action=action.value,
            ai_value_snapshot=field,
            human_value_snapshot=human_snapshot,
            canonical_value_id=canonical_value_id,
            reason=reason.strip() if reason else None,
        )
        await self._audit(
            actor,
            review_id,
            record.id,
            "AI_EXTRACTION_FIELD_REVIEWED",
            {
                "proposal_id": str(proposal_id),
                "field_id": field_id,
                "action": action.value,
                "canonical_value_id": str(canonical_value_id) if canonical_value_id else None,
            },
        )
        return {
            "id": record.id,
            "field_id": field_id,
            "action": action.value,
            "canonical_value_id": canonical_value_id,
            "human_actor_id": actor.user_id,
        }

    async def create_dataset(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        schema_version_id: UUID,
        logical_key: str,
        name: str,
        reference_standard: AIExtractionReferenceStandard,
        tolerance_policy_version: str | None,
        cases: list[dict[str, Any]],
    ) -> AIExtractionEvaluationDataset:
        AuthorizationService.require(actor, Permission.MANAGE_AI)
        await self._reviews.get(actor, review_id)
        schema = await self._schema(actor, review_id, schema_version_id)
        fields = {str(item["key"]): item for item in schema.fields}
        normalized: list[dict[str, Any]] = []
        for case in cases:
            study_id = UUID(str(case["study_id"]))
            field_key = str(case["field_key"])
            field = fields.get(field_key)
            if field is None:
                raise ConflictError("evaluation case field is not in the pinned schema")
            if await self._studies.get_study(actor.organization_id, review_id, study_id) is None:
                raise ResourceNotFoundError("evaluation case Study was not found")
            reference_missingness = _reference_missingness(case.get("reference_missingness"))
            _validate_reference_value(field, case, reference_missingness)
            source_id = _optional_uuid(case.get("reference_source_id"))
            if reference_standard is not AIExtractionReferenceStandard.CURATED_GOLD and (
                source_id is None
                or not await self._repository.verified_reference_exists(
                    actor.organization_id, review_id, source_id
                )
            ):
                raise ConflictError(
                    "non-curated reference values require matched or adjudicated "
                    "dual-human provenance"
                )
            normalized.append(
                {
                    "study_id": study_id,
                    "field_key": field_key,
                    "field_type": str(field["field_type"]),
                    "reference_missingness": reference_missingness.value,
                    "reference_value": case.get("reference_value"),
                    "reference_unit": case.get("reference_unit"),
                    "reference_source_id": source_id,
                    "evidence_snapshot": case.get("evidence_snapshot"),
                    "absolute_tolerance": case.get("absolute_tolerance"),
                }
            )
        dataset_hash = content_hash(
            {
                "schema_version_id": str(schema.id),
                "schema_hash": schema.content_hash,
                "reference_standard": reference_standard.value,
                "tolerance_policy_version": tolerance_policy_version,
                "cases": normalized,
            }
        )
        dataset = await self._repository.create_dataset(
            organization_id=actor.organization_id,
            review_id=review_id,
            schema_version_id=schema.id,
            logical_key=logical_key.strip(),
            name=name.strip(),
            reference_standard=reference_standard.value,
            tolerance_policy_version=tolerance_policy_version,
            content_hash=dataset_hash,
            created_by_user_id=actor.user_id,
            cases=normalized,
        )
        await self._audit(
            actor,
            review_id,
            dataset.id,
            "AI_EXTRACTION_EVALUATION_DATASET_CREATED",
            {"case_count": len(normalized), "reference_standard": reference_standard.value},
        )
        return dataset

    async def evaluate_dataset(
        self, actor: ActorContext, *, review_id: UUID, dataset_id: UUID
    ) -> AIExtractionEvaluationResultRecord:
        AuthorizationService.require(actor, Permission.MANAGE_AI)
        await self._reviews.get(actor, review_id)
        dataset = await self._repository.get_dataset(actor.organization_id, review_id, dataset_id)
        if dataset is None:
            raise ResourceNotFoundError("AI extraction evaluation dataset was not found")
        cases = await self._repository.list_cases(actor.organization_id, review_id, dataset.id)
        results: list[dict[str, Any]] = []
        for case in cases:
            link = await self._repository.latest_study_link(
                actor.organization_id, review_id, case.study_id
            )
            proposal: AIOutputProposal | None = None
            prediction: dict[str, Any] | None = None
            validation: dict[str, Any] | None = None
            if link is not None and link.schema_version_id == dataset.schema_version_id:
                run = await self._manual_repository.get_run(
                    actor.organization_id, review_id, link.assignment_id
                )
                revealed = link.assistance_mode is AIScreeningMode.ASSISTED or (
                    run is not None and _submitted(run)
                )
                if revealed:
                    proposal = await self._ai_repository.get_proposal(
                        actor.organization_id, review_id, link.proposal_id
                    )
                    if proposal is not None:
                        prediction = _optional_field(proposal.structured_value, case.field_key)
                        validation = field_validation(link.validation_results, case.field_key)
            evaluated = evaluate_field(
                prediction=prediction,
                validation=validation,
                reference_missingness=case.reference_missingness,
                reference_value=case.reference_value,
                field_type=case.field_type,
                absolute_tolerance=case.absolute_tolerance,
            )
            categories = _error_categories(
                evaluated["classification"], case.field_type, prediction, validation
            )
            results.append(
                {
                    "case_id": case.id,
                    "proposal_id": proposal.id if proposal else None,
                    "classification": evaluated["classification"],
                    "ai_status": prediction.get("status") if prediction else None,
                    "ai_value": prediction.get("value") if prediction else None,
                    "reference_value": case.reference_value,
                    "absolute_error": evaluated["absolute_error"],
                    "relative_error": evaluated["relative_error"],
                    "evidence_valid": evaluated["evidence_valid"],
                    "error_categories": categories,
                    "confidence": prediction.get("confidence") if prediction else None,
                    "source_location": _first_evidence(
                        prediction, link.source_manifest if link else []
                    ),
                    "validation_errors": list(validation.get("errors", []))
                    if validation
                    else ["INVALID_PROPOSAL"],
                    "reference_missingness": case.reference_missingness,
                    "field_type": case.field_type,
                    "field_key": case.field_key,
                }
            )
        metrics = aggregate_metrics(results)
        persisted = [
            {
                key: value
                for key, value in item.items()
                if key
                not in {
                    "field_type",
                    "field_key",
                    "validation_errors",
                    "reference_missingness",
                }
            }
            for item in results
        ]
        dimensions = {
            "dataset_id": str(dataset.id),
            "schema_version_id": str(dataset.schema_version_id),
            "reference_standard": dataset.reference_standard.value,
            "task_definition_version": STRUCTURED_EXTRACTION_TASK.version,
        }
        result = await self._repository.create_evaluation(
            organization_id=actor.organization_id,
            review_id=review_id,
            dataset_id=dataset.id,
            metrics=metrics,
            dimensions=dimensions,
            result_hash=content_hash({"metrics": metrics, "cases": persisted}),
            created_by_user_id=actor.user_id,
            case_results=persisted,
        )
        await self._audit(
            actor,
            review_id,
            result.id,
            "AI_EXTRACTION_EVALUATION_COMPLETED",
            {
                "hallucination_count": metrics["hallucination_count"],
                "evidence_invalid_count": metrics["evidence_invalid_count"],
            },
        )
        return result

    async def list_datasets(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[AIExtractionEvaluationDataset]:
        await self._reviews.get(actor, review_id)
        return await self._repository.list_datasets(actor.organization_id, review_id)

    async def list_evaluations(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[AIExtractionEvaluationResultRecord]:
        await self._reviews.get(actor, review_id)
        return await self._repository.list_evaluations(actor.organization_id, review_id)

    async def high_risk_queue(
        self, actor: ActorContext, *, review_id: UUID, evaluation_result_id: UUID
    ) -> list[Any]:
        await self._reviews.get(actor, review_id)
        return await self._repository.high_risk_queue(
            actor.organization_id, review_id, evaluation_result_id
        )

    async def list_case_results(
        self, actor: ActorContext, *, review_id: UUID, evaluation_result_id: UUID
    ) -> list[Any]:
        await self._reviews.get(actor, review_id)
        evaluations = await self._repository.list_evaluations(actor.organization_id, review_id)
        if evaluation_result_id not in {item.id for item in evaluations}:
            raise ResourceNotFoundError("AI extraction evaluation result was not found")
        return await self._repository.list_case_results(
            actor.organization_id, review_id, evaluation_result_id
        )

    async def classify_error(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        case_result_id: UUID,
        category: AIExtractionErrorCategory,
        note: str | None,
    ) -> Any:
        AuthorizationService.require(actor, Permission.MANAGE_AI)
        await self._reviews.get(actor, review_id)
        try:
            record = await self._repository.classify_error(
                organization_id=actor.organization_id,
                review_id=review_id,
                case_result_id=case_result_id,
                category=category.value,
                note=note.strip() if note else None,
                classified_by_user_id=actor.user_id,
            )
        except LookupError as exc:
            raise ResourceNotFoundError(str(exc)) from exc
        await self._audit(
            actor,
            review_id,
            record.id,
            "AI_EXTRACTION_ERROR_CLASSIFIED",
            {"case_result_id": str(case_result_id), "category": category.value},
        )
        return record

    async def _view(
        self,
        actor: ActorContext,
        run: ExtractionRun,
        proposal: AIOutputProposal,
        link: AIExtractionProposalLink,
    ) -> AIExtractionProposalView:
        reveal = link.assistance_mode is AIScreeningMode.ASSISTED or _submitted(run)
        if reveal:
            await self._repository.record_access(
                organization_id=actor.organization_id,
                review_id=run.review_id,
                proposal_id=proposal.id,
                assignment_id=run.id,
                reviewer_user_id=actor.user_id,
                access_type=("POST_SUBMISSION_REVEAL" if _submitted(run) else "ASSISTED_VIEW"),
                canonical_run_id=run.id if _submitted(run) else None,
                reason="human extraction submitted" if _submitted(run) else "assisted extraction",
            )
        stale_reasons = await self._stale_reasons(actor, link)
        return AIExtractionProposalView(
            run.id,
            run.study_id,
            run.schema_version_id,
            proposal.id,
            proposal.ai_run_id,
            link.assistance_mode,
            AIExtractionReadiness.READY,
            "SUCCEEDED",
            None,
            reveal,
            proposal.structured_value if reveal else None,
            link.validation_results if reveal else None,
            bool(stale_reasons),
            tuple(stale_reasons),
            tuple(link.source_manifest),
            link.selected_chunk_ids,
            len(link.omitted_chunks),
            link.selection_method,
        )

    async def _stale_reasons(
        self, actor: ActorContext, link: AIExtractionProposalLink
    ) -> list[str]:
        reasons: list[str] = []
        schema = await self._schemas.get_version(
            actor.organization_id, link.review_id, link.schema_version_id
        )
        if schema is None or schema.content_hash != link.schema_hash:
            reasons.append("SCHEMA_CONTENT_CHANGED")
        elif ordered_field_hash(schema.fields) != link.ordered_field_hash:
            reasons.append("ORDERED_FIELDS_CHANGED")
        else:
            versions = await self._schemas.list_versions(
                actor.organization_id, link.review_id, schema.schema_id
            )
            if versions and versions[-1].id != schema.id:
                reasons.append("ACTIVE_SCHEMA_VERSION_CHANGED")
        sources: list[ExtractionSource] = []
        for snapshot in link.source_manifest:
            document_id = UUID(str(snapshot["document_id"]))
            document = await self._documents.get_document(actor.organization_id, document_id)
            if document is None or document.review_id != link.review_id:
                reasons.append("SOURCE_DOCUMENT_CHANGED")
                continue
            current = await self._documents.latest_successful_processing_run(
                actor.organization_id, link.review_id, document.id
            )
            if current is None or str(current.id) != str(snapshot["processing_run_id"]):
                reasons.append("PARSED_CONTENT_CHANGED")
                continue
            blocks = await self._documents.list_blocks(
                actor.organization_id, link.review_id, document.id
            )
            role = FullTextDocumentRole(str(snapshot["document_role"]))
            sources.append(ExtractionSource(document, current, role, tuple(blocks)))
            documents = await self._documents.list_documents_for_article(
                actor.organization_id, link.review_id, document.article_id
            )
            processed = [item for item in documents if item.status is DocumentStatus.PROCESSED]
            if processed and processed[-1].id != document.id:
                reasons.append("SOURCE_DOCUMENT_VERSION_CHANGED")
        if schema is not None and len(sources) == len(link.source_manifest):
            prepared = prepare_extraction_input(schema.fields, sources)
            if prepared.chunk_manifest_hash != link.chunk_manifest_hash:
                reasons.append("CHUNK_MANIFEST_CHANGED")
            elif prepared.selected_text_hash != link.selected_text_hash:
                reasons.append("SELECTED_CHUNKS_CHANGED")
        if link.task_definition_version != STRUCTURED_EXTRACTION_TASK.version:
            reasons.append("TASK_DEFINITION_CHANGED")
        ai_run = await self._ai_repository.get_run(
            actor.organization_id, link.review_id, link.ai_run_id
        )
        prompts = await self._ai_repository.list_prompts(actor.organization_id)
        extraction_prompts = [
            item for item in prompts if item.task_type is AITaskType.EXTRACTION_SUGGESTION
        ]
        if ai_run is None or (
            extraction_prompts and extraction_prompts[-1].id != ai_run.prompt_version_id
        ):
            reasons.append("PROMPT_VERSION_CHANGED")
        return list(dict.fromkeys(reasons))

    async def _accepted_manual_payload(
        self,
        actor: ActorContext,
        review_id: UUID,
        view: AIExtractionProposalView,
        field: dict[str, Any],
    ) -> dict[str, Any]:
        status = AIExtractionFieldStatus(str(field["status"]))
        source_manifest = list(view.source_manifest)
        if not source_manifest:
            raise ConflictError("AI extraction proposal has no pinned source")
        source_article_id = UUID(str(source_manifest[0]["article_id"]))
        evidence_location_id: UUID | None = None
        evidence_text: str | None = None
        if status is AIExtractionFieldStatus.PROPOSED_VALUE:
            span = field.get("evidence", [])[0]
            document = await self._documents.get_document(
                actor.organization_id, UUID(str(span["document_id"]))
            )
            if document is None or document.review_id != review_id:
                raise ResourceNotFoundError("AI evidence document was not found")
            chunk_id = str(span["chunk_id"])
            ai_run = await self._ai_repository.get_run(
                actor.organization_id, review_id, view.ai_run_id or UUID(int=0)
            )
            variables = ai_run.input_snapshot.get("variables", {}) if ai_run else {}
            chunk = next(
                (
                    item
                    for item in variables.get("chunks", [])
                    if isinstance(item, dict) and item.get("chunk_id") == chunk_id
                ),
                None,
            )
            if chunk is None:
                raise ConflictError("AI evidence chunk is not in the immutable run input")
            block_id = UUID(str(chunk["source_block_id"]))
            location = await self._documents.create_evidence_location(
                document=document,
                block_id=block_id,
                page_number=span.get("page"),
                section=span.get("section"),
                source_text=span.get("quote"),
                table_id=span.get("table_id"),
                figure_id=span.get("figure_id"),
                coordinates=None,
            )
            source_article_id = document.article_id
            evidence_location_id = location.id
            evidence_text = str(span.get("quote"))
        return {
            "field_key": str(field["field_id"]),
            "value": field.get("value"),
            "missingness": manual_missingness(status).value,
            "unit": field.get("unit"),
            "source_article_id": str(source_article_id),
            "evidence_location_id": str(evidence_location_id) if evidence_location_id else None,
            "evidence_text": evidence_text,
        }

    async def _authorized_assignment(
        self, actor: ActorContext, review_id: UUID, assignment_id: UUID
    ) -> ExtractionRun:
        run = await self._manual_repository.get_run(actor.organization_id, review_id, assignment_id)
        if run is None or run.extractor_user_id != actor.user_id:
            raise ResourceNotFoundError("human extraction assignment was not found")
        return run

    async def _schema(
        self, actor: ActorContext, review_id: UUID, schema_version_id: UUID
    ) -> ExtractionSchemaVersion:
        schema = await self._schemas.get_version(
            actor.organization_id, review_id, schema_version_id
        )
        if schema is None:
            raise ResourceNotFoundError("extraction schema version was not found")
        return schema

    async def _load_sources(
        self, actor: ActorContext, review_id: UUID, requested: list[dict[str, Any]]
    ) -> list[ExtractionSource]:
        sources: list[ExtractionSource] = []
        for item in requested:
            document_id = UUID(str(item["document_id"]))
            document = await self._documents.get_document(actor.organization_id, document_id)
            processing = await self._documents.latest_successful_processing_run(
                actor.organization_id, review_id, document_id
            )
            blocks = await self._documents.list_blocks(
                actor.organization_id, review_id, document_id
            )
            if document is None or processing is None:
                raise ConflictError("source document is no longer extraction-ready")
            sources.append(
                ExtractionSource(
                    document,
                    processing,
                    FullTextDocumentRole(
                        str(item.get("document_role", FullTextDocumentRole.PRIMARY_FULL_TEXT.value))
                    ),
                    tuple(blocks),
                )
            )
        return sources

    async def _audit(
        self,
        actor: ActorContext,
        review_id: UUID,
        entity_id: UUID,
        action: str,
        snapshot: dict[str, Any],
    ) -> None:
        await self._provenance.append_audit_event(
            organization_id=actor.organization_id,
            review_id=review_id,
            entity_type="AI_STRUCTURED_EXTRACTION",
            entity_id=entity_id,
            action=action,
            actor_user_id=actor.user_id,
            before_snapshot=None,
            after_snapshot=snapshot,
            reason=None,
        )


def _field_type(field: dict[str, Any]) -> ExtractionFieldType:
    return ExtractionFieldType(str(field["field_type"]))


def _schema_field(field: dict[str, Any]) -> dict[str, Any]:
    return {
        "field_id": str(field["key"]),
        "label": field["label"],
        "description": field.get("description"),
        "section": field.get("section"),
        "field_type": field["field_type"],
        "required": bool(field.get("required")),
        "allowed_options": field.get("allowed_options", []),
        "unit": field.get("unit"),
        "instructions": field.get("instructions"),
        "display_order": field.get("display_order"),
    }


def _source_manifest(source: ExtractionSource) -> dict[str, Any]:
    parsed_hash = content_hash(
        [
            {
                "block_id": item.block_id,
                "block_type": item.block_type.value,
                "order": item.block_order,
                "page": item.page_number,
                "section_path": item.section_path,
                "table_id": item.table_id,
                "figure_id": item.figure_id,
                "text_hash": content_hash(item.text),
            }
            for item in source.blocks
        ]
    )
    return {
        "article_id": str(source.document.article_id),
        "document_id": str(source.document.id),
        "document_version_id": str(source.document.id),
        "document_role": source.role.value,
        "document_content_hash": source.document.sha256
        or content_hash(
            {
                "document_id": str(source.document.id),
                "source_identifier": source.document.source_identifier,
            }
        ),
        "processing_run_id": str(source.processing.id),
        "parser_name": source.processing.parser_name,
        "parser_version": source.processing.parser_version,
        "parsed_content_hash": parsed_hash,
    }


def _source_row(source: ExtractionSource) -> dict[str, Any]:
    snapshot = _source_manifest(source)
    return {
        "article_id": source.document.article_id,
        "document_id": source.document.id,
        "document_version_id": source.document.id,
        "processing_run_id": source.processing.id,
        "document_role": source.role.value,
        "document_content_hash": snapshot["document_content_hash"],
        "parser_name": source.processing.parser_name,
        "parser_version": source.processing.parser_version,
        "parsed_content_hash": snapshot["parsed_content_hash"],
    }


def _evidence_rows(
    proposal: AIOutputProposal, chunks: tuple[dict[str, Any], ...]
) -> list[dict[str, Any]]:
    chunk_map = {str(item["chunk_id"]): item for item in chunks}
    rows: list[dict[str, Any]] = []
    for field in proposal.structured_value.get("fields", []):
        if not isinstance(field, dict) or not isinstance(field.get("evidence"), list):
            continue
        for ordinal, span in enumerate(field["evidence"], 1):
            if not isinstance(span, dict):
                continue
            chunk = chunk_map.get(str(span.get("chunk_id")))
            if chunk is None or str(span.get("document_id")) != str(chunk["document_id"]):
                continue
            quote = str(span.get("quote") or "")
            rows.append(
                {
                    "field_key": str(field.get("field_id")),
                    "ordinal": ordinal,
                    "document_id": UUID(str(chunk["document_id"])),
                    "document_version_id": UUID(str(chunk["document_version_id"])),
                    "chunk_id": str(chunk["chunk_id"]),
                    "source_block_id": UUID(str(chunk["source_block_id"])),
                    "page": span.get("page"),
                    "section": span.get("section"),
                    "table_id": span.get("table_id"),
                    "figure_id": span.get("figure_id"),
                    "quote": quote,
                    "evidence_hash": content_hash(
                        {
                            "document_id": chunk["document_id"],
                            "document_version_id": chunk["document_version_id"],
                            "chunk_id": chunk["chunk_id"],
                            "quote": quote,
                        }
                    ),
                }
            )
    return rows


def _find_field(value: dict[str, Any], field_id: str) -> dict[str, Any]:
    matches = [
        item
        for item in value.get("fields", [])
        if isinstance(item, dict) and item.get("field_id") == field_id
    ]
    if len(matches) != 1:
        raise ConflictError("AI extraction field is missing or ambiguous")
    return matches[0]


def _optional_field(value: dict[str, Any], field_id: str) -> dict[str, Any] | None:
    try:
        return _find_field(value, field_id)
    except ConflictError:
        return None


def _edited_manual_payload(field_id: str, human_value: dict[str, Any] | None) -> dict[str, Any]:
    if human_value is None:
        raise ConflictError("an edited field requires an explicit human value")
    result = dict(human_value)
    result["field_key"] = field_id
    return result


def _first_evidence(
    prediction: dict[str, Any] | None, source_manifest: list[dict[str, Any]]
) -> dict[str, Any] | None:
    if prediction is None or not isinstance(prediction.get("evidence"), list):
        return None
    if not prediction["evidence"]:
        return None
    evidence = dict(prediction["evidence"][0])
    source = next(
        (
            item
            for item in source_manifest
            if str(item.get("document_id")) == str(evidence.get("document_id"))
        ),
        None,
    )
    if source:
        evidence["document_role"] = source.get("document_role")
        evidence["article_id"] = source.get("article_id")
    return evidence


def _error_categories(
    classification: str,
    field_type: str,
    prediction: dict[str, Any] | None,
    validation: dict[str, Any] | None,
) -> list[str]:
    if classification == AIExtractionMatchClass.AI_VALUE_REFERENCE_MISSING.value:
        return [AIExtractionErrorCategory.HALLUCINATED_VALUE.value]
    if classification == AIExtractionMatchClass.EVIDENCE_INVALID.value:
        errors = set(validation.get("errors", [])) if validation else set()
        categories: list[str] = []
        if errors & {"WRONG_DOCUMENT", "WRONG_DOCUMENT_VERSION"}:
            categories.append(AIExtractionErrorCategory.WRONG_DOCUMENT.value)
        if "QUOTE_MISMATCH" in errors:
            categories.append(AIExtractionErrorCategory.QUOTE_MISMATCH.value)
        if errors & {"INVALID_CHUNK_REFERENCE", "MISSING_EVIDENCE", "MISSING_EVIDENCE_QUOTE"}:
            categories.append(AIExtractionErrorCategory.FABRICATED_EVIDENCE.value)
        if errors & {"INVALID_OPTION", "WRONG_TYPE", "UNKNOWN_FIELD", "DUPLICATE_FIELD"}:
            categories.append(AIExtractionErrorCategory.SCHEMA_MISINTERPRETATION.value)
        return categories or [AIExtractionErrorCategory.FABRICATED_EVIDENCE.value]
    if classification == AIExtractionMatchClass.AI_MISSING_REFERENCE_VALUE.value:
        return [AIExtractionErrorCategory.MISSED_REPORTED_VALUE.value]
    if classification == AIExtractionMatchClass.MISMATCH.value:
        if field_type in {"CATEGORICAL", "ENUM"}:
            return [AIExtractionErrorCategory.WRONG_OPTION.value]
        return [AIExtractionErrorCategory.WRONG_VALUE.value]
    if prediction and prediction.get("status") == "REQUIRES_TABLE_OR_FIGURE":
        return [AIExtractionErrorCategory.TABLE_REQUIRED.value]
    return []


def _submitted(run: ExtractionRun) -> bool:
    return run.status in {
        ExtractionRunStatus.COMPLETED,
        ExtractionRunStatus.NEEDS_REVIEW,
        ExtractionRunStatus.VERIFIED,
        ExtractionRunStatus.CONFLICT,
    }


def _optional_uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value)) if value is not None else None
    except (ValueError, TypeError):
        return None


def _reference_missingness(value: Any) -> MissingnessState:
    try:
        return MissingnessState(str(value))
    except ValueError as exc:
        raise ConflictError("evaluation reference missingness is invalid") from exc


def _validate_reference_value(
    field: dict[str, Any], case: dict[str, Any], missingness: MissingnessState
) -> None:
    value = case.get("reference_value")
    unit = case.get("reference_unit")
    if missingness is not MissingnessState.VALUE_REPORTED:
        if value is not None or unit is not None:
            raise ConflictError("missing evaluation references cannot carry a value or unit")
        return
    if value is None:
        raise ConflictError("reported evaluation references require a value")
    kind = _field_type(field)
    valid = True
    try:
        if kind is ExtractionFieldType.INTEGER:
            valid = isinstance(value, int) and not isinstance(value, bool)
        elif kind is ExtractionFieldType.DECIMAL:
            valid = not isinstance(value, bool) and Decimal(str(value)).is_finite()
        elif kind is ExtractionFieldType.BOOLEAN:
            valid = isinstance(value, bool)
        elif kind is ExtractionFieldType.DATE:
            valid = isinstance(value, str) and bool(date.fromisoformat(value))
        elif kind in {ExtractionFieldType.CATEGORICAL, ExtractionFieldType.ENUM}:
            valid = value in field.get("allowed_options", [])
        elif kind in {ExtractionFieldType.TEXT, ExtractionFieldType.CITATION}:
            valid = isinstance(value, str)
        else:
            valid = False
    except (InvalidOperation, TypeError, ValueError):
        valid = False
    if not valid:
        raise ConflictError("evaluation reference value does not match the schema field type")
    if unit != field.get("unit"):
        raise ConflictError("evaluation reference unit does not match the schema field unit")
