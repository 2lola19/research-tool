from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from backend.app.ai.domain import AIOutputProposal, AITaskType, content_hash
from backend.app.ai.full_text_domain import (
    AIFullTextProposalLink,
    FullTextDocumentRole,
    FullTextErrorCategory,
    FullTextEvaluationDataset,
    FullTextReadiness,
    FullTextReferenceStandard,
    prepare_full_text_input,
    validate_full_text_output,
)
from backend.app.ai.full_text_metrics import FullTextPrediction, evaluate_full_text_predictions
from backend.app.ai.full_text_persistence import SqlAlchemyAIFullTextRepository
from backend.app.ai.persistence import SqlAlchemyAIRepository
from backend.app.ai.screening_domain import (
    AIScreeningAccessType,
    AIScreeningDisagreement,
    AIScreeningInteraction,
    AIScreeningMode,
    AIScreeningSuggestion,
    ScreeningEvaluationPolicy,
    ScreeningReferenceDecision,
    classify_disagreement,
)
from backend.app.ai.screening_persistence import SqlAlchemyAIScreeningRepository
from backend.app.ai.service import AIExecutionService
from backend.app.ai.tasks import FULL_TEXT_SCREENING_TASK
from backend.app.citations.persistence import SqlAlchemyCitationRepository
from backend.app.core.errors import AuthorizationError, ConflictError, ResourceNotFoundError
from backend.app.documents.domain import DocumentStatus
from backend.app.documents.persistence import SqlAlchemyDocumentRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.protocols.domain import ProtocolDecisionKind, ProtocolVersion
from backend.app.protocols.persistence import SqlAlchemyProtocolRepository
from backend.app.provenance.domain import ProvenanceActorKind, VerificationState
from backend.app.provenance.persistence import SqlAlchemyProvenanceRepository
from backend.app.reviews.service import ReviewService
from backend.app.screening.domain import (
    ScreeningAssignment,
    ScreeningDecision,
    ScreeningDecisionKind,
    ScreeningOutcomeKind,
    ScreeningStage,
)
from backend.app.screening.persistence import SqlAlchemyScreeningRepository
from backend.app.screening.service import ScreeningService


@dataclass(frozen=True, slots=True)
class FullTextReadinessView:
    assignment_id: UUID
    document_id: UUID | None
    state: FullTextReadiness
    reason: str | None


@dataclass(frozen=True, slots=True)
class AIFullTextSuggestionView:
    assignment_id: UUID
    article_id: UUID
    document_id: UUID
    document_version_id: UUID
    processing_run_id: UUID
    proposal_id: UUID | None
    ai_run_id: UUID | None
    mode: AIScreeningMode
    readiness: FullTextReadiness
    status: str
    failure_reason: str | None
    is_revealed: bool
    suggestion: AIScreeningSuggestion | None
    structured_value: dict[str, Any] | None
    protocol_version_id: UUID
    stale: bool
    stale_reasons: tuple[str, ...]
    selected_chunk_ids: tuple[str, ...]
    selection_method: str


class AIFullTextScreeningService:
    """Document-grounded full-text assistance that cannot create scientific state itself."""

    def __init__(
        self,
        repository: SqlAlchemyAIFullTextRepository,
        ai_repository: SqlAlchemyAIRepository,
        policy_repository: SqlAlchemyAIScreeningRepository,
        screening_repository: SqlAlchemyScreeningRepository,
        document_repository: SqlAlchemyDocumentRepository,
        citation_repository: SqlAlchemyCitationRepository,
        protocol_repository: SqlAlchemyProtocolRepository,
        review_service: ReviewService,
        provenance_repository: SqlAlchemyProvenanceRepository,
        execution_service: AIExecutionService,
        canonical_screening_service: ScreeningService,
    ) -> None:
        self._repository = repository
        self._ai_repository = ai_repository
        self._policy_repository = policy_repository
        self._screening_repository = screening_repository
        self._document_repository = document_repository
        self._citation_repository = citation_repository
        self._protocol_repository = protocol_repository
        self._review_service = review_service
        self._provenance = provenance_repository
        self._execution = execution_service
        self._canonical_screening = canonical_screening_service

    async def readiness(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assignment_id: UUID,
        document_id: UUID | None,
    ) -> FullTextReadinessView:
        await self._review_service.get(actor, review_id)
        try:
            assignment, _ = await self._authorized_assignment(actor, assignment_id, review_id)
        except (ResourceNotFoundError, ConflictError) as exc:
            return FullTextReadinessView(
                assignment_id, document_id, FullTextReadiness.BLOCKED_ASSIGNMENT, str(exc)
            )
        if document_id is None:
            return FullTextReadinessView(
                assignment.id, None, FullTextReadiness.BLOCKED_NO_DOCUMENT, "no document selected"
            )
        document = await self._document_repository.get_document(actor.organization_id, document_id)
        if (
            document is None
            or document.review_id != review_id
            or document.article_id != assignment.article_id
        ):
            return FullTextReadinessView(
                assignment.id,
                document_id,
                FullTextReadiness.BLOCKED_NO_DOCUMENT,
                "the assignment document was not found",
            )
        if document.status is not DocumentStatus.PROCESSED:
            state = (
                FullTextReadiness.BLOCKED_PROCESSING
                if document.status
                in {
                    DocumentStatus.PROCESSING,
                    DocumentStatus.RETRIEVAL_PENDING,
                    DocumentStatus.RETRIEVED,
                }
                else FullTextReadiness.BLOCKED_OTHER
            )
            return FullTextReadinessView(
                assignment.id, document.id, state, f"document status is {document.status.value}"
            )
        blocks = await self._document_repository.list_blocks(
            actor.organization_id, review_id, document.id
        )
        if not any(item.text.strip() for item in blocks):
            return FullTextReadinessView(
                assignment.id,
                document.id,
                FullTextReadiness.BLOCKED_NO_TEXT,
                "the canonical parsed representation is empty",
            )
        run = await self._document_repository.latest_successful_processing_run(
            actor.organization_id, review_id, document.id
        )
        if run is None:
            return FullTextReadinessView(
                assignment.id,
                document.id,
                FullTextReadiness.BLOCKED_PROCESSING,
                "no successful parser run exists",
            )
        return FullTextReadinessView(assignment.id, document.id, FullTextReadiness.READY, None)

    async def create_suggestions(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        requests: list[dict[str, Any]],
        protocol_version_id: UUID | None = None,
        model_version_id: UUID | None = None,
        prompt_version_id: UUID | None = None,
        maximum_attempts: int = 3,
        timeout_seconds: int = 30,
        per_run_token_ceiling: int | None = 16_384,
    ) -> list[AIFullTextSuggestionView]:
        if not actor.has_permission(Permission.SCREEN_ARTICLES):
            raise AuthorizationError("the current role cannot request full-text assistance")
        review = await self._review_service.get(actor, review_id)
        policy = await self._policy_repository.current_policy(actor.organization_id, review.id)
        if policy is None or policy.mode is AIScreeningMode.OFF:
            raise ConflictError("AI screening assistance is disabled for this review")
        if not requests:
            raise ValueError("at least one assignment and document are required")
        if len(requests) > policy.maximum_batch_size:
            raise ConflictError("the requested full-text batch exceeds the active policy limit")
        assignment_ids = [str(item.get("assignment_id")) for item in requests]
        if len(set(assignment_ids)) != len(assignment_ids):
            raise ConflictError("full-text batch assignments must be unique")
        protocol = await self._approved_protocol(
            actor.organization_id, review.id, protocol_version_id
        )
        criteria = _criteria(protocol)
        results: list[AIFullTextSuggestionView] = []
        for request in requests:
            try:
                assignment_id = _uuid_value(request.get("assignment_id"), "assignment_id")
                document_id = _uuid_value(request.get("document_id"), "document_id")
                role = FullTextDocumentRole(
                    request.get("document_role", FullTextDocumentRole.PRIMARY_FULL_TEXT.value)
                )
                results.append(
                    await self._create_one(
                        actor,
                        review_id=review.id,
                        assignment_id=assignment_id,
                        document_id=document_id,
                        document_role=role,
                        protocol=protocol,
                        criteria=criteria,
                        mode=policy.mode,
                        model_version_id=model_version_id,
                        prompt_version_id=prompt_version_id,
                        maximum_attempts=maximum_attempts,
                        timeout_seconds=timeout_seconds,
                        per_run_token_ceiling=per_run_token_ceiling,
                    )
                )
            except (ValueError, ConflictError, ResourceNotFoundError, AuthorizationError) as exc:
                fallback_assignment = _optional_uuid(request.get("assignment_id"))
                fallback_document = _optional_uuid(request.get("document_id"))
                results.append(
                    AIFullTextSuggestionView(
                        assignment_id=fallback_assignment or UUID(int=0),
                        article_id=UUID(int=0),
                        document_id=fallback_document or UUID(int=0),
                        document_version_id=fallback_document or UUID(int=0),
                        processing_run_id=UUID(int=0),
                        proposal_id=None,
                        ai_run_id=None,
                        mode=policy.mode,
                        readiness=FullTextReadiness.BLOCKED_OTHER,
                        status="FAILED",
                        failure_reason=str(exc),
                        is_revealed=False,
                        suggestion=None,
                        structured_value=None,
                        protocol_version_id=protocol.id,
                        stale=False,
                        stale_reasons=(),
                        selected_chunk_ids=(),
                        selection_method="ordered-structured-bounded-v1",
                    )
                )
        return results

    async def _create_one(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assignment_id: UUID,
        document_id: UUID,
        document_role: FullTextDocumentRole,
        protocol: ProtocolVersion,
        criteria: dict[str, list[dict[str, str]]],
        mode: AIScreeningMode,
        model_version_id: UUID | None,
        prompt_version_id: UUID | None,
        maximum_attempts: int,
        timeout_seconds: int,
        per_run_token_ceiling: int | None,
    ) -> AIFullTextSuggestionView:
        assignment, article = await self._authorized_assignment(actor, assignment_id, review_id)
        ready = await self.readiness(
            actor,
            review_id=review_id,
            assignment_id=assignment.id,
            document_id=document_id,
        )
        if ready.state is not FullTextReadiness.READY:
            raise ConflictError(ready.reason or "full-text AI input is not ready")
        document = await self._document_repository.get_document(actor.organization_id, document_id)
        assert document is not None
        blocks = await self._document_repository.list_blocks(
            actor.organization_id, review_id, document.id
        )
        processing = await self._document_repository.latest_successful_processing_run(
            actor.organization_id, review_id, document.id
        )
        assert processing is not None
        prepared = prepare_full_text_input(document.id, blocks)
        if not prepared.chunks:
            raise ConflictError("the parsed document contains no AI-consumable text")
        citation = _citation_snapshot(article)
        parsed_hash = content_hash(
            [
                {
                    "block_id": item.block_id,
                    "block_type": item.block_type.value,
                    "order": item.block_order,
                    "page": item.page_number,
                    "section_path": item.section_path,
                    "text_hash": content_hash(item.text),
                }
                for item in blocks
            ]
        )
        document_hash = document.sha256 or content_hash(
            {"document_id": str(document.id), "source_identifier": document.source_identifier}
        )
        input_data = {
            "review_id": str(review_id),
            "protocol_version_id": str(protocol.id),
            "eligibility_criteria": criteria["eligibility"],
            "exclusion_criteria": criteria["exclusion"],
            "article_id": str(article.id),
            "document_id": str(document.id),
            "document_version_id": str(document.id),
            "processing_run_id": str(processing.id),
            "citation": citation,
            "document_identity": {
                "document_id": str(document.id),
                "document_version_id": str(document.id),
                "processing_run_id": str(processing.id),
                "document_role": document_role.value,
                "sha256": document.sha256,
                "parser_name": processing.parser_name,
                "parser_version": processing.parser_version,
                "parsed_representation_hash": parsed_hash,
            },
            "chunks": list(prepared.chunks),
            "input_preparation": {
                "method": prepared.selection_method,
                "selected_chunk_ids": list(prepared.selected_chunk_ids),
                "omitted_chunks": list(prepared.omitted_chunks),
                "chunk_manifest_hash": prepared.chunk_manifest_hash,
                "selected_text_hash": prepared.selected_text_hash,
            },
            "references": [
                {"type": "protocol_version", "id": str(protocol.id)},
                {"type": "article", "id": str(article.id)},
                {"type": "document_version", "id": str(document.id)},
                {"type": "document_processing_run", "id": str(processing.id)},
            ],
        }
        run, proposal = await self._execution.create_and_execute(
            actor,
            review_id=review_id,
            task_type=AITaskType.FULL_TEXT_SCREENING_SUGGESTION,
            input_data=input_data,
            model_version_id=model_version_id,
            prompt_version_id=prompt_version_id,
            maximum_attempts=maximum_attempts,
            timeout_seconds=timeout_seconds,
            per_run_token_ceiling=per_run_token_ceiling,
            target_type="FULL_TEXT_SCREENING_ASSIGNMENT",
            target_id=assignment.id,
        )
        if proposal is None:
            return AIFullTextSuggestionView(
                assignment.id,
                article.id,
                document.id,
                document.id,
                processing.id,
                None,
                run.id,
                mode,
                FullTextReadiness.READY,
                "FAILED",
                f"AI run ended in {run.state.value}; no validated proposal was created",
                False,
                None,
                None,
                protocol.id,
                False,
                (),
                prepared.selected_chunk_ids,
                prepared.selection_method,
            )
        link = await self._repository.create_proposal_link(
            organization_id=actor.organization_id,
            review_id=review_id,
            proposal_id=proposal.id,
            ai_run_id=run.id,
            article_id=article.id,
            assignment_id=assignment.id,
            protocol_version_id=protocol.id,
            document_id=document.id,
            document_version_id=document.id,
            processing_run_id=processing.id,
            document_role=document_role.value,
            parser_name=processing.parser_name,
            parser_version=processing.parser_version,
            protocol_content_hash=protocol.content_hash,
            exclusion_criteria_hash=content_hash(criteria["exclusion"]),
            citation_content_hash=content_hash(citation),
            document_content_hash=document_hash,
            parsed_representation_hash=parsed_hash,
            selected_text_hash=prepared.selected_text_hash,
            chunk_manifest_hash=prepared.chunk_manifest_hash,
            selected_chunk_ids=list(prepared.selected_chunk_ids),
            omitted_chunks=list(prepared.omitted_chunks),
            selection_method=prepared.selection_method,
            task_definition_version=FULL_TEXT_SCREENING_TASK.version,
            assistance_mode=mode.value,
        )
        await self._audit(
            actor,
            review_id,
            proposal.id,
            "AI_FULL_TEXT_PROPOSAL_CREATED",
            {
                "assignment_id": str(assignment.id),
                "document_version_id": str(document.id),
                "processing_run_id": str(processing.id),
                "selected_chunk_count": len(prepared.selected_chunk_ids),
                "assistance_mode": mode.value,
            },
        )
        return await self._view(actor, assignment, proposal, link, mode=mode)

    async def get_suggestion(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assignment_id: UUID | None = None,
        proposal_id: UUID | None = None,
    ) -> AIFullTextSuggestionView:
        await self._review_service.get(actor, review_id)
        if (assignment_id is None) == (proposal_id is None):
            raise ValueError("exactly one assignment or proposal identifier is required")
        if proposal_id is not None:
            link = await self._repository.get_proposal_link(
                actor.organization_id, review_id, proposal_id
            )
            if link is None:
                raise ResourceNotFoundError("AI full-text suggestion was not found")
            assignment_id = link.assignment_id
        else:
            assert assignment_id is not None
            link = await self._repository.latest_assignment_link(
                actor.organization_id, review_id, assignment_id
            )
            if link is None:
                raise ResourceNotFoundError("AI full-text suggestion was not found")
        assignment, _ = await self._authorized_assignment(actor, assignment_id, review_id)
        proposal = await self._ai_repository.get_proposal(
            actor.organization_id, review_id, link.proposal_id
        )
        if proposal is None:
            raise ResourceNotFoundError("AI full-text proposal was not found")
        return await self._view(actor, assignment, proposal, link, mode=link.assistance_mode)

    async def accept_suggestion(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        proposal_id: UUID,
        exclusion_reason: str | None,
    ) -> ScreeningDecision:
        view = await self.get_suggestion(actor, review_id=review_id, proposal_id=proposal_id)
        if view.stale:
            raise ConflictError("a stale AI full-text suggestion cannot be accepted")
        if not view.is_revealed or view.suggestion not in {
            AIScreeningSuggestion.INCLUDE,
            AIScreeningSuggestion.EXCLUDE,
        }:
            raise ConflictError("only a revealed binary AI suggestion can be used")
        assert view.structured_value is not None
        canonical_kind = (
            ScreeningDecisionKind.INCLUDE
            if view.suggestion is AIScreeningSuggestion.INCLUDE
            else ScreeningDecisionKind.EXCLUDE
        )
        reason = exclusion_reason.strip() if exclusion_reason else None
        if canonical_kind is ScreeningDecisionKind.EXCLUDE and reason is None:
            criteria = view.structured_value.get("exclusion_criterion_ids", [])
            rationale = str(view.structured_value.get("rationale", "")).strip()
            reason = f"{', '.join(criteria)}: {rationale}" if criteria else rationale
        decision = await self._canonical_screening.decide(
            actor,
            assignment_id=view.assignment_id,
            decision=canonical_kind,
            exclusion_reason=reason,
        )
        await self._repository.link_decision(
            organization_id=actor.organization_id,
            review_id=review_id,
            screening_decision_id=decision.id,
            proposal_id=proposal_id,
            human_reviewer_user_id=actor.user_id,
            interaction=AIScreeningInteraction.ACCEPTED.value,
            disagreement=(
                AIScreeningDisagreement.AGREE_INCLUDE.value
                if canonical_kind is ScreeningDecisionKind.INCLUDE
                else AIScreeningDisagreement.AGREE_EXCLUDE.value
            ),
            exclusion_criterion_from_ai=canonical_kind is ScreeningDecisionKind.EXCLUDE,
        )
        await self._provenance.append_provenance(
            organization_id=actor.organization_id,
            review_id=review_id,
            subject_type="screening_decision",
            subject_id=decision.id,
            source_type="ai_full_text_proposal",
            source_id=proposal_id,
            source_locator={
                "document_version_id": str(view.document_version_id),
                "processing_run_id": str(view.processing_run_id),
                "selected_chunk_ids": list(view.selected_chunk_ids),
            },
            method_name="human-accepted-ai-full-text-suggestion",
            method_version="1",
            actor_kind=ProvenanceActorKind.HUMAN,
            actor_user_id=actor.user_id,
            ai_run_id=view.ai_run_id,
            confidence=None,
            verification_state=VerificationState.HUMAN_VERIFIED,
        )
        await self._audit(
            actor,
            review_id,
            decision.id,
            "AI_FULL_TEXT_SUGGESTION_ACCEPTED_BY_HUMAN",
            {"proposal_id": str(proposal_id), "canonical_decision": canonical_kind.value},
        )
        return decision

    async def record_decision_interaction(
        self, actor: ActorContext, decision: ScreeningDecision
    ) -> None:
        round_record = await self._screening_repository.get_round(
            actor.organization_id, decision.round_id
        )
        if round_record is None or round_record.stage is not ScreeningStage.FULL_TEXT:
            return
        link = await self._repository.latest_assignment_link(
            actor.organization_id, decision.review_id, decision.assignment_id
        )
        if link is None:
            return
        proposal = await self._ai_repository.get_proposal(
            actor.organization_id, decision.review_id, link.proposal_id
        )
        if proposal is None:
            return
        suggestion = AIScreeningSuggestion(proposal.structured_value["suggestion"])
        reference = (
            ScreeningReferenceDecision.RETAIN
            if decision.decision is ScreeningDecisionKind.INCLUDE
            else ScreeningReferenceDecision.EXCLUDE
        )
        disagreement = classify_disagreement(suggestion, reference)
        interaction = _decision_interaction(
            suggestion,
            disagreement,
            link.assistance_mode,
        )
        await self._repository.link_decision(
            organization_id=actor.organization_id,
            review_id=decision.review_id,
            screening_decision_id=decision.id,
            proposal_id=proposal.id,
            human_reviewer_user_id=decision.reviewer_user_id,
            interaction=interaction.value,
            disagreement=disagreement.value,
            exclusion_criterion_from_ai=False,
        )
        await self._audit(
            actor,
            decision.review_id,
            decision.id,
            "AI_FULL_TEXT_DECISION_LINKED",
            {"proposal_id": str(proposal.id), "disagreement": disagreement.value},
        )

    async def create_dataset(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        logical_key: str,
        name: str,
        protocol_version_id: UUID | None,
        reference_standard: FullTextReferenceStandard,
        cases: list[dict[str, Any]],
    ) -> FullTextEvaluationDataset:
        AuthorizationService.require(actor, Permission.MANAGE_AI)
        await self._review_service.get(actor, review_id)
        protocol = await self._approved_protocol(
            actor.organization_id, review_id, protocol_version_id
        )
        if not cases:
            raise ValueError("a full-text evaluation dataset requires cases")
        criteria = _criteria(protocol)
        allowed_criteria = {item["id"] for item in criteria["exclusion"]}
        normalized: list[dict[str, Any]] = []
        seen: set[UUID] = set()
        for item in cases:
            document_id = _uuid_value(item.get("document_id"), "document_id")
            if document_id in seen:
                raise ConflictError("evaluation cases cannot repeat a document version")
            seen.add(document_id)
            document = await self._document_repository.get_document(
                actor.organization_id, document_id
            )
            if document is None or document.review_id != review_id:
                raise ResourceNotFoundError("evaluation document was not found")
            processing = await self._document_repository.latest_successful_processing_run(
                actor.organization_id, review_id, document.id
            )
            if processing is None:
                raise ConflictError(
                    "evaluation documents require a successful parsed representation"
                )
            reference = ScreeningReferenceDecision(str(item.get("reference_decision")))
            criterion = item.get("reference_exclusion_criterion_id")
            if criterion is not None and str(criterion) not in allowed_criteria:
                raise ConflictError("reference exclusion criterion is not in the pinned protocol")
            if reference is ScreeningReferenceDecision.EXCLUDE and criterion is None:
                raise ConflictError("reference exclusions require a criterion")
            source_type = FullTextReferenceStandard(
                item.get("reference_source_type", reference_standard.value)
            )
            source_id = _optional_uuid(item.get("reference_source_id"))
            await self._validate_reference_source(
                actor,
                review_id=review_id,
                article_id=document.article_id,
                reference=reference,
                source_type=source_type,
                source_id=source_id,
            )
            blocks = await self._document_repository.list_blocks(
                actor.organization_id, review_id, document.id
            )
            normalized.append(
                {
                    "article_id": document.article_id,
                    "document_id": document.id,
                    "document_version_id": document.id,
                    "processing_run_id": processing.id,
                    "reference_decision": reference.value,
                    "reference_exclusion_criterion_id": str(criterion) if criterion else None,
                    "reference_source_type": source_type.value,
                    "reference_source_id": source_id,
                    "evidence_snapshot_hash": content_hash(
                        [
                            {"block_id": block.block_id, "text_hash": content_hash(block.text)}
                            for block in blocks
                        ]
                    ),
                }
            )
        snapshot = {
            "logical_key": logical_key.strip(),
            "name": name.strip(),
            "protocol_version_id": str(protocol.id),
            "reference_standard": reference_standard.value,
            "cases": [
                {
                    **item,
                    "article_id": str(item["article_id"]),
                    "document_id": str(item["document_id"]),
                    "document_version_id": str(item["document_version_id"]),
                    "processing_run_id": str(item["processing_run_id"]),
                    "reference_source_id": str(item["reference_source_id"])
                    if item["reference_source_id"]
                    else None,
                }
                for item in normalized
            ],
        }
        dataset = await self._repository.create_dataset(
            cases=normalized,
            organization_id=actor.organization_id,
            review_id=review_id,
            logical_key=logical_key.strip(),
            protocol_version_id=protocol.id,
            name=name.strip(),
            reference_standard=reference_standard.value,
            content_hash=content_hash(snapshot),
            created_by_user_id=actor.user_id,
        )
        await self._audit(
            actor,
            review_id,
            dataset.id,
            "AI_FULL_TEXT_EVALUATION_DATASET_CREATED",
            {"version": dataset.version, "case_count": len(normalized)},
        )
        return dataset

    async def list_datasets(
        self, actor: ActorContext, review_id: UUID
    ) -> list[FullTextEvaluationDataset]:
        await self._review_service.get(actor, review_id)
        return await self._repository.list_datasets(actor.organization_id, review_id)

    async def evaluate_dataset(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        dataset_id: UUID,
        evaluation_policy: ScreeningEvaluationPolicy,
        prompt_version_id: UUID | None = None,
        model_version_id: UUID | None = None,
    ) -> Any:
        AuthorizationService.require(actor, Permission.MANAGE_AI)
        await self._review_service.get(actor, review_id)
        dataset = await self._repository.get_dataset(actor.organization_id, review_id, dataset_id)
        if dataset is None:
            raise ResourceNotFoundError("full-text evaluation dataset was not found")
        cases = await self._repository.list_cases(actor.organization_id, review_id, dataset.id)
        dimensions = await self._repository.latest_dimensions(
            actor.organization_id, review_id, dataset.protocol_version_id
        )
        prompt_id = prompt_version_id or (dimensions[0] if dimensions else None)
        model_id = model_version_id or (dimensions[1] if dimensions else None)
        if prompt_id is None or model_id is None:
            raise ConflictError("evaluation requires matching full-text proposals")
        matching = await self._repository.matching_proposals(
            actor.organization_id,
            review_id,
            dataset.protocol_version_id,
            prompt_id,
            model_id,
            [item.document_version_id for item in cases],
        )
        if len(matching) != len(cases):
            raise ConflictError("evaluation requires one matching proposal per document version")
        articles = {
            item.id: item
            for item in await self._citation_repository.list_articles_by_ids(
                actor.organization_id,
                review_id,
                {item.article_id for item in cases},
            )
        }
        predictions: list[FullTextPrediction] = []
        case_results: list[dict[str, Any]] = []
        proposal_evidence: dict[UUID, list[dict[str, Any]]] = {}
        for case in cases:
            proposal_row, link, run, decision_id = matching[case.document_version_id]
            if link.assistance_mode == AIScreeningMode.BLINDED_AI.value and decision_id is None:
                raise ConflictError(
                    "blinded full-text proposals cannot enter evaluation before human decision"
                )
            structured = proposal_row.structured_value
            suggestion = AIScreeningSuggestion(structured["suggestion"])
            reference = ScreeningReferenceDecision(case.reference_decision)
            proposed_criteria = tuple(
                str(item) for item in structured.get("exclusion_criterion_ids", [])
            )
            input_variables = run.input_snapshot.get("variables", {})
            validation_errors = validate_full_text_output(structured, input_variables)
            issues = tuple(sorted({str(item["code"]) for item in validation_errors}))
            sections = tuple(
                str(item.get("section"))
                for item in structured.get("evidence", [])
                if isinstance(item, dict) and item.get("section") is not None
            )
            confidence = float(proposal_row.model_reported_confidence or 0.0)
            prediction = FullTextPrediction(
                case.id,
                case.article_id,
                case.document_id,
                proposal_row.id,
                reference,
                suggestion,
                confidence,
                case.reference_exclusion_criterion_id,
                proposed_criteria,
                issues,
                sections,
            )
            predictions.append(prediction)
            proposal_evidence[proposal_row.id] = [
                {
                    "chunk_id": item.get("chunk_id"),
                    "page": item.get("page"),
                    "section": item.get("section"),
                    "quoted_text": item.get("quoted_text"),
                }
                for item in structured.get("evidence", [])
                if isinstance(item, dict)
            ]
            disagreement = classify_disagreement(suggestion, reference)
            criterion_correct = (
                case.reference_exclusion_criterion_id in proposed_criteria
                if reference is ScreeningReferenceDecision.EXCLUDE
                and suggestion is AIScreeningSuggestion.EXCLUDE
                else None
            )
            case_results.append(
                {
                    "case_id": case.id,
                    "proposal_id": proposal_row.id,
                    "suggestion": suggestion.value,
                    "reference_decision": reference.value,
                    "model_reported_confidence": confidence,
                    "proposed_criterion_ids": list(proposed_criteria),
                    "reference_criterion_id": case.reference_exclusion_criterion_id,
                    "criterion_correct": criterion_correct,
                    "evidence_valid": not issues,
                    "evidence_issue_codes": list(issues),
                    "evidence_sections": list(sections),
                    "disagreement": disagreement.value,
                }
            )
        metrics = evaluate_full_text_predictions(predictions, evaluation_policy)
        by_proposal = {item.proposal_id: item for item in predictions}
        for row in metrics["high_risk_disagreements"]:
            prediction = by_proposal[UUID(str(row["proposal_id"]))]
            row.update(
                {
                    "document_id": str(prediction.document_id),
                    "reference_decision": prediction.reference.value,
                    "ai_suggestion": prediction.suggestion.value,
                    "citation": _citation_snapshot(articles[prediction.article_id])
                    if prediction.article_id in articles
                    else {"article_id": str(prediction.article_id)},
                    "ai_criterion_ids": list(prediction.proposed_criterion_ids),
                    "evidence_sections": list(prediction.evidence_sections),
                    "evidence": proposal_evidence[prediction.proposal_id],
                }
            )
        result_hash = content_hash(
            {
                "dataset_hash": dataset.content_hash,
                "prompt_version_id": str(prompt_id),
                "model_version_id": str(model_id),
                "policy": evaluation_policy.value,
                "metrics": metrics,
            }
        )
        result_id = await self._repository.create_result(
            case_results=case_results,
            dataset_id=dataset.id,
            organization_id=actor.organization_id,
            review_id=review_id,
            protocol_version_id=dataset.protocol_version_id,
            prompt_version_id=prompt_id,
            model_version_id=model_id,
            task_definition_version=FULL_TEXT_SCREENING_TASK.version,
            evaluation_policy=evaluation_policy.value,
            metric_version=str(metrics["metric_version"]),
            metrics=metrics,
            content_hash=result_hash,
            created_by_user_id=actor.user_id,
        )
        result = await self._repository.get_result(actor.organization_id, review_id, result_id)
        assert result is not None
        await self._audit(
            actor,
            review_id,
            result.id,
            "AI_FULL_TEXT_EVALUATION_COMPLETED",
            {"dataset_id": str(dataset.id), "false_negatives": metrics["confusion_matrix"]["fn"]},
        )
        return result

    async def list_results(self, actor: ActorContext, review_id: UUID) -> list[Any]:
        await self._review_service.get(actor, review_id)
        return await self._repository.list_results(actor.organization_id, review_id)

    async def list_case_results(
        self, actor: ActorContext, *, review_id: UUID, result_id: UUID
    ) -> list[Any]:
        await self._review_service.get(actor, review_id)
        result = await self._repository.get_result(actor.organization_id, review_id, result_id)
        if result is None:
            raise ResourceNotFoundError("full-text evaluation result was not found")
        return await self._repository.list_case_results(actor.organization_id, review_id, result_id)

    async def list_case_error_classifications(
        self, actor: ActorContext, *, review_id: UUID, result_id: UUID
    ) -> list[Any]:
        await self._review_service.get(actor, review_id)
        result = await self._repository.get_result(actor.organization_id, review_id, result_id)
        if result is None:
            raise ResourceNotFoundError("full-text evaluation result was not found")
        return await self._repository.list_error_classifications_for_result(
            actor.organization_id, review_id, result_id
        )

    async def classify_error(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        case_result_id: UUID,
        category: FullTextErrorCategory,
        notes: str | None,
    ) -> None:
        AuthorizationService.require(actor, Permission.MANAGE_AI)
        await self._review_service.get(actor, review_id)
        try:
            await self._repository.classify_error(
                case_result_id=case_result_id,
                organization_id=actor.organization_id,
                review_id=review_id,
                category=category.value,
                notes=notes.strip() if notes else None,
                classified_by_user_id=actor.user_id,
            )
        except LookupError as exc:
            raise ResourceNotFoundError(str(exc)) from exc

    async def _view(
        self,
        actor: ActorContext,
        assignment: ScreeningAssignment,
        proposal: AIOutputProposal,
        link: AIFullTextProposalLink,
        *,
        mode: AIScreeningMode,
    ) -> AIFullTextSuggestionView:
        decision = await self._screening_repository.get_decision_for_assignment(
            actor.organization_id, assignment.id
        )
        reveal = decision is not None or mode is AIScreeningMode.ASSISTED
        if reveal:
            await self._repository.record_access(
                organization_id=actor.organization_id,
                review_id=assignment.review_id,
                proposal_id=proposal.id,
                assignment_id=assignment.id,
                reviewer_user_id=actor.user_id,
                access_type=(
                    AIScreeningAccessType.POST_DECISION_REVEAL.value
                    if decision is not None
                    else AIScreeningAccessType.ASSISTED_VIEW.value
                ),
                screening_decision_id=decision.id if decision else None,
            )
        stale_reasons = await self._stale_reasons(actor, link)
        structured = proposal.structured_value if reveal else None
        return AIFullTextSuggestionView(
            assignment.id,
            assignment.article_id,
            link.document_id,
            link.document_version_id,
            link.processing_run_id,
            proposal.id,
            proposal.ai_run_id,
            mode,
            FullTextReadiness.READY,
            "SUCCEEDED",
            None,
            reveal,
            AIScreeningSuggestion(structured["suggestion"]) if structured else None,
            structured,
            link.protocol_version_id,
            bool(stale_reasons),
            tuple(stale_reasons),
            link.selected_chunk_ids,
            link.selection_method,
        )

    async def _stale_reasons(self, actor: ActorContext, link: AIFullTextProposalLink) -> list[str]:
        reasons: list[str] = []
        versions = await self._protocol_repository.list_versions(
            actor.organization_id, link.review_id
        )
        current_protocol = next(
            (
                item
                for item, decision in reversed(versions)
                if decision is not None and decision.decision is ProtocolDecisionKind.APPROVED
            ),
            None,
        )
        if current_protocol is None or current_protocol.id != link.protocol_version_id:
            reasons.append("PROTOCOL_VERSION_CHANGED")
        article = await self._citation_repository.get_article(
            actor.organization_id, link.review_id, link.article_id
        )
        if (
            article is None
            or content_hash(_citation_snapshot(article)) != link.citation_content_hash
        ):
            reasons.append("CITATION_CHANGED")
        documents = await self._document_repository.list_documents_for_article(
            actor.organization_id, link.review_id, link.article_id
        )
        processed = [item for item in documents if item.status is DocumentStatus.PROCESSED]
        if processed and processed[-1].id != link.document_version_id:
            reasons.append("DOCUMENT_VERSION_CHANGED")
        current_run = await self._document_repository.latest_successful_processing_run(
            actor.organization_id, link.review_id, link.document_id
        )
        if current_run is None or current_run.id != link.processing_run_id:
            reasons.append("PARSED_REPRESENTATION_CHANGED")
        blocks = await self._document_repository.list_blocks(
            actor.organization_id, link.review_id, link.document_id
        )
        prepared = prepare_full_text_input(link.document_id, blocks) if blocks else None
        if prepared is None or prepared.chunk_manifest_hash != link.chunk_manifest_hash:
            reasons.append("CHUNK_MANIFEST_CHANGED")
        elif prepared.selected_text_hash != link.selected_text_hash:
            reasons.append("SELECTED_TEXT_CHANGED")
        if link.task_definition_version != FULL_TEXT_SCREENING_TASK.version:
            reasons.append("TASK_DEFINITION_CHANGED")
        return reasons

    async def _authorized_assignment(
        self, actor: ActorContext, assignment_id: UUID, review_id: UUID
    ) -> tuple[ScreeningAssignment, Any]:
        assignment = await self._screening_repository.get_assignment(
            actor.organization_id, assignment_id
        )
        if assignment is None or assignment.reviewer_user_id != actor.user_id:
            raise ResourceNotFoundError("full-text screening assignment was not found")
        if assignment.review_id != review_id:
            raise ResourceNotFoundError("full-text screening assignment was not found")
        round_record = await self._screening_repository.get_round(
            actor.organization_id, assignment.round_id
        )
        if round_record is None or round_record.stage is not ScreeningStage.FULL_TEXT:
            raise ConflictError("AI full-text assistance requires a full-text screening round")
        article = await self._citation_repository.get_article(
            actor.organization_id, review_id, assignment.article_id
        )
        if article is None:
            raise ResourceNotFoundError("screening article was not found")
        return assignment, article

    async def _approved_protocol(
        self, organization_id: UUID, review_id: UUID, protocol_version_id: UUID | None
    ) -> ProtocolVersion:
        versions = await self._protocol_repository.list_versions(organization_id, review_id)
        candidates = [
            item
            for item, decision in versions
            if decision is not None and decision.decision is ProtocolDecisionKind.APPROVED
        ]
        selected = (
            next((item for item in candidates if item.id == protocol_version_id), None)
            if protocol_version_id is not None
            else candidates[-1]
            if candidates
            else None
        )
        if selected is None:
            raise ConflictError("AI full-text screening requires an approved protocol version")
        return selected

    async def _validate_reference_source(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        article_id: UUID,
        reference: ScreeningReferenceDecision,
        source_type: FullTextReferenceStandard,
        source_id: UUID | None,
    ) -> None:
        if source_type is FullTextReferenceStandard.CURATED_DATASET:
            return
        if source_id is None:
            raise ConflictError(
                "non-curated reference standards require a canonical outcome source"
            )
        outcome = await self._screening_repository.get_outcome_by_id(
            actor.organization_id, source_id
        )
        if outcome is None or outcome.review_id != review_id or outcome.article_id != article_id:
            raise ResourceNotFoundError("full-text reference-standard source was not found")
        round_record = await self._screening_repository.get_round(
            actor.organization_id, outcome.round_id
        )
        if round_record is None or round_record.stage is not ScreeningStage.FULL_TEXT:
            raise ConflictError("reference-standard source must be a full-text outcome")
        adjudication = await self._screening_repository.get_adjudication(
            actor.organization_id, outcome.id
        )
        if source_type is FullTextReferenceStandard.ADJUDICATED_FULL_TEXT and adjudication is None:
            raise ConflictError("adjudicated reference standards require an adjudication")
        if source_type is FullTextReferenceStandard.REVIEWER_CONSENSUS:
            if outcome.outcome is ScreeningOutcomeKind.CONFLICT:
                raise ConflictError("reviewer-consensus standards cannot cite a conflict")
            final_decision = ScreeningDecisionKind(outcome.outcome.value)
        elif adjudication is not None:
            final_decision = adjudication.decision
        elif outcome.outcome is not ScreeningOutcomeKind.CONFLICT:
            final_decision = ScreeningDecisionKind(outcome.outcome.value)
        else:
            raise ConflictError("final human reference standard is unresolved")
        expected = (
            ScreeningReferenceDecision.RETAIN
            if final_decision is ScreeningDecisionKind.INCLUDE
            else ScreeningReferenceDecision.EXCLUDE
        )
        if reference is not expected:
            raise ConflictError("reference decision does not match its canonical full-text source")

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
            entity_type="AI_FULL_TEXT_SCREENING",
            entity_id=entity_id,
            action=action,
            actor_user_id=actor.user_id,
            before_snapshot=None,
            after_snapshot=snapshot,
            reason=None,
        )


def _criteria(protocol: ProtocolVersion) -> dict[str, list[dict[str, str]]]:
    eligibility = protocol.content.get("eligibility")
    if not isinstance(eligibility, dict):
        raise ConflictError("protocol eligibility criteria are unavailable")
    inclusion = eligibility.get("inclusion")
    exclusion = eligibility.get("exclusion")
    if not isinstance(inclusion, list) or not isinstance(exclusion, list) or not exclusion:
        raise ConflictError("protocol full-text exclusion criteria are unavailable")
    return {
        "eligibility": [
            {"id": f"inclusion-{index + 1}", "text": str(value)}
            for index, value in enumerate(inclusion)
        ],
        "exclusion": [
            {"id": f"exclusion-{index + 1}", "text": str(value)}
            for index, value in enumerate(exclusion)
        ],
    }


def _citation_snapshot(article: Any) -> dict[str, Any]:
    return {
        "article_id": str(article.id),
        "title": article.title,
        "abstract": article.abstract,
        "publication_year": article.publication_year,
        "doi": article.doi,
        "pmid": article.pmid,
        "journal": article.journal,
    }


def _uuid_value(value: Any, field: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        raise ValueError(f"{field} must be a valid UUID") from None


def _optional_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    try:
        return _uuid_value(value, "identifier")
    except ValueError:
        return None


def _decision_interaction(
    suggestion: AIScreeningSuggestion,
    disagreement: AIScreeningDisagreement,
    mode: AIScreeningMode,
) -> AIScreeningInteraction:
    if mode is AIScreeningMode.BLINDED_AI:
        return AIScreeningInteraction.UNSEEN
    if disagreement in {
        AIScreeningDisagreement.AI_EXCLUDE_HUMAN_INCLUDE,
        AIScreeningDisagreement.AI_INCLUDE_HUMAN_EXCLUDE,
    }:
        return AIScreeningInteraction.DISAGREED
    if suggestion in {AIScreeningSuggestion.MAYBE, AIScreeningSuggestion.ABSTAIN}:
        return AIScreeningInteraction.OVERRIDDEN
    return AIScreeningInteraction.VIEWED
