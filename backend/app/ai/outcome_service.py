from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from backend.app.ai.domain import AITaskType, content_hash
from backend.app.ai.extraction_domain import ExtractionSource
from backend.app.ai.full_text_domain import FullTextDocumentRole
from backend.app.ai.outcome_domain import (
    AIOutcomeCandidateType,
    AIOutcomeErrorCategory,
    AIOutcomePolicy,
    AIOutcomeProposalLink,
    AIOutcomeReadiness,
    AIOutcomeReferenceStandard,
    AIOutcomeReviewAction,
    allowed_mapping_manifest,
    outcome_evaluation_metrics,
    prepare_outcome_input,
    source_manifest,
    validate_outcome_output,
)
from backend.app.ai.outcome_persistence import (
    AIOutcomeEvaluationResultRecord,
    SqlAlchemyAIOutcomeRepository,
)
from backend.app.ai.persistence import SqlAlchemyAIRepository
from backend.app.ai.service import AIExecutionService
from backend.app.ai.tasks import OUTCOME_TASK
from backend.app.core.errors import AuthorizationError, ConflictError, ResourceNotFoundError
from backend.app.documents.domain import DocumentStatus
from backend.app.documents.persistence import SqlAlchemyDocumentRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.outcomes.domain import (
    AdjustmentStatus,
    AnalysisPopulation,
    DirectionTransformation,
    EffectMeasure,
    EstimateOrigin,
    MappingMethod,
    TimeAnchor,
    TimeUnit,
    VarianceScale,
)
from backend.app.outcomes.persistence import SqlAlchemyOutcomeRepository
from backend.app.outcomes.service import OutcomeService
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.service import ReviewService
from backend.app.studies.persistence import SqlAlchemyStudyRepository


@dataclass(frozen=True, slots=True)
class AIOutcomeReadinessView:
    extraction_value_id: UUID
    study_id: UUID | None
    outcome_version_id: UUID | None
    state: AIOutcomeReadiness
    reason: str | None


@dataclass(frozen=True, slots=True)
class AIOutcomeProposalView:
    extraction_value_id: UUID
    study_id: UUID
    outcome_version_id: UUID
    proposal_id: UUID | None
    ai_run_id: UUID | None
    readiness: AIOutcomeReadiness
    status: str
    failure_reason: str | None
    structured_value: dict[str, Any] | None
    validation_results: dict[str, Any] | None
    stale: bool
    stale_reasons: tuple[str, ...]
    source_manifest: tuple[dict[str, Any], ...]
    selected_chunk_ids: tuple[str, ...]
    omitted_chunk_count: int
    selection_method: str


class AIOutcomeService:
    """Evidence-grounded outcome advice; canonical mappings remain human-owned."""

    def __init__(
        self,
        repository: SqlAlchemyAIOutcomeRepository,
        ai_repository: SqlAlchemyAIRepository,
        outcome_repository: SqlAlchemyOutcomeRepository,
        documents: SqlAlchemyDocumentRepository,
        studies: SqlAlchemyStudyRepository,
        reviews: ReviewService,
        provenance: ProvenanceService,
        execution: AIExecutionService,
        outcome_service: OutcomeService,
    ) -> None:
        self._repository = repository
        self._ai = ai_repository
        self._outcomes = outcome_repository
        self._documents = documents
        self._studies = studies
        self._reviews = reviews
        self._provenance = provenance
        self._execution = execution
        self._outcome_service = outcome_service

    async def create_policy(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        maximum_batch_size: int,
    ) -> AIOutcomePolicy:
        AuthorizationService.require(actor, Permission.MANAGE_AI)
        await self._reviews.get(actor, review_id)
        if not 1 <= maximum_batch_size <= 100:
            raise ValueError("maximum batch size must be from 1 through 100")
        policy = await self._repository.create_policy(
            organization_id=actor.organization_id,
            review_id=review_id,
            maximum_batch_size=maximum_batch_size,
            created_by_user_id=actor.user_id,
        )
        await self._audit(
            actor,
            review_id,
            policy.id,
            "AI_OUTCOME_POLICY_CREATED",
            {"maximum_batch_size": maximum_batch_size},
        )
        return policy

    async def readiness(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        extraction_value_id: UUID,
        outcome_version_id: UUID,
        documents: list[dict[str, Any]],
    ) -> AIOutcomeReadinessView:
        AuthorizationService.require(actor, Permission.HARMONIZE_OUTCOMES)
        await self._reviews.get(actor, review_id)
        context = await self._outcomes.extraction_value_context(
            actor.organization_id, review_id, extraction_value_id
        )
        if context is None:
            return AIOutcomeReadinessView(
                extraction_value_id,
                None,
                outcome_version_id,
                AIOutcomeReadiness.BLOCKED_NO_EXTRACTION,
                "extraction value was not found",
            )
        outcome = await self._outcomes.get_outcome_version(
            actor.organization_id, review_id, outcome_version_id
        )
        if outcome is None:
            return AIOutcomeReadinessView(
                extraction_value_id,
                context["study_id"],
                None,
                AIOutcomeReadiness.BLOCKED_OUTCOME_VERSION,
                "outcome version was not found",
            )
        if not context["verified"]:
            return AIOutcomeReadinessView(
                extraction_value_id,
                context["study_id"],
                outcome.id,
                AIOutcomeReadiness.BLOCKED_UNVERIFIED_EXTRACTION,
                "outcome assistance requires a verified extraction value",
            )
        if not documents or len(documents) > 8:
            return AIOutcomeReadinessView(
                extraction_value_id,
                context["study_id"],
                outcome.id,
                AIOutcomeReadiness.BLOCKED_SOURCE_SCOPE,
                "one through eight explicit source documents are required",
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
            except (TypeError, ValueError):
                return AIOutcomeReadinessView(
                    extraction_value_id,
                    context["study_id"],
                    outcome.id,
                    AIOutcomeReadiness.BLOCKED_SOURCE_SCOPE,
                    "source document identity or role is invalid",
                )
            if document_id in seen:
                return AIOutcomeReadinessView(
                    extraction_value_id,
                    context["study_id"],
                    outcome.id,
                    AIOutcomeReadiness.BLOCKED_SOURCE_SCOPE,
                    "source documents must be unique",
                )
            seen.add(document_id)
            document = await self._documents.get_document(actor.organization_id, document_id)
            if document is None or document.review_id != review_id:
                return AIOutcomeReadinessView(
                    extraction_value_id,
                    context["study_id"],
                    outcome.id,
                    AIOutcomeReadiness.BLOCKED_SOURCE_SCOPE,
                    "source document was not found in this review",
                )
            if not await self._studies.article_linked(
                actor.organization_id, review_id, context["study_id"], document.article_id
            ):
                return AIOutcomeReadinessView(
                    extraction_value_id,
                    context["study_id"],
                    outcome.id,
                    AIOutcomeReadiness.BLOCKED_SOURCE_SCOPE,
                    "source Article is not linked to the extraction Study",
                )
            if document.status is not DocumentStatus.PROCESSED:
                return AIOutcomeReadinessView(
                    extraction_value_id,
                    context["study_id"],
                    outcome.id,
                    AIOutcomeReadiness.BLOCKED_DOCUMENT_PROCESSING,
                    f"document {document.id} is not processed",
                )
            processing = await self._documents.latest_successful_processing_run(
                actor.organization_id, review_id, document.id
            )
            if processing is None:
                return AIOutcomeReadinessView(
                    extraction_value_id,
                    context["study_id"],
                    outcome.id,
                    AIOutcomeReadiness.BLOCKED_DOCUMENT_PROCESSING,
                    f"document {document.id} has no successful parser run",
                )
            blocks = await self._documents.list_blocks(
                actor.organization_id, review_id, document.id
            )
            if not any(block.text.strip() for block in blocks):
                return AIOutcomeReadinessView(
                    extraction_value_id,
                    context["study_id"],
                    outcome.id,
                    AIOutcomeReadiness.BLOCKED_NO_PARSED_TEXT,
                    f"document {document.id} has no parsed scientific text",
                )
        return AIOutcomeReadinessView(
            extraction_value_id,
            context["study_id"],
            outcome.id,
            AIOutcomeReadiness.READY,
            None,
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
    ) -> list[AIOutcomeProposalView]:
        if not actor.has_permission(Permission.HARMONIZE_OUTCOMES):
            raise AuthorizationError("the current role cannot request outcome assistance")
        await self._reviews.get(actor, review_id)
        policy = await self._repository.current_policy(actor.organization_id, review_id)
        if policy is None:
            raise ConflictError("AI outcome assistance is not configured for this review")
        if not requests or len(requests) > policy.maximum_batch_size:
            raise ConflictError("the outcome batch is empty or exceeds the active policy")
        identities = [
            f"{item.get('extraction_value_id')}:{item.get('outcome_version_id')}"
            for item in requests
        ]
        if len(identities) != len(set(identities)):
            raise ConflictError("outcome assistance requests must be unique")
        results: list[AIOutcomeProposalView] = []
        for request in requests:
            extraction_id = _uuid_or_zero(request.get("extraction_value_id"))
            outcome_id = _uuid_or_zero(request.get("outcome_version_id"))
            try:
                results.append(
                    await self._create_one(
                        actor,
                        review_id=review_id,
                        extraction_value_id=extraction_id,
                        outcome_version_id=outcome_id,
                        documents=list(request.get("documents") or []),
                        model_version_id=model_version_id,
                        prompt_version_id=prompt_version_id,
                        maximum_attempts=maximum_attempts,
                        timeout_seconds=timeout_seconds,
                        per_run_token_ceiling=per_run_token_ceiling,
                    )
                )
            except (ValueError, ConflictError, ResourceNotFoundError, AuthorizationError) as exc:
                results.append(
                    AIOutcomeProposalView(
                        extraction_id,
                        UUID(int=0),
                        outcome_id,
                        None,
                        None,
                        AIOutcomeReadiness.BLOCKED_OTHER,
                        "FAILED",
                        str(exc),
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
        extraction_value_id: UUID,
        outcome_version_id: UUID,
        documents: list[dict[str, Any]],
        model_version_id: UUID | None,
        prompt_version_id: UUID | None,
        maximum_attempts: int,
        timeout_seconds: int,
        per_run_token_ceiling: int | None,
    ) -> AIOutcomeProposalView:
        ready = await self.readiness(
            actor,
            review_id=review_id,
            extraction_value_id=extraction_value_id,
            outcome_version_id=outcome_version_id,
            documents=documents,
        )
        if ready.state is not AIOutcomeReadiness.READY:
            return AIOutcomeProposalView(
                extraction_value_id,
                ready.study_id or UUID(int=0),
                ready.outcome_version_id or UUID(int=0),
                None,
                None,
                ready.state,
                "BLOCKED",
                ready.reason,
                None,
                None,
                False,
                (),
                (),
                (),
                0,
                "field-aware-structured-bounded-v1",
            )
        context = await self._outcomes.extraction_value_context(
            actor.organization_id, review_id, extraction_value_id
        )
        outcome = await self._outcomes.get_outcome_version(
            actor.organization_id, review_id, outcome_version_id
        )
        if context is None or outcome is None:
            raise ResourceNotFoundError("outcome assistance input disappeared")
        sources = await self._load_sources(actor, review_id, documents)
        prepared = prepare_outcome_input(outcome.definition, sources)
        if not prepared.chunks:
            raise ConflictError("the source set contains no AI-consumable parsed text")
        configurations = await self._outcome_service.list_configuration(actor, review_id=review_id)
        units, windows, scales = configurations
        source_rows = source_manifest(sources)
        allowed = allowed_mapping_manifest(
            outcome.definition,
            units=[_unit(item) for item in units],
            windows=[_window(item) for item in windows],
            scales=[_scale(item) for item in scales],
        )
        input_data = {
            "review_id": str(review_id),
            "study_id": str(context["study_id"]),
            "extraction_value_id": str(extraction_value_id),
            "outcome_version_id": str(outcome.id),
            "outcome_definition": {"id": str(outcome.id), **outcome.definition},
            "extraction_value": _context_snapshot(context),
            "allowed_mappings": allowed,
            "source_documents": source_rows,
            "chunks": list(prepared.chunks),
            "input_preparation": {
                "method": prepared.selection_method,
                "selected_chunk_ids": list(prepared.selected_chunk_ids),
                "omitted_chunks": list(prepared.omitted_chunks),
                "chunk_manifest_hash": prepared.chunk_manifest_hash,
                "selected_text_hash": prepared.selected_text_hash,
            },
            "references": [
                {"type": "outcome_definition_version", "id": str(outcome.id)},
                {"type": "extraction_value", "id": str(extraction_value_id)},
                {"type": "study", "id": str(context["study_id"])},
                *[
                    {"type": "document_processing_run", "id": str(source.processing.id)}
                    for source in sources
                ],
            ],
        }
        ai_run, proposal = await self._execution.create_and_execute(
            actor,
            review_id=review_id,
            task_type=AITaskType.OUTCOME_MAPPING_SUGGESTION,
            input_data=input_data,
            model_version_id=model_version_id,
            prompt_version_id=prompt_version_id,
            maximum_attempts=maximum_attempts,
            timeout_seconds=timeout_seconds,
            per_run_token_ceiling=per_run_token_ceiling,
            target_type="OUTCOME_HARMONIZATION",
            target_id=extraction_value_id,
        )
        if proposal is None:
            return AIOutcomeProposalView(
                extraction_value_id,
                context["study_id"],
                outcome.id,
                None,
                ai_run.id,
                AIOutcomeReadiness.READY,
                ai_run.state.value,
                "AI output was invalid or execution failed",
                None,
                None,
                False,
                (),
                tuple(source_rows),
                tuple(prepared.selected_chunk_ids),
                len(prepared.omitted_chunks),
                prepared.selection_method,
            )
        validation_errors = validate_outcome_output(proposal.structured_value, input_data)
        link = await self._repository.create_link(
            organization_id=actor.organization_id,
            review_id=review_id,
            proposal_id=proposal.id,
            ai_run_id=ai_run.id,
            study_id=context["study_id"],
            extraction_value_id=extraction_value_id,
            outcome_version_id=outcome.id,
            outcome_version_hash=outcome.content_hash,
            extraction_snapshot_hash=content_hash(_context_snapshot(context)),
            task_definition_version=OUTCOME_TASK.version,
            source_manifest=source_rows,
            selected_chunk_ids=list(prepared.selected_chunk_ids),
            omitted_chunks=list(prepared.omitted_chunks),
            selection_method=prepared.selection_method,
            chunk_manifest_hash=prepared.chunk_manifest_hash,
            selected_text_hash=prepared.selected_text_hash,
            validation_results={
                "aggregate_valid": not validation_errors,
                "errors": validation_errors,
            },
        )
        await self._audit(
            actor,
            review_id,
            link.id,
            "AI_OUTCOME_PROPOSAL_LINKED",
            {
                "proposal_id": str(proposal.id),
                "outcome_version_id": str(outcome.id),
                "extraction_snapshot_hash": link.extraction_snapshot_hash,
            },
        )
        return await self._view(actor, link, proposal)

    async def get_proposal(
        self, actor: ActorContext, *, review_id: UUID, proposal_id: UUID
    ) -> AIOutcomeProposalView:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        link = await self._repository.get_link(actor.organization_id, review_id, proposal_id)
        if link is None:
            raise ResourceNotFoundError("AI outcome proposal was not found")
        proposal = await self._ai.get_proposal(actor.organization_id, review_id, proposal_id)
        if proposal is None:
            raise ResourceNotFoundError("AI outcome proposal was not found")
        return await self._view(actor, link, proposal)

    async def list_proposals(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[AIOutcomeProposalView]:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        result: list[AIOutcomeProposalView] = []
        for link in await self._repository.list_links(actor.organization_id, review_id):
            proposal = await self._ai.get_proposal(
                actor.organization_id, review_id, link.proposal_id
            )
            if proposal is not None:
                result.append(await self._view(actor, link, proposal))
        return result

    async def review_proposal(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        proposal_id: UUID,
        action: AIOutcomeReviewAction,
        canonical_action: str | None,
        human_payload: dict[str, Any] | None,
        reason: str | None,
    ) -> dict[str, Any]:
        AuthorizationService.require(actor, Permission.HARMONIZE_OUTCOMES)
        view = await self.get_proposal(actor, review_id=review_id, proposal_id=proposal_id)
        link = await self._repository.get_link(actor.organization_id, review_id, proposal_id)
        proposal = await self._ai.get_proposal(actor.organization_id, review_id, proposal_id)
        if link is None or proposal is None:
            raise ResourceNotFoundError("AI outcome proposal was not found")
        if action in {AIOutcomeReviewAction.ACCEPTED, AIOutcomeReviewAction.EDITED}:
            if view.stale:
                raise ConflictError("stale outcome proposals cannot be accepted")
            if not canonical_action or human_payload is None:
                raise ConflictError("human acceptance requires an explicit canonical payload")
            if action is AIOutcomeReviewAction.ACCEPTED:
                if not view.validation_results or not view.validation_results.get(
                    "aggregate_valid", False
                ):
                    raise ConflictError(
                        "invalid AI proposals require an explicit EDITED disposition"
                    )
                candidate_type = (proposal.structured_value or {}).get("candidate_type")
                expected_type = {
                    "CREATE_MAPPING": AIOutcomeCandidateType.MAPPING.value,
                    "CREATE_EFFECT_ESTIMATE": AIOutcomeCandidateType.EFFECT_ESTIMATE.value,
                }.get(canonical_action)
                if candidate_type != expected_type:
                    raise ConflictError("accepted canonical action does not match the AI candidate")
            canonical_id: UUID | None = None
            if canonical_action == "CREATE_MAPPING":
                canonical_id = (
                    await self._outcome_service.create_mapping(
                        actor,
                        review_id=review_id,
                        study_id=link.study_id,
                        extraction_value_id=link.extraction_value_id,
                        outcome_version_id=link.outcome_version_id,
                        method=MappingMethod.MANUAL,
                        **_mapping_payload(human_payload),
                    )
                ).id
            elif canonical_action == "CREATE_EFFECT_ESTIMATE":
                canonical_id = (
                    await self._outcome_service.create_effect_estimate(
                        actor,
                        review_id=review_id,
                        study_id=link.study_id,
                        outcome_version_id=link.outcome_version_id,
                        **_effect_payload(human_payload),
                    )
                ).id
            else:
                raise ConflictError("canonical action is not supported")
            await self._provenance.record_provenance(
                actor,
                review_id=review_id,
                subject_type="outcome_mapping"
                if canonical_action == "CREATE_MAPPING"
                else "effect_estimate",
                subject_id=canonical_id,
                source_type="AI_PROPOSAL",
                source_id=proposal_id,
                source_locator={"ai_run_id": str(link.ai_run_id)},
                method_name="human-accepted-ai-outcome-proposal",
                method_version="1",
                actor_kind=ProvenanceActorKind.HUMAN,
                ai_run_id=None,
                confidence=None,
                verification_state=VerificationState.HUMAN_VERIFIED,
            )
        else:
            canonical_action = None
            canonical_id = None
        review = await self._repository.record_review(
            organization_id=actor.organization_id,
            review_id=review_id,
            proposal_id=proposal_id,
            action=action.value,
            canonical_action=canonical_action,
            canonical_subject_id=canonical_id,
            ai_candidate_snapshot=proposal.structured_value,
            human_payload_snapshot=human_payload,
            reason=reason.strip() if reason else None,
            reviewer_user_id=actor.user_id,
        )
        await self._audit(
            actor,
            review_id,
            review.id,
            "AI_OUTCOME_PROPOSAL_REVIEWED",
            {
                "proposal_id": str(proposal_id),
                "action": action.value,
                "canonical_action": canonical_action,
                "canonical_subject_id": str(canonical_id) if canonical_id else None,
            },
        )
        return {
            "id": review.id,
            "proposal_id": proposal_id,
            "action": action.value,
            "canonical_action": canonical_action,
            "canonical_subject_id": canonical_id,
        }

    async def create_dataset(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        logical_key: str,
        name: str,
        reference_standard: AIOutcomeReferenceStandard,
        cases: list[dict[str, Any]],
    ) -> Any:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        if not cases or len(cases) > 100_000:
            raise ConflictError("outcome evaluation dataset requires at least one case")
        keys = [str(item.get("case_key", "")) for item in cases]
        if any(not key for key in keys) or len(keys) != len(set(keys)):
            raise ConflictError("evaluation case keys must be present and unique")
        payload = {
            "logical_key": logical_key.strip(),
            "name": name.strip(),
            "reference_standard": reference_standard.value,
            "cases": cases,
        }
        dataset = await self._repository.create_dataset(
            organization_id=actor.organization_id,
            review_id=review_id,
            logical_key=logical_key.strip(),
            name=name.strip(),
            reference_standard=reference_standard.value,
            cases=cases,
            content_hash=content_hash(payload),
            created_by_user_id=actor.user_id,
        )
        await self._audit(actor, review_id, dataset.id, "AI_OUTCOME_DATASET_CREATED", payload)
        return dataset

    async def list_datasets(self, actor: ActorContext, *, review_id: UUID) -> list[Any]:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        return await self._repository.list_datasets(actor.organization_id, review_id)

    async def evaluate_dataset(
        self, actor: ActorContext, *, review_id: UUID, dataset_id: UUID
    ) -> AIOutcomeEvaluationResultRecord:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        dataset = await self._repository.get_dataset(actor.organization_id, review_id, dataset_id)
        if dataset is None:
            raise ResourceNotFoundError("AI outcome evaluation dataset was not found")
        case_results: list[dict[str, Any]] = []
        for case in dataset.cases:
            proposal_id = _uuid_or_none(case.get("proposal_id"))
            proposal = (
                await self._ai.get_proposal(actor.organization_id, review_id, proposal_id)
                if proposal_id
                else None
            )
            link = (
                await self._repository.get_link(actor.organization_id, review_id, proposal_id)
                if proposal_id
                else None
            )
            candidate = proposal.structured_value if proposal is not None else None
            validation = link.validation_results if link is not None else None
            reference_type = case.get("reference_candidate_type")
            reference_match = bool(candidate and candidate.get("candidate_type") == reference_type)
            case_results.append(
                {
                    "case_key": case.get("case_key"),
                    "proposal_id": proposal_id,
                    "candidate_type": candidate.get("candidate_type") if candidate else None,
                    "validation_valid": bool(validation and validation.get("aggregate_valid")),
                    "reference_type": reference_type,
                    "reference_match": reference_match,
                    "error_categories": list(case.get("error_categories", [])),
                    "abstention": bool(
                        candidate
                        and candidate.get("candidate_type") == AIOutcomeCandidateType.ABSTAIN.value
                    ),
                }
            )
        metrics = outcome_evaluation_metrics(case_results)
        result = await self._repository.create_result(
            organization_id=actor.organization_id,
            review_id=review_id,
            dataset_id=dataset.id,
            metrics=metrics,
            dimensions={
                "reference_standard": dataset.reference_standard,
                "task_definition_version": OUTCOME_TASK.version,
                "calibration": "descriptive_only",
            },
            case_results=case_results,
            result_hash=content_hash({"metrics": metrics, "cases": case_results}),
            created_by_user_id=actor.user_id,
        )
        await self._audit(
            actor,
            review_id,
            result.id,
            "AI_OUTCOME_EVALUATION_COMPLETED",
            {
                "case_count": metrics["case_count"],
                "high_risk_error_count": metrics["high_risk_error_count"],
            },
        )
        return result

    async def list_evaluations(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[AIOutcomeEvaluationResultRecord]:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        return await self._repository.list_results(actor.organization_id, review_id)

    async def classify_error(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        evaluation_result_id: UUID,
        case_key: str,
        category: AIOutcomeErrorCategory,
        note: str | None,
    ) -> Any:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        try:
            record = await self._repository.classify_error(
                organization_id=actor.organization_id,
                review_id=review_id,
                evaluation_result_id=evaluation_result_id,
                case_key=case_key,
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
            "AI_OUTCOME_ERROR_CLASSIFIED",
            {
                "evaluation_result_id": str(evaluation_result_id),
                "case_key": case_key,
                "category": category.value,
            },
        )
        return record

    async def _view(
        self, actor: ActorContext, link: AIOutcomeProposalLink, proposal: Any
    ) -> AIOutcomeProposalView:
        stale_reasons = await self._stale_reasons(actor, link)
        await self._repository.record_access(
            organization_id=actor.organization_id,
            review_id=link.review_id,
            proposal_id=link.proposal_id,
            reviewer_user_id=actor.user_id,
            access_type="HUMAN_REVIEW",
            reason="outcome harmonization review",
        )
        return AIOutcomeProposalView(
            link.extraction_value_id,
            link.study_id,
            link.outcome_version_id,
            proposal.id,
            proposal.ai_run_id,
            AIOutcomeReadiness.READY,
            "SUCCEEDED",
            None,
            proposal.structured_value,
            link.validation_results,
            bool(stale_reasons),
            tuple(stale_reasons),
            tuple(link.source_manifest),
            link.selected_chunk_ids,
            len(link.omitted_chunks),
            link.selection_method,
        )

    async def _stale_reasons(self, actor: ActorContext, link: AIOutcomeProposalLink) -> list[str]:
        reasons: list[str] = []
        outcome = await self._outcomes.get_outcome_version(
            actor.organization_id, link.review_id, link.outcome_version_id
        )
        if outcome is None or outcome.content_hash != link.outcome_version_hash:
            reasons.append("OUTCOME_VERSION_CHANGED")
        context = await self._outcomes.extraction_value_context(
            actor.organization_id, link.review_id, link.extraction_value_id
        )
        if (
            context is None
            or content_hash(_context_snapshot(context)) != link.extraction_snapshot_hash
        ):
            reasons.append("EXTRACTION_VALUE_CHANGED")
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
            sources.append(
                ExtractionSource(
                    document,
                    current,
                    FullTextDocumentRole(str(snapshot["document_role"])),
                    tuple(blocks),
                )
            )
        if outcome is not None and len(sources) == len(link.source_manifest):
            prepared = prepare_outcome_input(outcome.definition, sources)
            if prepared.chunk_manifest_hash != link.chunk_manifest_hash:
                reasons.append("CHUNK_MANIFEST_CHANGED")
            if prepared.selected_text_hash != link.selected_text_hash:
                reasons.append("SELECTED_CHUNKS_CHANGED")
        if link.task_definition_version != OUTCOME_TASK.version:
            reasons.append("TASK_DEFINITION_CHANGED")
        return list(dict.fromkeys(reasons))

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
                raise ConflictError("source document is no longer outcome-ready")
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
        await self._provenance.record_audit_event(
            actor,
            review_id=review_id,
            entity_type="ai_outcome",
            entity_id=entity_id,
            action=action,
            before_snapshot=None,
            after_snapshot=snapshot,
            reason=None,
        )


def _uuid_or_zero(value: Any) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return UUID(int=0)


def _uuid_or_none(value: Any) -> UUID | None:
    try:
        return UUID(str(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _context_snapshot(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "study_id": str(context["study_id"]),
        "field_key": context["field_key"],
        "reported_value": context["reported_value"],
        "reported_unit": context["reported_unit"],
        "evidence_location_id": str(context["evidence_location_id"])
        if context.get("evidence_location_id")
        else None,
        "verified": bool(context["verified"]),
    }


def _mapping_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "rationale": str(payload.get("rationale", "")).strip(),
        "confidence": _decimal_or_none(payload.get("confidence")),
        "reported_unit_id": _uuid_or_none(payload.get("reported_unit_id")),
        "normalized_unit_id": _uuid_or_none(payload.get("normalized_unit_id")),
        "reported_time_value": _decimal_or_none(payload.get("reported_time_value")),
        "reported_time_unit": _enum_or_none(TimeUnit, payload.get("reported_time_unit")),
        "reported_time_anchor": _enum_or_none(TimeAnchor, payload.get("reported_time_anchor")),
        "timepoint_window_id": _uuid_or_none(payload.get("timepoint_window_id")),
        "measurement_scale_id": _uuid_or_none(payload.get("measurement_scale_id")),
        "direction_transformation": _enum_or_default(
            DirectionTransformation,
            payload.get("direction_transformation"),
            DirectionTransformation.NONE,
        ),
        "transformation_reason": payload.get("transformation_reason"),
        "supersedes_mapping_id": _uuid_or_none(payload.get("supersedes_mapping_id")),
    }


def _effect_payload(payload: dict[str, Any]) -> dict[str, Any]:
    components = payload.get("components") or {}
    if not isinstance(components, dict):
        raise ConflictError("effect components must be an object")
    normalized_components: dict[str, Decimal] = {}
    for key, value in components.items():
        parsed = _decimal_or_none(value)
        if parsed is None:
            raise ConflictError("effect components must contain numeric values")
        normalized_components[str(key)] = parsed
    source_mapping_ids: list[UUID] = []
    for value in payload.get("source_mapping_ids", []):
        try:
            source_mapping_ids.append(UUID(str(value)))
        except (TypeError, ValueError) as exc:
            raise ConflictError("source mapping identity is invalid") from exc
    return {
        "effect_measure": EffectMeasure(str(payload.get("effect_measure"))),
        "origin": EstimateOrigin.REPORTED,
        "estimate": _decimal_or_none(payload.get("estimate")),
        "standard_error": _decimal_or_none(payload.get("standard_error")),
        "variance": _decimal_or_none(payload.get("variance")),
        "variance_scale": _enum_or_none(VarianceScale, payload.get("variance_scale")),
        "ci_lower": _decimal_or_none(payload.get("ci_lower")),
        "ci_upper": _decimal_or_none(payload.get("ci_upper")),
        "confidence_level": _decimal_or_none(payload.get("confidence_level")),
        "adjustment": _enum_or_default(
            AdjustmentStatus, payload.get("adjustment"), AdjustmentStatus.UNADJUSTED
        ),
        "analysis_population": _enum_or_default(
            AnalysisPopulation, payload.get("analysis_population"), AnalysisPopulation.UNCLEAR
        ),
        "covariates": payload.get("covariates"),
        "model_description": payload.get("model_description"),
        "timepoint_window_id": _uuid_or_none(payload.get("timepoint_window_id")),
        "unit_id": _uuid_or_none(payload.get("unit_id")),
        "measurement_scale_id": _uuid_or_none(payload.get("measurement_scale_id")),
        "components": normalized_components,
        "source_mapping_ids": source_mapping_ids,
        "source_evidence_location_id": _uuid_or_none(payload.get("source_evidence_location_id")),
    }


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise ConflictError("numeric outcome payload is invalid") from exc


def _enum_or_none(enum_type: Any, value: Any) -> Any:
    if value is None or value == "":
        return None
    try:
        return enum_type(str(value))
    except ValueError as exc:
        raise ConflictError("outcome payload enum is invalid") from exc


def _enum_or_default(enum_type: Any, value: Any, default: Any) -> Any:
    return _enum_or_none(enum_type, value) or default


def _unit(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "key": item.key,
        "label": item.label,
        "dimension": item.dimension,
        "context_key": item.context_key,
        "base_unit_key": item.base_unit_key,
        "rule_version": item.rule_version,
    }


def _window(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "key": item.key,
        "label": item.label,
        "anchor": item.anchor.value,
        "minimum_days": item.minimum_days,
        "maximum_days": item.maximum_days,
        "rule_version": item.rule_version,
    }


def _scale(item: Any) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "key": item.key,
        "name": item.name,
        "minimum": item.minimum,
        "maximum": item.maximum,
        "directionality": item.directionality.value,
    }
