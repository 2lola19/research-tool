from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from backend.app.ai.domain import AITaskType, content_hash
from backend.app.ai.extraction_domain import ExtractionSource
from backend.app.ai.full_text_domain import FullTextDocumentRole
from backend.app.ai.persistence import SqlAlchemyAIRepository
from backend.app.ai.rob_domain import (
    AIRobAccessType,
    AIRobAnswerStatus,
    AIRobErrorCategory,
    AIRobEvaluationDataset,
    AIRobMatchClass,
    AIRobPolicy,
    AIRobProposalLink,
    AIRobReadiness,
    AIRobReferenceStandard,
    AIRobReviewAction,
    aggregate_rob_metrics,
    evaluate_rob_case,
    prepare_rob_input,
    question_definitions,
    source_manifest,
    validate_rob_output,
)
from backend.app.ai.rob_persistence import (
    AIRobEvaluationCaseResultRecord,
    AIRobEvaluationResultRecord,
    SqlAlchemyAIRobRepository,
)
from backend.app.ai.screening_domain import AIScreeningMode
from backend.app.ai.service import AIExecutionService
from backend.app.ai.tasks import ROB_TASK
from backend.app.core.errors import AuthorizationError, ConflictError, ResourceNotFoundError
from backend.app.documents.domain import DocumentStatus
from backend.app.documents.persistence import SqlAlchemyDocumentRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.service import ReviewService
from backend.app.risk_of_bias.domain import AssessmentStatus
from backend.app.risk_of_bias.persistence import SqlAlchemyRiskOfBiasRepository
from backend.app.risk_of_bias.service import RiskOfBiasService
from backend.app.studies.persistence import SqlAlchemyStudyRepository


@dataclass(frozen=True, slots=True)
class AIRobReadinessView:
    assessment_id: UUID
    study_id: UUID | None
    instrument_version_id: UUID | None
    state: AIRobReadiness
    reason: str | None


@dataclass(frozen=True, slots=True)
class AIRobProposalView:
    assessment_id: UUID
    study_id: UUID
    instrument_version_id: UUID
    proposal_id: UUID | None
    ai_run_id: UUID | None
    mode: AIScreeningMode
    readiness: AIRobReadiness
    status: str
    failure_reason: str | None
    is_revealed: bool
    structured_value: dict[str, Any] | None
    validation_results: dict[str, Any] | None
    domain_suggestions: dict[str, str | None] | None
    overall_suggestion: str | None
    stale: bool
    stale_reasons: tuple[str, ...]
    source_manifest: tuple[dict[str, Any], ...]
    selected_chunk_ids: tuple[str, ...]
    omitted_chunk_count: int
    selection_method: str


class AIRiskOfBiasService:
    """Evidence-grounded RoB advice; canonical assessments remain human-owned."""

    def __init__(
        self,
        repository: SqlAlchemyAIRobRepository,
        ai_repository: SqlAlchemyAIRepository,
        rob_repository: SqlAlchemyRiskOfBiasRepository,
        documents: SqlAlchemyDocumentRepository,
        studies: SqlAlchemyStudyRepository,
        reviews: ReviewService,
        provenance: ProvenanceService,
        execution: AIExecutionService,
        rob_service: RiskOfBiasService,
    ) -> None:
        self._repository = repository
        self._ai = ai_repository
        self._rob = rob_repository
        self._documents = documents
        self._studies = studies
        self._reviews = reviews
        self._provenance = provenance
        self._execution = execution
        self._rob_service = rob_service

    async def create_policy(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        mode: AIScreeningMode,
        maximum_batch_size: int,
    ) -> AIRobPolicy:
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
            "AI_ROB_POLICY_CREATED",
            {"mode": mode.value, "maximum_batch_size": maximum_batch_size},
        )
        return policy

    async def readiness(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assessment_id: UUID,
        documents: list[dict[str, Any]],
    ) -> AIRobReadinessView:
        await self._reviews.get(actor, review_id)
        assessment = await self._rob.get_assessment(actor.organization_id, review_id, assessment_id)
        if assessment is None:
            return AIRobReadinessView(
                assessment_id,
                None,
                None,
                AIRobReadiness.BLOCKED_NO_ASSESSMENT,
                "assessment was not found",
            )
        if assessment.assessor_user_id != actor.user_id:
            return AIRobReadinessView(
                assessment_id,
                assessment.study_id,
                assessment.instrument_version_id,
                AIRobReadiness.BLOCKED_NOT_OWNER,
                "the assessment is not assigned to the current reviewer",
            )
        if assessment.status is AssessmentStatus.SUBMITTED:
            return AIRobReadinessView(
                assessment_id,
                assessment.study_id,
                assessment.instrument_version_id,
                AIRobReadiness.BLOCKED_SUBMITTED,
                "new assistance is not generated for a submitted assessment",
            )
        version = await self._rob.get_version(
            actor.organization_id, review_id, assessment.instrument_version_id
        )
        if version is None:
            return AIRobReadinessView(
                assessment_id,
                assessment.study_id,
                None,
                AIRobReadiness.BLOCKED_NO_INSTRUMENT,
                "the pinned instrument version was not found",
            )
        if version.decision is None or version.decision.value != "APPROVED":
            return AIRobReadinessView(
                assessment_id,
                assessment.study_id,
                version.id,
                AIRobReadiness.BLOCKED_INSTRUMENT_NOT_APPROVED,
                "only an approved instrument version may receive assistance",
            )
        if not documents or len(documents) > 8:
            return AIRobReadinessView(
                assessment_id,
                assessment.study_id,
                version.id,
                AIRobReadiness.BLOCKED_SOURCE_SCOPE,
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
                return AIRobReadinessView(
                    assessment_id,
                    assessment.study_id,
                    version.id,
                    AIRobReadiness.BLOCKED_SOURCE_SCOPE,
                    "source document identity or role is invalid",
                )
            if document_id in seen:
                return AIRobReadinessView(
                    assessment_id,
                    assessment.study_id,
                    version.id,
                    AIRobReadiness.BLOCKED_SOURCE_SCOPE,
                    "source documents must be unique",
                )
            seen.add(document_id)
            document = await self._documents.get_document(actor.organization_id, document_id)
            if document is None or document.review_id != review_id:
                return AIRobReadinessView(
                    assessment_id,
                    assessment.study_id,
                    version.id,
                    AIRobReadiness.BLOCKED_SOURCE_SCOPE,
                    "a source document was not found in this review",
                )
            if not await self._studies.article_linked(
                actor.organization_id, review_id, assessment.study_id, document.article_id
            ):
                return AIRobReadinessView(
                    assessment_id,
                    assessment.study_id,
                    version.id,
                    AIRobReadiness.BLOCKED_SOURCE_SCOPE,
                    "every source Article must be in the assessment Study Family",
                )
            if document.status is not DocumentStatus.PROCESSED:
                return AIRobReadinessView(
                    assessment_id,
                    assessment.study_id,
                    version.id,
                    AIRobReadiness.BLOCKED_DOCUMENT_PROCESSING,
                    f"document {document.id} is not processed",
                )
            processing = await self._documents.latest_successful_processing_run(
                actor.organization_id, review_id, document.id
            )
            if processing is None:
                return AIRobReadinessView(
                    assessment_id,
                    assessment.study_id,
                    version.id,
                    AIRobReadiness.BLOCKED_DOCUMENT_PROCESSING,
                    f"document {document.id} has no successful parser run",
                )
            blocks = await self._documents.list_blocks(
                actor.organization_id, review_id, document.id
            )
            if not any(block.text.strip() for block in blocks):
                return AIRobReadinessView(
                    assessment_id,
                    assessment.study_id,
                    version.id,
                    AIRobReadiness.BLOCKED_NO_PARSED_TEXT,
                    f"document {document.id} has no parsed scientific text",
                )
        return AIRobReadinessView(
            assessment_id, assessment.study_id, version.id, AIRobReadiness.READY, None
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
    ) -> list[AIRobProposalView]:
        if not actor.has_permission(Permission.PERFORM_ROB_ASSESSMENT):
            raise AuthorizationError("the current role cannot request Risk of Bias assistance")
        await self._reviews.get(actor, review_id)
        policy = await self._repository.current_policy(actor.organization_id, review_id)
        if policy is None or policy.mode is AIScreeningMode.OFF:
            raise ConflictError("Risk of Bias assistance is disabled for this review")
        if not requests or len(requests) > policy.maximum_batch_size:
            raise ConflictError("the Risk of Bias batch is empty or exceeds the active policy")
        ids = [str(item.get("assessment_id")) for item in requests]
        if len(ids) != len(set(ids)):
            raise ConflictError("Risk of Bias assessment requests must be unique")
        result: list[AIRobProposalView] = []
        for request in requests:
            assessment_id = _uuid_or_none(request.get("assessment_id"))
            try:
                if assessment_id is None:
                    raise ValueError("assessment_id is required")
                result.append(
                    await self._create_one(
                        actor,
                        review_id=review_id,
                        assessment_id=assessment_id,
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
                result.append(
                    AIRobProposalView(
                        assessment_id=assessment_id or UUID(int=0),
                        study_id=UUID(int=0),
                        instrument_version_id=UUID(int=0),
                        proposal_id=None,
                        ai_run_id=None,
                        mode=policy.mode,
                        readiness=AIRobReadiness.BLOCKED_OTHER,
                        status="FAILED",
                        failure_reason=str(exc),
                        is_revealed=False,
                        structured_value=None,
                        validation_results=None,
                        domain_suggestions=None,
                        overall_suggestion=None,
                        stale=False,
                        stale_reasons=(),
                        source_manifest=(),
                        selected_chunk_ids=(),
                        omitted_chunk_count=0,
                        selection_method="question-aware-rob-bounded-v1",
                    )
                )
        return result

    async def _create_one(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assessment_id: UUID,
        documents: list[dict[str, Any]],
        mode: AIScreeningMode,
        model_version_id: UUID | None,
        prompt_version_id: UUID | None,
        maximum_attempts: int,
        timeout_seconds: int,
        per_run_token_ceiling: int | None,
    ) -> AIRobProposalView:
        ready = await self.readiness(
            actor,
            review_id=review_id,
            assessment_id=assessment_id,
            documents=documents,
        )
        assessment = await self._assessment(actor, review_id, assessment_id)
        if ready.state is not AIRobReadiness.READY:
            return AIRobProposalView(
                assessment_id=assessment_id,
                study_id=assessment.study_id,
                instrument_version_id=ready.instrument_version_id
                or assessment.instrument_version_id,
                proposal_id=None,
                ai_run_id=None,
                mode=mode,
                readiness=ready.state,
                status="BLOCKED",
                failure_reason=ready.reason,
                is_revealed=False,
                structured_value=None,
                validation_results=None,
                domain_suggestions=None,
                overall_suggestion=None,
                stale=False,
                stale_reasons=(),
                source_manifest=(),
                selected_chunk_ids=(),
                omitted_chunk_count=0,
                selection_method="question-aware-rob-bounded-v1",
            )
        version = await self._rob.get_version(
            actor.organization_id, review_id, assessment.instrument_version_id
        )
        if version is None:
            raise ResourceNotFoundError("Risk of Bias instrument version was not found")
        sources = await self._load_sources(actor, review_id, documents, assessment.study_id)
        prepared = prepare_rob_input(version.definition, sources)
        if not prepared.chunks:
            raise ConflictError("the source set contains no AI-consumable parsed text")
        manifests = [source_manifest(source) for source in sources]
        input_data = {
            "review_id": str(review_id),
            "assessment_id": str(assessment.id),
            "study_id": str(assessment.study_id),
            "instrument_version_id": str(version.id),
            "instrument_definition": version.definition,
            "questions": question_definitions(version.definition),
            "source_documents": manifests,
            "chunks": list(prepared.chunks),
            "input_preparation": {
                "method": prepared.selection_method,
                "candidate_chunk_ids": [str(item["chunk_id"]) for item in prepared.chunks]
                + [str(item["chunk_id"]) for item in prepared.omitted_chunks],
                "selected_chunk_ids": list(prepared.selected_chunk_ids),
                "omitted_chunks": list(prepared.omitted_chunks),
                "chunk_manifest_hash": prepared.chunk_manifest_hash,
                "selected_text_hash": prepared.selected_text_hash,
            },
            "references": [
                {"type": "rob_assessment", "id": str(assessment.id)},
                {"type": "rob_instrument_version", "id": str(version.id)},
                {"type": "study", "id": str(assessment.study_id)},
                *[
                    {"type": "document_processing_run", "id": str(source.processing.id)}
                    for source in sources
                ],
            ],
        }
        run, proposal = await self._execution.create_and_execute(
            actor,
            review_id=review_id,
            task_type=AITaskType.ROB_SUGGESTION,
            input_data=input_data,
            model_version_id=model_version_id,
            prompt_version_id=prompt_version_id,
            maximum_attempts=maximum_attempts,
            timeout_seconds=timeout_seconds,
            per_run_token_ceiling=per_run_token_ceiling,
            target_type="ROB_ASSESSMENT",
            target_id=assessment.id,
        )
        if proposal is None:
            return AIRobProposalView(
                assessment_id=assessment.id,
                study_id=assessment.study_id,
                instrument_version_id=version.id,
                proposal_id=None,
                ai_run_id=run.id,
                mode=mode,
                readiness=AIRobReadiness.READY,
                status="FAILED",
                failure_reason=f"AI run ended in {run.state.value}; no proposal was created",
                is_revealed=False,
                structured_value=None,
                validation_results=None,
                domain_suggestions=None,
                overall_suggestion=None,
                stale=False,
                stale_reasons=(),
                source_manifest=tuple(manifests),
                selected_chunk_ids=prepared.selected_chunk_ids,
                omitted_chunk_count=len(prepared.omitted_chunks),
                selection_method=prepared.selection_method,
            )
        validation = validate_rob_output(proposal.structured_value, version.definition, input_data)
        link = await self._repository.create_proposal_link(
            organization_id=actor.organization_id,
            review_id=review_id,
            proposal_id=proposal.id,
            ai_run_id=run.id,
            assessment_id=assessment.id,
            study_id=assessment.study_id,
            instrument_version_id=version.id,
            instrument_content_hash=version.content_hash,
            task_definition_version=ROB_TASK.version,
            assistance_mode=mode.value,
            source_manifest=manifests,
            selected_chunk_ids=list(prepared.selected_chunk_ids),
            omitted_chunks=list(prepared.omitted_chunks),
            selection_method=prepared.selection_method,
            chunk_manifest_hash=prepared.chunk_manifest_hash,
            selected_text_hash=prepared.selected_text_hash,
            validation_results=validation,
            domain_suggestions=validation["domain_suggestions"],
            overall_suggestion=validation["overall_suggestion"],
        )
        for ordinal, manifest in enumerate(manifests, 1):
            await self._repository.create_source(
                organization_id=actor.organization_id,
                review_id=review_id,
                proposal_link_id=link.id,
                ordinal=ordinal,
                **manifest,
            )
        for answer in proposal.structured_value.get("answers", []):
            if not isinstance(answer, dict) or not isinstance(answer.get("evidence"), list):
                continue
            for ordinal, evidence in enumerate(answer["evidence"], 1):
                if not isinstance(evidence, dict):
                    continue
                chunk = next(
                    (
                        item
                        for item in prepared.chunks
                        if item["chunk_id"] == evidence.get("chunk_id")
                    ),
                    None,
                )
                if chunk is None:
                    continue
                await self._repository.create_evidence(
                    organization_id=actor.organization_id,
                    review_id=review_id,
                    proposal_link_id=link.id,
                    question_key=str(answer.get("question_key")),
                    ordinal=ordinal,
                    document_id=UUID(str(evidence["document_id"])),
                    document_version_id=UUID(str(evidence["document_version_id"])),
                    chunk_id=str(evidence["chunk_id"]),
                    source_block_id=UUID(str(chunk["source_block_id"])),
                    page=evidence.get("page"),
                    section=evidence.get("section"),
                    quote=str(evidence.get("quote", "")),
                    evidence_hash=content_hash(
                        {
                            "document_id": evidence.get("document_id"),
                            "chunk_id": evidence.get("chunk_id"),
                            "quote": evidence.get("quote"),
                        }
                    ),
                )
        await self._audit(
            actor,
            review_id,
            link.id,
            "AI_ROB_PROPOSAL_CREATED",
            {
                "proposal_id": str(proposal.id),
                "assessment_id": str(assessment.id),
                "instrument_version_id": str(version.id),
                "input_hash": run.input_hash,
                "validation": validation,
            },
        )
        return await self._view(actor, review_id, link=link)

    async def get_suggestion(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assessment_id: UUID | None = None,
        proposal_id: UUID | None = None,
    ) -> AIRobProposalView:
        await self._reviews.get(actor, review_id)
        if (assessment_id is None) == (proposal_id is None):
            raise ValueError("supply exactly one assessment_id or proposal_id")
        if assessment_id is not None:
            link = await self._repository.latest_assignment_link(
                actor.organization_id, review_id, assessment_id
            )
        else:
            assert proposal_id is not None
            link = await self._repository.get_link_by_proposal(
                actor.organization_id, review_id, proposal_id
            )
        if link is None:
            raise ResourceNotFoundError("Risk of Bias AI proposal was not found")
        return await self._view(actor, review_id, link=link)

    async def list_suggestions(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[AIRobProposalView]:
        await self._reviews.get(actor, review_id)
        result: list[AIRobProposalView] = []
        for link in await self._repository.list_links(actor.organization_id, review_id):
            try:
                result.append(await self._view(actor, review_id, link=link))
            except ResourceNotFoundError:
                continue
        return result

    async def review_answer(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        proposal_id: UUID,
        question_key: str,
        action: AIRobReviewAction,
        human_answer: dict[str, Any] | None,
        reason: str | None,
    ) -> dict[str, Any]:
        AuthorizationService.require(actor, Permission.PERFORM_ROB_ASSESSMENT)
        link = await self._link_for_owner(actor, review_id, proposal_id)
        view = await self._view(actor, review_id, link=link)
        if view.stale:
            raise ConflictError("stale Risk of Bias assistance cannot be accepted")
        if not view.validation_results or not view.validation_results.get("aggregate_valid"):
            raise ConflictError("only a fully valid Risk of Bias proposal can be reviewed")
        answer_item = next(
            (
                item
                for item in (view.structured_value or {}).get("answers", [])
                if item.get("question_key") == question_key
            ),
            None,
        )
        if answer_item is None:
            raise ResourceNotFoundError("Risk of Bias signalling question was not proposed")
        assessment = await self._assessment(actor, review_id, link.assessment_id)
        if assessment.status is AssessmentStatus.SUBMITTED:
            raise ConflictError("submitted assessments cannot receive AI answer review")
        if action in {AIRobReviewAction.ACCEPTED, AIRobReviewAction.EDITED}:
            payload = human_answer or {}
            answer = str(
                payload.get("answer")
                if action is AIRobReviewAction.EDITED
                else answer_item.get("answer") or ""
            )
            rationale = str(payload.get("rationale") or reason or "").strip()
            if not rationale:
                raise ConflictError("a human rationale is required for accepted or edited answers")
            if answer_item.get("status") != AIRobAnswerStatus.PROPOSED_ANSWER.value:
                raise ConflictError("an abstained AI answer cannot be accepted")
            updated = await self._rob_service.save_answer(
                actor,
                review_id=review_id,
                assessment_id=assessment.id,
                question_key=question_key,
                answer=answer,
                rationale=rationale,
                evidence_location_id=_uuid_or_none(payload.get("evidence_location_id")),
            )
            await self._provenance.record_provenance(
                actor,
                review_id=review_id,
                subject_type="rob_answer",
                subject_id=next(
                    item.id for item in updated.answers if item.question_key == question_key
                ),
                source_type="AI_PROPOSAL",
                source_id=link.proposal_id,
                source_locator={
                    "ai_run_id": str(link.ai_run_id),
                    "assessment_id": str(link.assessment_id),
                    "instrument_version_id": str(link.instrument_version_id),
                    "question_key": question_key,
                },
                method_name="human-reviewed-ai-risk-of-bias-answer",
                method_version="1",
                actor_kind=ProvenanceActorKind.HUMAN,
                ai_run_id=None,
                confidence=None,
                verification_state=VerificationState.HUMAN_VERIFIED,
            )
            canonical_snapshot = {
                "answer": answer,
                "rationale": rationale,
                "evidence_location_id": str(_uuid_or_none(payload.get("evidence_location_id")))
                if _uuid_or_none(payload.get("evidence_location_id"))
                else None,
            }
        else:
            updated = assessment
            canonical_snapshot = None
        review = await self._repository.record_answer_review(
            organization_id=actor.organization_id,
            review_id=review_id,
            proposal_id=link.proposal_id,
            assessment_id=link.assessment_id,
            question_key=question_key,
            reviewer_user_id=actor.user_id,
            action=action.value,
            ai_answer_snapshot=answer_item,
            human_answer_snapshot=canonical_snapshot,
            reason=reason,
        )
        await self._audit(
            actor,
            review_id,
            review.id,
            "AI_ROB_ANSWER_REVIEWED",
            {
                "proposal_id": str(link.proposal_id),
                "question_key": question_key,
                "action": action.value,
            },
            reason,
        )
        return {
            "id": review.id,
            "proposal_id": link.proposal_id,
            "assessment_id": updated.id,
            "question_key": question_key,
            "action": action.value,
            "human_actor_id": actor.user_id,
            "canonical_answer_recorded": canonical_snapshot is not None,
        }

    async def create_dataset(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        instrument_version_id: UUID,
        logical_key: str,
        name: str,
        reference_standard: AIRobReferenceStandard,
        cases: list[dict[str, Any]],
    ) -> AIRobEvaluationDataset:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        version = await self._rob.get_version(
            actor.organization_id, review_id, instrument_version_id
        )
        if version is None or version.decision is None or version.decision.value != "APPROVED":
            raise ResourceNotFoundError("approved Risk of Bias instrument version was not found")
        if not cases or len(cases) > 100_000:
            raise ValueError("at least one and at most 100000 evaluation cases are required")
        normalized_cases: list[dict[str, Any]] = []
        for case in cases:
            study_id = _uuid_or_none(case.get("study_id"))
            if (
                study_id is None
                or await self._studies.get_study(actor.organization_id, review_id, study_id) is None
            ):
                raise ResourceNotFoundError("evaluation Study was not found")
            answers = case.get("reference_answers")
            if not isinstance(answers, dict) or not answers:
                raise ValueError("reference answers are required")
            normalized_cases.append(
                {
                    "study_id": study_id,
                    "assessment_id": _uuid_or_none(case.get("assessment_id")),
                    "question_key": str(case.get("question_key") or "__ASSESSMENT__"),
                    "reference_answers": answers,
                    "reference_domains": case.get("reference_domains"),
                    "reference_overall": case.get("reference_overall"),
                    "evidence_snapshot": case.get("evidence_snapshot"),
                }
            )
        content = {
            "instrument_version_id": str(version.id),
            "instrument_content_hash": version.content_hash,
            "logical_key": logical_key.strip(),
            "name": name.strip(),
            "reference_standard": reference_standard.value,
            "cases": [
                {
                    **case,
                    "study_id": str(case["study_id"]),
                }
                for case in normalized_cases
            ],
        }
        return await self._repository.create_dataset(
            organization_id=actor.organization_id,
            review_id=review_id,
            instrument_version_id=version.id,
            logical_key=logical_key.strip(),
            version=await self._next_dataset_version(actor, review_id, logical_key),
            name=name.strip(),
            reference_standard=reference_standard.value,
            content_hash=content_hash(content),
            created_by_user_id=actor.user_id,
            cases=normalized_cases,
        )

    async def evaluate_dataset(
        self, actor: ActorContext, *, review_id: UUID, dataset_id: UUID
    ) -> AIRobEvaluationResultRecord:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        dataset = await self._repository.get_dataset(actor.organization_id, review_id, dataset_id)
        if dataset is None:
            raise ResourceNotFoundError("Risk of Bias evaluation dataset was not found")
        version = await self._rob.get_version(
            actor.organization_id, review_id, dataset.instrument_version_id
        )
        if version is None:
            raise ResourceNotFoundError("Risk of Bias instrument version was not found")
        rows: list[dict[str, Any]] = []
        persisted: list[dict[str, Any]] = []
        for case in await self._repository.list_cases(actor.organization_id, review_id, dataset.id):
            link = (
                await self._repository.latest_assignment_link(
                    actor.organization_id, review_id, case.assessment_id
                )
                if case.assessment_id is not None
                else await self._repository.latest_study_link(
                    actor.organization_id, review_id, case.study_id
                )
            )
            if link is None:
                evaluation = evaluate_rob_case(
                    None,
                    None,
                    case.reference_answers,
                    case.reference_domains,
                    case.reference_overall,
                )
                proposal_id = None
                details = evaluation
            else:
                assessment = await self._rob.get_assessment(
                    actor.organization_id, review_id, link.assessment_id
                )
                if link.assistance_mode is AIScreeningMode.BLINDED_AI and (
                    assessment is None or assessment.status is not AssessmentStatus.SUBMITTED
                ):
                    raise ConflictError(
                        "unrevealed BLINDED_AI Risk of Bias proposals cannot enter evaluation"
                    )
                proposal = await self._ai.get_proposal(
                    actor.organization_id, review_id, link.proposal_id
                )
                evaluation = evaluate_rob_case(
                    proposal.structured_value if proposal else None,
                    link.validation_results,
                    case.reference_answers,
                    case.reference_domains,
                    case.reference_overall,
                )
                proposal_id = proposal.id if proposal else None
                dangerous = _dangerous_underestimation(
                    link.domain_suggestions,
                    case.reference_domains or {},
                    version.definition,
                )
                evaluation["dangerous_underestimation"] = dangerous
                if dangerous:
                    evaluation["classification"] = AIRobMatchClass.DISAGREEMENT.value
                details = {**evaluation, "assessment_id": str(link.assessment_id)}
            rows.append(details)
            persisted.append(
                {
                    "case_id": case.id,
                    "proposal_id": proposal_id,
                    "classification": details["classification"],
                    "signalling_agreement": details["signalling_agreement"],
                    "domain_agreement": details["domain_agreement"],
                    "overall_agreement": details["overall_agreement"],
                    "evidence_grounding_valid": details["evidence_grounding_valid"],
                    "abstention": details["abstention"],
                    "dangerous_underestimation": details["dangerous_underestimation"],
                    "details": details,
                }
            )
        metrics = aggregate_rob_metrics(rows)
        dimensions = {
            "dataset_id": str(dataset.id),
            "instrument_version_id": str(dataset.instrument_version_id),
            "instrument_content_hash": version.content_hash,
            "task_definition_version": ROB_TASK.version,
        }
        return await self._repository.create_evaluation(
            organization_id=actor.organization_id,
            review_id=review_id,
            dataset_id=dataset.id,
            metrics=metrics,
            dimensions=dimensions,
            result_hash=content_hash({"metrics": metrics, "dimensions": dimensions}),
            created_by_user_id=actor.user_id,
            case_results=persisted,
        )

    async def list_datasets(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[AIRobEvaluationDataset]:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        return await self._repository.list_datasets(actor.organization_id, review_id)

    async def list_evaluations(
        self, actor: ActorContext, *, review_id: UUID
    ) -> list[AIRobEvaluationResultRecord]:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        return await self._repository.list_evaluations(actor.organization_id, review_id)

    async def list_case_results(
        self, actor: ActorContext, *, review_id: UUID, evaluation_id: UUID
    ) -> list[AIRobEvaluationCaseResultRecord]:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        return await self._repository.list_case_results(
            actor.organization_id, review_id, evaluation_id
        )

    async def high_risk_queue(
        self, actor: ActorContext, *, review_id: UUID, evaluation_id: UUID
    ) -> list[AIRobEvaluationCaseResultRecord]:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        return await self._repository.high_risk_queue(
            actor.organization_id, review_id, evaluation_id
        )

    async def classify_error(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        case_result_id: UUID,
        category: AIRobErrorCategory,
        note: str | None,
    ) -> Any:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        return await self._repository.classify_error(
            organization_id=actor.organization_id,
            review_id=review_id,
            case_result_id=case_result_id,
            category=category.value,
            note=note,
            classified_by_user_id=actor.user_id,
        )

    async def _view(
        self, actor: ActorContext, review_id: UUID, *, link: AIRobProposalLink
    ) -> AIRobProposalView:
        assessment = await self._assessment(actor, review_id, link.assessment_id)
        proposal = await self._ai.get_proposal(actor.organization_id, review_id, link.proposal_id)
        if proposal is None:
            raise ResourceNotFoundError("Risk of Bias AI proposal was not found")
        stale_reasons = await self._stale_reasons(actor, review_id, link)
        revealed = link.assistance_mode is AIScreeningMode.ASSISTED or (
            assessment.status is AssessmentStatus.SUBMITTED
        )
        if revealed:
            access_type = (
                AIRobAccessType.ASSISTED_VIEW
                if link.assistance_mode is AIScreeningMode.ASSISTED
                else AIRobAccessType.POST_SUBMISSION_REVEAL
            )
            if not await self._repository.access_exists(
                actor.organization_id, review_id, link.proposal_id, actor.user_id, access_type
            ):
                await self._repository.record_access(
                    organization_id=actor.organization_id,
                    review_id=review_id,
                    proposal_id=link.proposal_id,
                    assessment_id=link.assessment_id,
                    reviewer_user_id=actor.user_id,
                    access_type=access_type.value,
                    canonical_assessment_id=assessment.id
                    if assessment.status is AssessmentStatus.SUBMITTED
                    else None,
                )
        return AIRobProposalView(
            link.assessment_id,
            link.study_id,
            link.instrument_version_id,
            link.proposal_id,
            link.ai_run_id,
            link.assistance_mode,
            AIRobReadiness.READY,
            "SUCCEEDED",
            None,
            revealed,
            proposal.structured_value if revealed else None,
            link.validation_results if revealed else None,
            link.domain_suggestions if revealed else None,
            link.overall_suggestion if revealed else None,
            bool(stale_reasons),
            tuple(stale_reasons),
            tuple(link.source_manifest),
            link.selected_chunk_ids,
            len(link.omitted_chunks),
            link.selection_method,
        )

    async def _stale_reasons(
        self, actor: ActorContext, review_id: UUID, link: AIRobProposalLink
    ) -> list[str]:
        version = await self._rob.get_version(
            actor.organization_id, review_id, link.instrument_version_id
        )
        reasons: list[str] = []
        if version is None:
            reasons.append("INSTRUMENT_VERSION_MISSING")
        elif version.content_hash != link.instrument_content_hash:
            reasons.append("INSTRUMENT_VERSION_CHANGED")
        assessments = await self._rob.list_assessments(actor.organization_id, review_id)
        if any(item.supersedes_assessment_id == link.assessment_id for item in assessments):
            reasons.append("ASSESSMENT_SUPERSEDED")
        try:
            requested = [
                {"document_id": source["document_id"], "document_role": source["document_role"]}
                for source in link.source_manifest
            ]
            sources = await self._load_sources(actor, review_id, requested, link.study_id)
            current_manifests = [source_manifest(source) for source in sources]
            if current_manifests != link.source_manifest:
                reasons.append("SOURCE_DOCUMENT_OR_PARSER_CHANGED")
            if version is not None:
                prepared = prepare_rob_input(version.definition, sources)
                if prepared.chunk_manifest_hash != link.chunk_manifest_hash:
                    reasons.append("CHUNK_MANIFEST_CHANGED")
                if prepared.selected_text_hash != link.selected_text_hash:
                    reasons.append("SELECTED_TEXT_CHANGED")
        except (ValueError, ResourceNotFoundError, ConflictError):
            reasons.append("SOURCE_INPUT_UNAVAILABLE")
        return list(dict.fromkeys(reasons))

    async def _link_for_owner(
        self, actor: ActorContext, review_id: UUID, proposal_id: UUID
    ) -> AIRobProposalLink:
        link = await self._repository.get_link_by_proposal(
            actor.organization_id, review_id, proposal_id
        )
        if link is None:
            raise ResourceNotFoundError("Risk of Bias AI proposal was not found")
        await self._assessment(actor, review_id, link.assessment_id)
        return link

    async def _assessment(self, actor: ActorContext, review_id: UUID, assessment_id: UUID) -> Any:
        assessment = await self._rob.get_assessment(actor.organization_id, review_id, assessment_id)
        if assessment is None or assessment.assessor_user_id != actor.user_id:
            raise ResourceNotFoundError("Risk of Bias assessment was not found")
        return assessment

    async def _load_sources(
        self,
        actor: ActorContext,
        review_id: UUID,
        documents: list[dict[str, Any]],
        study_id: UUID,
    ) -> list[ExtractionSource]:
        sources: list[ExtractionSource] = []
        for requested in documents:
            document_id = UUID(str(requested["document_id"]))
            role = FullTextDocumentRole(
                str(requested.get("document_role", FullTextDocumentRole.PRIMARY_FULL_TEXT.value))
            )
            document = await self._documents.get_document(actor.organization_id, document_id)
            if document is None or document.review_id != review_id:
                raise ResourceNotFoundError("source document was not found")
            if not await self._studies.article_linked(
                actor.organization_id, review_id, study_id, document.article_id
            ):
                raise ConflictError("source Article is not linked to the assessment Study")
            processing = await self._documents.latest_successful_processing_run(
                actor.organization_id, review_id, document.id
            )
            if processing is None:
                raise ConflictError("source document has no successful parser run")
            blocks = await self._documents.list_blocks(
                actor.organization_id, review_id, document.id
            )
            sources.append(ExtractionSource(document, processing, role, tuple(blocks)))
        return sources

    async def _next_dataset_version(
        self, actor: ActorContext, review_id: UUID, logical_key: str
    ) -> int:
        datasets = await self._repository.list_datasets(actor.organization_id, review_id)
        return 1 + max(
            (item.version for item in datasets if item.logical_key == logical_key.strip()),
            default=0,
        )

    async def _audit(
        self,
        actor: ActorContext,
        review_id: UUID,
        entity_id: UUID,
        action: str,
        after: dict[str, Any],
        reason: str | None = None,
    ) -> None:
        await self._provenance.record_audit_event(
            actor,
            review_id=review_id,
            entity_type="ai_rob",
            entity_id=entity_id,
            action=action,
            before_snapshot=None,
            after_snapshot=after,
            reason=reason,
        )


def _uuid_or_none(value: Any) -> UUID | None:
    try:
        return UUID(str(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _dangerous_underestimation(
    predicted: dict[str, str | None], reference: dict[str, str], definition: dict[str, Any]
) -> bool:
    for domain in definition.get("domains", []):
        key = domain.get("key")
        predicted_value = predicted.get(key)
        reference_value = reference.get(key)
        rule = domain.get("rule") or {}
        severity = {str(value): index for index, value in enumerate(rule.get("severity_order", []))}
        if (
            predicted_value in severity
            and reference_value in severity
            and severity[str(predicted_value)] < severity[str(reference_value)]
        ):
            return True
    return False
