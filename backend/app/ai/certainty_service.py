from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from backend.app.ai.certainty_domain import (
    AICertaintyAccessType,
    AICertaintyErrorCategory,
    AICertaintyPolicy,
    AICertaintyProposalLink,
    AICertaintyReadiness,
    AICertaintyReferenceStandard,
    AICertaintyReviewAction,
    certainty_evaluation_metrics,
    certainty_source_manifest,
    prepare_certainty_input,
    validate_certainty_output,
)
from backend.app.ai.certainty_persistence import SqlAlchemyAICertaintyRepository
from backend.app.ai.domain import AITaskType, content_hash
from backend.app.ai.extraction_domain import ExtractionSource
from backend.app.ai.full_text_domain import FullTextDocumentRole
from backend.app.ai.persistence import SqlAlchemyAIRepository
from backend.app.ai.service import AIExecutionService
from backend.app.ai.tasks import CERTAINTY_TASK
from backend.app.certainty.domain import (
    CertaintyAssessment,
    CertaintyAssessmentStatus,
    CertaintyFrameworkVersion,
    assessment_snapshot,
)
from backend.app.certainty.persistence import SqlAlchemyCertaintyRepository
from backend.app.certainty.service import CertaintyService
from backend.app.core.errors import AuthorizationError, ConflictError, ResourceNotFoundError
from backend.app.documents.domain import DocumentStatus
from backend.app.documents.persistence import SqlAlchemyDocumentRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.service import ReviewService
from backend.app.studies.persistence import SqlAlchemyStudyRepository


@dataclass(frozen=True, slots=True)
class AICertaintyReadinessView:
    assessment_id: UUID
    outcome_version_id: UUID | None
    framework_version_id: UUID | None
    state: AICertaintyReadiness
    reason: str | None


@dataclass(frozen=True, slots=True)
class AICertaintyProposalView:
    assessment_id: UUID
    outcome_version_id: UUID
    framework_version_id: UUID
    proposal_id: UUID | None
    ai_run_id: UUID | None
    readiness: AICertaintyReadiness
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


class AICertaintyService:
    """Evidence-grounded certainty drafting; CertaintyService remains canonical."""

    def __init__(
        self,
        repository: SqlAlchemyAICertaintyRepository,
        ai_repository: SqlAlchemyAIRepository,
        certainty_repository: SqlAlchemyCertaintyRepository,
        documents: SqlAlchemyDocumentRepository,
        studies: SqlAlchemyStudyRepository,
        reviews: ReviewService,
        provenance: ProvenanceService,
        execution: AIExecutionService,
        certainty_service: CertaintyService,
    ) -> None:
        self._repository = repository
        self._ai = ai_repository
        self._certainty_repository = certainty_repository
        self._documents = documents
        self._studies = studies
        self._reviews = reviews
        self._provenance = provenance
        self._execution = execution
        self._certainty_service = certainty_service

    async def create_policy(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        maximum_batch_size: int,
    ) -> AICertaintyPolicy:
        AuthorizationService.require(actor, Permission.MANAGE_AI)
        await self._reviews.get(actor, review_id)
        if not 1 <= maximum_batch_size <= 100:
            raise ConflictError("maximum batch size must be from 1 through 100")
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
            "AI_CERTAINTY_POLICY_CREATED",
            {"maximum_batch_size": maximum_batch_size},
        )
        return policy

    async def readiness(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assessment_id: UUID,
        documents: list[dict[str, Any]],
    ) -> AICertaintyReadinessView:
        AuthorizationService.require(actor, Permission.ASSESS_CERTAINTY)
        await self._reviews.get(actor, review_id)
        assessment = await self._certainty_repository.get_assessment(
            actor.organization_id, review_id, assessment_id
        )
        if assessment is None:
            return AICertaintyReadinessView(
                assessment_id,
                None,
                None,
                AICertaintyReadiness.BLOCKED_NO_ASSESSMENT,
                "certainty assessment was not found",
            )
        if assessment.assessor_user_id != actor.user_id:
            return AICertaintyReadinessView(
                assessment_id,
                assessment.outcome_version_id,
                assessment.framework_version_id,
                AICertaintyReadiness.BLOCKED_NOT_OWNER,
                "certainty assistance is assignment-scoped to the assessor",
            )
        if assessment.status is not CertaintyAssessmentStatus.IN_PROGRESS:
            return AICertaintyReadinessView(
                assessment_id,
                assessment.outcome_version_id,
                assessment.framework_version_id,
                AICertaintyReadiness.BLOCKED_SUBMITTED,
                "new assistance is not generated for a submitted assessment",
            )
        framework = await self._certainty_repository.get_framework_version(
            actor.organization_id, review_id, assessment.framework_version_id
        )
        if framework is None:
            return AICertaintyReadinessView(
                assessment_id,
                assessment.outcome_version_id,
                None,
                AICertaintyReadiness.BLOCKED_FRAMEWORK,
                "the pinned certainty framework version was not found",
            )
        if not documents or len(documents) > 8:
            return AICertaintyReadinessView(
                assessment_id,
                assessment.outcome_version_id,
                framework.id,
                AICertaintyReadiness.BLOCKED_SOURCE_SCOPE,
                "one through eight explicit source documents are required",
            )
        try:
            profile = await self._certainty_service.evidence_profile(
                actor, review_id=review_id, assessment_id=assessment_id
            )
        except (ConflictError, ResourceNotFoundError) as exc:
            return AICertaintyReadinessView(
                assessment_id,
                assessment.outcome_version_id,
                framework.id,
                AICertaintyReadiness.BLOCKED_OTHER,
                str(exc),
            )
        study_ids = {str(value) for value in profile.get("study_ids", [])}
        if not study_ids:
            return AICertaintyReadinessView(
                assessment_id,
                assessment.outcome_version_id,
                framework.id,
                AICertaintyReadiness.BLOCKED_SOURCE_SCOPE,
                "certainty evidence profile contains no included Study identities",
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
                return AICertaintyReadinessView(
                    assessment_id,
                    assessment.outcome_version_id,
                    framework.id,
                    AICertaintyReadiness.BLOCKED_SOURCE_SCOPE,
                    "source document identity or role is invalid",
                )
            if document_id in seen:
                return AICertaintyReadinessView(
                    assessment_id,
                    assessment.outcome_version_id,
                    framework.id,
                    AICertaintyReadiness.BLOCKED_SOURCE_SCOPE,
                    "source documents must be unique",
                )
            seen.add(document_id)
            document = await self._documents.get_document(actor.organization_id, document_id)
            if document is None or document.review_id != review_id:
                return AICertaintyReadinessView(
                    assessment_id,
                    assessment.outcome_version_id,
                    framework.id,
                    AICertaintyReadiness.BLOCKED_SOURCE_SCOPE,
                    "source document was not found in this review",
                )
            article_linked = False
            for study_id in study_ids:
                if await self._studies.article_linked(
                    actor.organization_id, review_id, UUID(study_id), document.article_id
                ):
                    article_linked = True
                    break
            if not article_linked:
                return AICertaintyReadinessView(
                    assessment_id,
                    assessment.outcome_version_id,
                    framework.id,
                    AICertaintyReadiness.BLOCKED_SOURCE_SCOPE,
                    "every source Article must belong to an included Study",
                )
            if document.status is not DocumentStatus.PROCESSED:
                return AICertaintyReadinessView(
                    assessment_id,
                    assessment.outcome_version_id,
                    framework.id,
                    AICertaintyReadiness.BLOCKED_DOCUMENT_PROCESSING,
                    f"document {document.id} is not processed",
                )
            processing = await self._documents.latest_successful_processing_run(
                actor.organization_id, review_id, document.id
            )
            if processing is None:
                return AICertaintyReadinessView(
                    assessment_id,
                    assessment.outcome_version_id,
                    framework.id,
                    AICertaintyReadiness.BLOCKED_DOCUMENT_PROCESSING,
                    f"document {document.id} has no successful parser run",
                )
            blocks = await self._documents.list_blocks(
                actor.organization_id, review_id, document.id
            )
            if not any(block.text.strip() for block in blocks):
                return AICertaintyReadinessView(
                    assessment_id,
                    assessment.outcome_version_id,
                    framework.id,
                    AICertaintyReadiness.BLOCKED_NO_PARSED_TEXT,
                    f"document {document.id} has no parsed scientific text",
                )
        return AICertaintyReadinessView(
            assessment_id,
            assessment.outcome_version_id,
            framework.id,
            AICertaintyReadiness.READY,
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
    ) -> list[AICertaintyProposalView]:
        if not actor.has_permission(Permission.ASSESS_CERTAINTY):
            raise AuthorizationError("the current role cannot request certainty assistance")
        await self._reviews.get(actor, review_id)
        policy = await self._repository.current_policy(actor.organization_id, review_id)
        if policy is None:
            raise ConflictError("AI certainty assistance is not configured for this review")
        if not requests or len(requests) > policy.maximum_batch_size:
            raise ConflictError("the certainty batch is empty or exceeds the active policy")
        assessment_ids = [str(item.get("assessment_id")) for item in requests]
        if len(assessment_ids) != len(set(assessment_ids)):
            raise ConflictError("certainty assistance requests must be unique")
        results: list[AICertaintyProposalView] = []
        for request in requests:
            assessment_id = _uuid_or_zero(request.get("assessment_id"))
            try:
                results.append(
                    await self._create_one(
                        actor,
                        review_id=review_id,
                        assessment_id=assessment_id,
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
                    AICertaintyProposalView(
                        assessment_id,
                        UUID(int=0),
                        UUID(int=0),
                        None,
                        None,
                        AICertaintyReadiness.BLOCKED_OTHER,
                        "FAILED",
                        str(exc),
                        None,
                        None,
                        False,
                        (),
                        (),
                        (),
                        0,
                        "certainty-domain-aware-bounded-v1",
                    )
                )
        return results

    async def _create_one(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assessment_id: UUID,
        documents: list[dict[str, Any]],
        model_version_id: UUID | None,
        prompt_version_id: UUID | None,
        maximum_attempts: int,
        timeout_seconds: int,
        per_run_token_ceiling: int | None,
    ) -> AICertaintyProposalView:
        ready = await self.readiness(
            actor,
            review_id=review_id,
            assessment_id=assessment_id,
            documents=documents,
        )
        if ready.state is not AICertaintyReadiness.READY:
            return AICertaintyProposalView(
                assessment_id,
                ready.outcome_version_id or UUID(int=0),
                ready.framework_version_id or UUID(int=0),
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
                "certainty-domain-aware-bounded-v1",
            )
        assessment, framework, profile = await self._context(
            actor, review_id=review_id, assessment_id=assessment_id
        )
        sources = await self._load_sources(actor, review_id, documents)
        prepared = prepare_certainty_input(framework.definition, sources)
        if not prepared.chunks:
            raise ConflictError("the source set contains no AI-consumable parsed text")
        source_rows = certainty_source_manifest(sources)
        assessment_snapshot_value = assessment_snapshot(assessment)
        input_data: dict[str, Any] = {
            "review_id": str(review_id),
            "assessment_id": str(assessment.id),
            "outcome_version_id": str(assessment.outcome_version_id),
            "timepoint_window_id": (
                str(assessment.timepoint_window_id) if assessment.timepoint_window_id else None
            ),
            "framework_version_id": str(framework.id),
            "framework_definition": framework.definition,
            "assessment_snapshot": assessment_snapshot_value,
            "evidence_profile": profile,
            "included_studies": list(profile.get("study_ids", [])),
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
                {"type": "certainty_assessment", "id": str(assessment.id)},
                {"type": "certainty_framework_version", "id": str(framework.id)},
                {"type": "outcome_definition_version", "id": str(assessment.outcome_version_id)},
                *[
                    {"type": "document_processing_run", "id": str(source.processing.id)}
                    for source in sources
                ],
            ],
        }
        ai_run, proposal = await self._execution.create_and_execute(
            actor,
            review_id=review_id,
            task_type=AITaskType.CERTAINTY_SUGGESTION,
            input_data=input_data,
            model_version_id=model_version_id,
            prompt_version_id=prompt_version_id,
            maximum_attempts=maximum_attempts,
            timeout_seconds=timeout_seconds,
            per_run_token_ceiling=per_run_token_ceiling,
            target_type="CERTAINTY_ASSESSMENT",
            target_id=assessment.id,
        )
        if proposal is None:
            return AICertaintyProposalView(
                assessment.id,
                assessment.outcome_version_id,
                framework.id,
                None,
                ai_run.id,
                AICertaintyReadiness.READY,
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
        validation_errors = validate_certainty_output(proposal.structured_value, input_data)
        link = await self._repository.create_link(
            organization_id=actor.organization_id,
            review_id=review_id,
            proposal_id=proposal.id,
            ai_run_id=ai_run.id,
            assessment_id=assessment.id,
            outcome_version_id=assessment.outcome_version_id,
            outcome_version_hash=profile["outcome"]["content_hash"],
            framework_version_id=framework.id,
            framework_version_hash=framework.content_hash,
            assessment_snapshot_hash=content_hash(assessment_snapshot_value),
            evidence_profile_hash=content_hash(profile),
            task_definition_version=CERTAINTY_TASK.version,
            source_manifest=source_rows,
            selected_chunk_ids=list(prepared.selected_chunk_ids),
            omitted_chunks=list(prepared.omitted_chunks),
            selection_method=prepared.selection_method,
            chunk_manifest_hash=prepared.chunk_manifest_hash,
            selected_text_hash=prepared.selected_text_hash,
            validation_results={
                "aggregate_valid": not validation_errors,
                "errors": validation_errors,
                "validator_version": "ai-certainty-validator-1",
            },
        )
        await self._audit(
            actor,
            review_id,
            link.id,
            "AI_CERTAINTY_PROPOSAL_LINKED",
            {
                "proposal_id": str(proposal.id),
                "assessment_id": str(assessment.id),
                "framework_version_hash": framework.content_hash,
                "evidence_profile_hash": link.evidence_profile_hash,
            },
        )
        return await self._view(actor, link, proposal)

    async def get_proposal(
        self, actor: ActorContext, *, review_id: UUID, proposal_id: UUID
    ) -> AICertaintyProposalView:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        link = await self._repository.get_link(actor.organization_id, review_id, proposal_id)
        proposal = await self._ai.get_proposal(actor.organization_id, review_id, proposal_id)
        if link is None or proposal is None:
            raise ResourceNotFoundError("AI certainty proposal was not found")
        return await self._view(actor, link, proposal)

    async def list_proposals(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[AICertaintyProposalView]:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        result: list[AICertaintyProposalView] = []
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
        action: AICertaintyReviewAction,
        canonical_action: str | None,
        human_payload: dict[str, Any] | None,
        reason: str | None,
    ) -> dict[str, Any]:
        AuthorizationService.require(actor, Permission.ASSESS_CERTAINTY)
        await self._reviews.get(actor, review_id)
        link = await self._repository.get_link(actor.organization_id, review_id, proposal_id)
        proposal = await self._ai.get_proposal(actor.organization_id, review_id, proposal_id)
        if link is None or proposal is None:
            raise ResourceNotFoundError("AI certainty proposal was not found")
        stale_reasons = await self._stale_reasons(actor, link)
        if action in {AICertaintyReviewAction.ACCEPTED, AICertaintyReviewAction.EDITED}:
            if stale_reasons:
                raise ConflictError("stale certainty proposals cannot be accepted")
            if not canonical_action or human_payload is None:
                raise ConflictError("human acceptance requires an explicit domain payload")
            if canonical_action != "SAVE_DOMAIN_JUDGMENTS":
                raise ConflictError("certainty canonical action is not supported")
            if action is AICertaintyReviewAction.ACCEPTED and not link.validation_results.get(
                "aggregate_valid", False
            ):
                raise ConflictError("invalid AI proposals require an explicit EDITED disposition")
            if action is AICertaintyReviewAction.ACCEPTED:
                self._require_matching_candidate(proposal.structured_value, human_payload)
            updated = await self._apply_human_domains(
                actor,
                review_id=review_id,
                assessment_id=link.assessment_id,
                payload=human_payload,
                proposal_id=proposal_id,
                ai_run_id=link.ai_run_id,
            )
            canonical_subject_id = link.assessment_id
        else:
            canonical_action = None
            canonical_subject_id = None
            updated = None
        review = await self._repository.record_review(
            organization_id=actor.organization_id,
            review_id=review_id,
            proposal_id=proposal_id,
            assessment_id=link.assessment_id,
            action=action.value,
            canonical_action=canonical_action,
            canonical_subject_id=canonical_subject_id,
            ai_candidate_snapshot=proposal.structured_value,
            human_payload_snapshot=human_payload,
            reason=reason.strip() if reason else None,
            reviewer_user_id=actor.user_id,
        )
        await self._audit(
            actor,
            review_id,
            review.id,
            "AI_CERTAINTY_PROPOSAL_REVIEWED",
            {
                "proposal_id": str(proposal_id),
                "assessment_id": str(link.assessment_id),
                "action": action.value,
                "canonical_action": canonical_action,
                "canonical_subject_id": str(canonical_subject_id) if canonical_subject_id else None,
                "domain_write_count": len(updated or []),
            },
        )
        return {
            "id": review.id,
            "proposal_id": proposal_id,
            "assessment_id": link.assessment_id,
            "action": action.value,
            "canonical_action": canonical_action,
            "canonical_subject_id": canonical_subject_id,
        }

    async def create_dataset(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        logical_key: str,
        name: str,
        reference_standard: AICertaintyReferenceStandard,
        cases: list[dict[str, Any]],
    ) -> Any:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        if not cases or len(cases) > 100_000:
            raise ConflictError("certainty evaluation dataset requires at least one case")
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
        await self._audit(actor, review_id, dataset.id, "AI_CERTAINTY_DATASET_CREATED", payload)
        return dataset

    async def list_datasets(self, actor: ActorContext, *, review_id: UUID) -> list[Any]:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        return await self._repository.list_datasets(actor.organization_id, review_id)

    async def evaluate_dataset(
        self, actor: ActorContext, *, review_id: UUID, dataset_id: UUID
    ) -> Any:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        dataset = await self._repository.get_dataset(actor.organization_id, review_id, dataset_id)
        if dataset is None:
            raise ResourceNotFoundError("AI certainty evaluation dataset was not found")
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
            reference = case.get("reference_domain_suggestions")
            candidate_domains = candidate.get("domain_suggestions") if candidate else None
            case_results.append(
                {
                    "case_key": case.get("case_key"),
                    "proposal_id": proposal_id,
                    "validation_valid": bool(
                        link and link.validation_results.get("aggregate_valid")
                    ),
                    "reference_type": case.get("reference_type"),
                    "reference_match": bool(
                        reference is not None and candidate_domains == reference
                    ),
                    "error_categories": list(case.get("error_categories", [])),
                    "abstention": bool(candidate and candidate.get("abstention")),
                }
            )
        metrics = certainty_evaluation_metrics(case_results)
        result = await self._repository.create_result(
            organization_id=actor.organization_id,
            review_id=review_id,
            dataset_id=dataset.id,
            metrics=metrics,
            dimensions={
                "reference_standard": dataset.reference_standard,
                "task_definition_version": CERTAINTY_TASK.version,
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
            "AI_CERTAINTY_EVALUATION_COMPLETED",
            {
                "case_count": metrics["case_count"],
                "high_risk_error_count": metrics["high_risk_error_count"],
            },
        )
        return result

    async def list_evaluations(self, actor: ActorContext, *, review_id: UUID) -> list[Any]:
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
        category: AICertaintyErrorCategory,
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
            "AI_CERTAINTY_ERROR_CLASSIFIED",
            {
                "evaluation_result_id": str(evaluation_result_id),
                "case_key": case_key,
                "category": category.value,
            },
        )
        return record

    async def _context(
        self, actor: ActorContext, *, review_id: UUID, assessment_id: UUID
    ) -> tuple[CertaintyAssessment, CertaintyFrameworkVersion, dict[str, Any]]:
        assessment = await self._certainty_repository.get_assessment(
            actor.organization_id, review_id, assessment_id
        )
        if assessment is None:
            raise ResourceNotFoundError("certainty assessment was not found")
        framework = await self._certainty_repository.get_framework_version(
            actor.organization_id, review_id, assessment.framework_version_id
        )
        if framework is None:
            raise ResourceNotFoundError("certainty framework version was not found")
        profile = await self._certainty_service.evidence_profile(
            actor, review_id=review_id, assessment_id=assessment_id
        )
        return assessment, framework, profile

    async def _view(
        self, actor: ActorContext, link: AICertaintyProposalLink, proposal: Any
    ) -> AICertaintyProposalView:
        stale_reasons = await self._stale_reasons(actor, link)
        await self._repository.record_access(
            organization_id=actor.organization_id,
            review_id=link.review_id,
            proposal_id=link.proposal_id,
            reviewer_user_id=actor.user_id,
            access_type=AICertaintyAccessType.HUMAN_REVIEW.value,
            reason="certainty-of-evidence assistance review",
        )
        return AICertaintyProposalView(
            link.assessment_id,
            link.outcome_version_id,
            link.framework_version_id,
            proposal.id,
            proposal.ai_run_id,
            AICertaintyReadiness.READY,
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

    async def _stale_reasons(self, actor: ActorContext, link: AICertaintyProposalLink) -> list[str]:
        reasons: list[str] = []
        assessment = await self._certainty_repository.get_assessment(
            actor.organization_id, link.review_id, link.assessment_id
        )
        if assessment is None:
            return ["ASSESSMENT_MISSING"]
        if content_hash(assessment_snapshot(assessment)) != link.assessment_snapshot_hash:
            reasons.append("ASSESSMENT_CHANGED")
        framework = await self._certainty_repository.get_framework_version(
            actor.organization_id, link.review_id, link.framework_version_id
        )
        if framework is None or framework.content_hash != link.framework_version_hash:
            reasons.append("FRAMEWORK_VERSION_CHANGED")
        try:
            profile = await self._certainty_service.evidence_profile(
                actor, review_id=link.review_id, assessment_id=link.assessment_id
            )
        except (ConflictError, ResourceNotFoundError):
            profile = None
        if profile is None or content_hash(profile) != link.evidence_profile_hash:
            reasons.append("EVIDENCE_PROFILE_CHANGED")
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
        if framework is not None and len(sources) == len(link.source_manifest):
            prepared = prepare_certainty_input(framework.definition, sources)
            if prepared.chunk_manifest_hash != link.chunk_manifest_hash:
                reasons.append("CHUNK_MANIFEST_CHANGED")
            if prepared.selected_text_hash != link.selected_text_hash:
                reasons.append("SELECTED_CHUNKS_CHANGED")
        if link.task_definition_version != CERTAINTY_TASK.version:
            reasons.append("TASK_DEFINITION_CHANGED")
        return list(dict.fromkeys(reasons))

    async def _load_sources(
        self, actor: ActorContext, review_id: UUID, requested: list[dict[str, Any]]
    ) -> list[ExtractionSource]:
        sources: list[ExtractionSource] = []
        for item in requested:
            document_id = UUID(str(item["document_id"]))
            document = await self._documents.get_document(actor.organization_id, document_id)
            if document is None or document.review_id != review_id:
                raise ConflictError("source document is no longer certainty-ready")
            processing = await self._documents.latest_successful_processing_run(
                actor.organization_id, review_id, document_id
            )
            blocks = await self._documents.list_blocks(
                actor.organization_id, review_id, document_id
            )
            if processing is None:
                raise ConflictError("source document is no longer certainty-ready")
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

    async def _apply_human_domains(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assessment_id: UUID,
        payload: dict[str, Any],
        proposal_id: UUID,
        ai_run_id: UUID,
    ) -> list[Any]:
        allowed_payload = {"domains"}
        if set(payload) - allowed_payload:
            raise ConflictError("human certainty payload contains unsupported fields")
        domains = payload.get("domains")
        if not isinstance(domains, list) or not domains:
            raise ConflictError("human certainty payload requires explicit domain judgments")
        if len(domains) > 50:
            raise ConflictError("human certainty payload contains too many domains")
        updated: list[Any] = []
        seen: set[str] = set()
        for item in domains:
            if not isinstance(item, dict):
                raise ConflictError("human certainty domain payload must be an object")
            allowed = {"domain_key", "judgment", "rationale", "evidence_location_id", "evidence"}
            if set(item) - allowed:
                raise ConflictError("human certainty domain payload contains unsupported fields")
            key = str(item.get("domain_key", "")).strip().upper()
            if not key or key in seen:
                raise ConflictError("human certainty domain keys must be present and unique")
            seen.add(key)
            evidence_location_id = _uuid_or_none(item.get("evidence_location_id"))
            evidence_value = item.get("evidence")
            if not isinstance(evidence_value, dict):
                evidence_value = {}
            result = await self._certainty_service.save_domain(
                actor,
                review_id=review_id,
                assessment_id=assessment_id,
                domain_key=key,
                judgment=str(item.get("judgment", "")),
                rationale=str(item.get("rationale", "")),
                evidence_location_id=evidence_location_id,
                evidence=evidence_value,
            )
            updated.append(result)
            domain = next(domain for domain in result.domain_judgments if domain.domain_key == key)
            await self._provenance.record_provenance(
                actor,
                review_id=review_id,
                subject_type="certainty_domain_judgment",
                subject_id=domain.id,
                source_type="AI_PROPOSAL",
                source_id=proposal_id,
                source_locator={"ai_run_id": str(ai_run_id), "assessment_id": str(assessment_id)},
                method_name="human-accepted-ai-certainty-proposal",
                method_version="1",
                actor_kind=ProvenanceActorKind.HUMAN,
                ai_run_id=None,
                confidence=None,
                verification_state=VerificationState.HUMAN_VERIFIED,
            )
        return updated

    @staticmethod
    def _require_matching_candidate(candidate: dict[str, Any], payload: dict[str, Any]) -> None:
        suggestions = candidate.get("domain_suggestions") if isinstance(candidate, dict) else None
        domains = payload.get("domains") if isinstance(payload, dict) else None
        if not isinstance(suggestions, list) or not isinstance(domains, list) or not suggestions:
            raise ConflictError("accepted certainty proposals require a non-abstaining candidate")
        ai_values = {
            str(item.get("domain_key")): (item.get("judgment"), item.get("magnitude"))
            for item in suggestions
            if isinstance(item, dict)
        }
        human_values = {
            str(item.get("domain_key", "")).strip().upper(): (item.get("judgment"), None)
            for item in domains
            if isinstance(item, dict)
        }
        if set(ai_values) != set(human_values) or any(
            ai_values[key][0] != human_values[key][0] for key in ai_values
        ):
            raise ConflictError("accepted certainty payload must match the validated AI candidate")

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
            entity_type="ai_certainty",
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
        return UUID(str(value)) if value else None
    except (TypeError, ValueError):
        return None
