from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from backend.app.ai.domain import AIOutputProposal, AITaskType, content_hash
from backend.app.ai.persistence import SqlAlchemyAIRepository
from backend.app.ai.screening_domain import (
    AIScreeningAccessType,
    AIScreeningDisagreement,
    AIScreeningErrorCategory,
    AIScreeningInteraction,
    AIScreeningMode,
    AIScreeningPolicyVersion,
    AIScreeningProposalLink,
    AIScreeningSuggestion,
    ScreeningEvaluationCaseResult,
    ScreeningEvaluationDataset,
    ScreeningEvaluationPolicy,
    ScreeningEvaluationResult,
    ScreeningReferenceDecision,
    ScreeningReferenceStandard,
    classify_disagreement,
)
from backend.app.ai.screening_metrics import (
    ScreeningPrediction,
    evaluate_screening_predictions,
)
from backend.app.ai.screening_persistence import SqlAlchemyAIScreeningRepository
from backend.app.ai.service import AIExecutionService
from backend.app.ai.tasks import SCREENING_TASK
from backend.app.citations.persistence import SqlAlchemyCitationRepository
from backend.app.core.errors import AuthorizationError, ConflictError, ResourceNotFoundError
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
    ScreeningStage,
)
from backend.app.screening.persistence import SqlAlchemyScreeningRepository


@dataclass(frozen=True, slots=True)
class AIScreeningSuggestionView:
    assignment_id: UUID
    article_id: UUID
    proposal_id: UUID
    ai_run_id: UUID
    mode: AIScreeningMode
    is_revealed: bool
    suggestion: AIScreeningSuggestion | None
    structured_value: dict[str, Any] | None
    protocol_version_id: UUID
    citation_content_hash: str
    accessed: bool


class AIScreeningService:
    """Governed AI screening assistance; it never writes a canonical decision."""

    def __init__(
        self,
        repository: SqlAlchemyAIScreeningRepository,
        ai_repository: SqlAlchemyAIRepository,
        screening_repository: SqlAlchemyScreeningRepository,
        citation_repository: SqlAlchemyCitationRepository,
        protocol_repository: SqlAlchemyProtocolRepository,
        review_service: ReviewService,
        provenance_repository: SqlAlchemyProvenanceRepository,
        execution_service: AIExecutionService,
    ) -> None:
        self._repository = repository
        self._ai_repository = ai_repository
        self._screening_repository = screening_repository
        self._citation_repository = citation_repository
        self._protocol_repository = protocol_repository
        self._review_service = review_service
        self._provenance_repository = provenance_repository
        self._execution_service = execution_service

    async def get_policy(
        self, actor: ActorContext, review_id: UUID
    ) -> AIScreeningPolicyVersion | None:
        await self._review_service.get(actor, review_id)
        return await self._repository.current_policy(actor.organization_id, review_id)

    async def set_policy(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        mode: AIScreeningMode,
        maximum_batch_size: int,
    ) -> AIScreeningPolicyVersion:
        AuthorizationService.require(actor, Permission.MANAGE_AI)
        await self._review_service.get(actor, review_id)
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
            "AI_SCREENING_POLICY_CREATED",
            {"version": policy.version, "mode": policy.mode.value},
        )
        return policy

    async def create_suggestions(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        assignment_ids: list[UUID],
        protocol_version_id: UUID | None = None,
        model_version_id: UUID | None = None,
        prompt_version_id: UUID | None = None,
        maximum_attempts: int = 3,
        timeout_seconds: int = 30,
        per_run_token_ceiling: int | None = 4096,
    ) -> list[AIScreeningSuggestionView]:
        if not actor.has_permission(Permission.SCREEN_ARTICLES):
            raise AuthorizationError("the current role cannot request screening assistance")
        review = await self._review_service.get(actor, review_id)
        policy = await self._repository.current_policy(actor.organization_id, review.id)
        if policy is None or policy.mode is AIScreeningMode.OFF:
            raise ConflictError("AI screening assistance is disabled for this review")
        if not assignment_ids:
            raise ValueError("at least one screening assignment is required")
        if len(assignment_ids) > policy.maximum_batch_size:
            raise ConflictError("the requested screening batch exceeds the active policy limit")
        if len(set(assignment_ids)) != len(assignment_ids):
            raise ConflictError("screening assignments must be unique")
        protocol = await self._approved_protocol(
            actor.organization_id, review.id, protocol_version_id
        )
        result: list[AIScreeningSuggestionView] = []
        for assignment_id in assignment_ids:
            assignment, article = await self._authorized_assignment(actor, assignment_id)
            round_record = await self._screening_repository.get_round(
                actor.organization_id, assignment.round_id
            )
            if round_record is None or round_record.stage is not ScreeningStage.TITLE_ABSTRACT:
                raise ConflictError("AI screening assistance is limited to title/abstract rounds")
            if round_record.review_id != review.id:
                raise ResourceNotFoundError("screening assignment was not found")
            criteria = _criteria(protocol)
            citation = _citation_snapshot(article)
            input_data = {
                "review_id": str(review.id),
                "protocol_version_id": str(protocol.id),
                "eligibility_criteria": criteria["eligibility"],
                "exclusion_criteria": criteria["exclusion"],
                "article_id": str(article.id),
                "title": article.title,
                "abstract": article.abstract,
                "citation": citation,
                "references": [
                    {"type": "protocol_version", "id": str(protocol.id)},
                    {"type": "article", "id": str(article.id)},
                ],
            }
            run, proposal = await self._execution_service.create_and_execute(
                actor,
                review_id=review.id,
                task_type=AITaskType.SCREENING_SUGGESTION,
                input_data=input_data,
                model_version_id=model_version_id,
                prompt_version_id=prompt_version_id,
                maximum_attempts=maximum_attempts,
                timeout_seconds=timeout_seconds,
                per_run_token_ceiling=per_run_token_ceiling,
                target_type="SCREENING_ARTICLE",
                target_id=article.id,
            )
            if proposal is None:
                raise ConflictError("AI screening proposal did not pass deterministic validation")
            link = await self._repository.create_proposal_link(
                organization_id=actor.organization_id,
                review_id=review.id,
                proposal_id=proposal.id,
                ai_run_id=run.id,
                article_id=article.id,
                assignment_id=assignment.id,
                protocol_version_id=protocol.id,
                protocol_content_hash=protocol.content_hash,
                eligibility_criteria_hash=content_hash(criteria["eligibility"]),
                exclusion_criteria_hash=content_hash(criteria["exclusion"]),
                citation_content_hash=content_hash(citation),
                task_definition_version=SCREENING_TASK.version,
                assistance_mode=policy.mode.value,
            )
            await self._audit(
                actor,
                review.id,
                proposal.id,
                "AI_SCREENING_PROPOSAL_CREATED",
                {
                    "ai_run_id": str(run.id),
                    "article_id": str(article.id),
                    "assignment_id": str(assignment.id),
                    "protocol_version_id": str(protocol.id),
                    "assistance_mode": policy.mode.value,
                },
            )
            result.append(
                await self._view(
                    actor,
                    assignment,
                    proposal,
                    link,
                    mode=policy.mode,
                )
            )
        return result

    async def get_suggestion(
        self, actor: ActorContext, *, review_id: UUID, assignment_id: UUID
    ) -> AIScreeningSuggestionView:
        await self._review_service.get(actor, review_id)
        assignment, _ = await self._authorized_assignment(actor, assignment_id)
        if assignment.review_id != review_id:
            raise ResourceNotFoundError("screening assignment was not found")
        link = await self._repository.latest_assignment_link(
            actor.organization_id, review_id, assignment.id
        )
        if link is None:
            raise ResourceNotFoundError("AI screening suggestion was not found")
        proposal = await self._ai_repository.get_proposal(
            actor.organization_id, review_id, link.proposal_id
        )
        if proposal is None:
            raise ResourceNotFoundError("AI screening proposal was not found")
        policy = await self._repository.current_policy(actor.organization_id, review_id)
        mode = policy.mode if policy is not None else link.assistance_mode
        return await self._view(actor, assignment, proposal, link, mode=mode)

    async def record_decision_interaction(
        self, actor: ActorContext, decision: ScreeningDecision
    ) -> None:
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
        try:
            suggestion = AIScreeningSuggestion(proposal.structured_value["suggestion"])
        except (KeyError, ValueError):
            return
        reference = (
            ScreeningReferenceDecision.RETAIN
            if decision.decision is ScreeningDecisionKind.INCLUDE
            else ScreeningReferenceDecision.EXCLUDE
        )
        disagreement = classify_disagreement(suggestion, reference)
        interaction = _interaction_for(disagreement)
        await self._repository.link_decision(
            organization_id=actor.organization_id,
            review_id=decision.review_id,
            screening_decision_id=decision.id,
            proposal_id=proposal.id,
            human_reviewer_user_id=decision.reviewer_user_id,
            interaction=interaction.value,
            disagreement=disagreement.value,
        )
        await self._audit(
            actor,
            decision.review_id,
            decision.id,
            "AI_SCREENING_DECISION_LINKED",
            {
                "proposal_id": str(proposal.id),
                "interaction": interaction.value,
                "disagreement": disagreement.value,
            },
        )

    async def create_dataset(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        logical_key: str,
        name: str,
        protocol_version_id: UUID | None,
        reference_standard: ScreeningReferenceStandard,
        cases: list[dict[str, Any]],
    ) -> ScreeningEvaluationDataset:
        AuthorizationService.require(actor, Permission.MANAGE_AI)
        review = await self._review_service.get(actor, review_id)
        protocol = await self._approved_protocol(
            actor.organization_id, review.id, protocol_version_id
        )
        normalized_cases: list[dict[str, Any]] = []
        seen_articles: set[UUID] = set()
        if not cases:
            raise ValueError("an evaluation dataset requires at least one case")
        for case in cases:
            article_id = _uuid_value(case.get("article_id"), "article_id")
            if article_id in seen_articles:
                raise ConflictError("an evaluation dataset cannot repeat an article")
            seen_articles.add(article_id)
            article = await self._citation_repository.get_article(
                actor.organization_id, review.id, article_id
            )
            if article is None:
                raise ResourceNotFoundError("evaluation article was not found")
            raw_decision = case.get("reference_decision")
            if not isinstance(raw_decision, str):
                raise ValueError("reference_decision is required")
            decision = ScreeningReferenceDecision(raw_decision)
            source_type = ScreeningReferenceStandard(
                case.get("reference_source_type", reference_standard.value)
            )
            normalized_cases.append(
                {
                    "article_id": article.id,
                    "reference_decision": decision.value,
                    "reference_source_type": source_type.value,
                    "reference_source_id": case.get("reference_source_id"),
                }
            )
        key = logical_key.strip()
        title = name.strip()
        if not key or not title:
            raise ValueError("dataset logical key and name are required")
        snapshot = {
            "logical_key": key,
            "name": title,
            "protocol_version_id": str(protocol.id),
            "protocol_content_hash": protocol.content_hash,
            "reference_standard": reference_standard.value,
            "cases": [
                {
                    **case,
                    "article_id": str(case["article_id"]),
                    "reference_source_id": (
                        str(case["reference_source_id"])
                        if case["reference_source_id"] is not None
                        else None
                    ),
                }
                for case in normalized_cases
            ],
        }
        dataset = await self._repository.create_dataset(
            cases=normalized_cases,
            organization_id=actor.organization_id,
            review_id=review.id,
            logical_key=key,
            protocol_version_id=protocol.id,
            name=title,
            reference_standard=reference_standard.value,
            content_hash=content_hash(snapshot),
            created_by_user_id=actor.user_id,
        )
        await self._provenance_repository.append_provenance(
            organization_id=actor.organization_id,
            review_id=review.id,
            subject_type="ai_screening_evaluation_dataset",
            subject_id=dataset.id,
            source_type=None,
            source_id=None,
            source_locator={"content_hash": dataset.content_hash},
            method_name="human-curated-ai-screening-evaluation-dataset",
            method_version="1",
            actor_kind=ProvenanceActorKind.HUMAN,
            actor_user_id=actor.user_id,
            ai_run_id=None,
            confidence=None,
            verification_state=VerificationState.HUMAN_VERIFIED,
        )
        await self._audit(
            actor,
            review.id,
            dataset.id,
            "AI_SCREENING_EVALUATION_DATASET_CREATED",
            {"version": dataset.version, "case_count": len(normalized_cases)},
        )
        return dataset

    async def list_datasets(
        self, actor: ActorContext, review_id: UUID
    ) -> list[ScreeningEvaluationDataset]:
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
    ) -> ScreeningEvaluationResult:
        AuthorizationService.require(actor, Permission.MANAGE_AI)
        await self._review_service.get(actor, review_id)
        dataset = await self._repository.get_dataset(actor.organization_id, review_id, dataset_id)
        if dataset is None:
            raise ResourceNotFoundError("AI screening evaluation dataset was not found")
        cases = await self._repository.list_cases(actor.organization_id, review_id, dataset.id)
        article_ids = [case.article_id for case in cases]
        dimensions = None
        if prompt_version_id is None or model_version_id is None:
            dimensions = await self._repository.latest_screening_dimensions(
                actor.organization_id, review_id, dataset.protocol_version_id, article_ids
            )
        resolved_prompt = prompt_version_id or (dimensions[0] if dimensions else None)
        resolved_model = model_version_id or (dimensions[1] if dimensions else None)
        if resolved_prompt is None or resolved_model is None:
            raise ConflictError("evaluation requires matching AI screening proposals")
        matching = await self._repository.matching_proposals(
            actor.organization_id,
            review_id,
            dataset.protocol_version_id,
            resolved_prompt,
            resolved_model,
            article_ids,
        )
        missing = [case.article_id for case in cases if case.article_id not in matching]
        if missing:
            raise ConflictError("evaluation requires one matching proposal for every case")
        predictions: list[ScreeningPrediction] = []
        case_results: list[dict[str, Any]] = []
        for case in cases:
            proposal, _ = matching[case.article_id]
            try:
                suggestion = AIScreeningSuggestion(proposal.structured_value["suggestion"])
            except (KeyError, ValueError) as exc:
                raise ConflictError(
                    "a matching proposal has an invalid screening suggestion"
                ) from exc
            confidence = proposal.model_reported_confidence
            if confidence is None:
                raw_confidence = proposal.structured_value.get("model_reported_confidence")
                confidence = (
                    float(raw_confidence) if isinstance(raw_confidence, (int, float)) else 0.0
                )
            disagreement = classify_disagreement(suggestion, case.reference_decision)
            predictions.append(
                ScreeningPrediction(
                    case_id=case.id,
                    article_id=case.article_id,
                    proposal_id=proposal.id,
                    reference=case.reference_decision,
                    suggestion=suggestion,
                    confidence=confidence,
                )
            )
            case_results.append(
                {
                    "case_id": case.id,
                    "proposal_id": proposal.id,
                    "suggestion": suggestion.value,
                    "reference_decision": case.reference_decision.value,
                    "model_reported_confidence": confidence,
                    "disagreement": disagreement.value,
                }
            )
        evaluated = evaluate_screening_predictions(predictions, evaluation_policy)
        snapshot = {
            "dataset_id": str(dataset.id),
            "dataset_content_hash": dataset.content_hash,
            "protocol_version_id": str(dataset.protocol_version_id),
            "prompt_version_id": str(resolved_prompt),
            "model_version_id": str(resolved_model),
            "task_definition_version": SCREENING_TASK.version,
            "evaluation_policy": evaluation_policy.value,
            "metrics": evaluated,
            "case_results": case_results,
        }
        result = await self._repository.create_result(
            case_results=case_results,
            organization_id=actor.organization_id,
            review_id=review_id,
            dataset_id=dataset.id,
            protocol_version_id=dataset.protocol_version_id,
            prompt_version_id=resolved_prompt,
            model_version_id=resolved_model,
            task_definition_version=SCREENING_TASK.version,
            evaluation_policy=evaluation_policy.value,
            metric_version=evaluated["metric_version"],
            metrics={
                key: value
                for key, value in evaluated.items()
                if key not in {"calibration", "threshold_simulation", "high_risk_disagreements"}
            },
            calibration=evaluated["calibration"],
            threshold_simulation=evaluated["threshold_simulation"],
            high_risk_disagreements=evaluated["high_risk_disagreements"],
            content_hash=content_hash(snapshot),
            created_by_user_id=actor.user_id,
        )
        await self._provenance_repository.append_provenance(
            organization_id=actor.organization_id,
            review_id=review_id,
            subject_type="ai_screening_evaluation",
            subject_id=result.id,
            source_type="ai_screening_evaluation_dataset",
            source_id=dataset.id,
            source_locator={
                "dataset_content_hash": dataset.content_hash,
                "metric_version": result.metric_version,
            },
            method_name="deterministic-ai-screening-evaluation",
            method_version=result.metric_version,
            actor_kind=ProvenanceActorKind.SYSTEM,
            actor_user_id=None,
            ai_run_id=None,
            confidence=None,
            verification_state=VerificationState.UNVERIFIED,
        )
        await self._audit(
            actor,
            review_id,
            result.id,
            "AI_SCREENING_EVALUATION_CREATED",
            {
                "dataset_id": str(dataset.id),
                "metric_version": result.metric_version,
                "evaluation_policy": evaluation_policy.value,
            },
        )
        return result

    async def list_results(
        self, actor: ActorContext, review_id: UUID
    ) -> list[ScreeningEvaluationResult]:
        await self._review_service.get(actor, review_id)
        return await self._repository.list_results(actor.organization_id, review_id)

    async def list_case_results(
        self, actor: ActorContext, *, review_id: UUID, result_id: UUID
    ) -> list[ScreeningEvaluationCaseResult]:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._review_service.get(actor, review_id)
        result = await self._repository.get_result(actor.organization_id, review_id, result_id)
        if result is None:
            raise ResourceNotFoundError("AI screening evaluation was not found")
        return await self._repository.list_case_results(actor.organization_id, review_id, result.id)

    async def classify_error(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        case_result_id: UUID,
        category: AIScreeningErrorCategory,
        notes: str | None,
    ) -> None:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._review_service.get(actor, review_id)
        case_result = await self._repository.get_case_result(
            actor.organization_id, review_id, case_result_id
        )
        if case_result is None:
            raise ResourceNotFoundError("AI screening evaluation case result was not found")
        normalized_notes = notes.strip() if notes else None
        await self._repository.classify_error(
            case_result_id=case_result.id,
            organization_id=actor.organization_id,
            review_id=review_id,
            category=category.value,
            notes=normalized_notes,
            classified_by_user_id=actor.user_id,
        )
        await self._audit(
            actor,
            review_id,
            case_result.id,
            "AI_SCREENING_ERROR_CLASSIFIED",
            {"category": category.value, "notes": normalized_notes},
        )

    async def _authorized_assignment(
        self, actor: ActorContext, assignment_id: UUID
    ) -> tuple[ScreeningAssignment, Any]:
        assignment = await self._screening_repository.get_assignment(
            actor.organization_id, assignment_id
        )
        if assignment is None or assignment.reviewer_user_id != actor.user_id:
            raise ResourceNotFoundError("screening assignment was not found")
        article = await self._citation_repository.get_article(
            actor.organization_id, assignment.review_id, assignment.article_id
        )
        if article is None:
            raise ResourceNotFoundError("screening article was not found")
        return assignment, article

    async def _approved_protocol(
        self,
        organization_id: UUID,
        review_id: UUID,
        protocol_version_id: UUID | None,
    ) -> ProtocolVersion:
        versions = await self._protocol_repository.list_versions(organization_id, review_id)
        if protocol_version_id is not None:
            selected = next((item for item, _ in versions if item.id == protocol_version_id), None)
            decision = next(
                (decision for item, decision in versions if item.id == protocol_version_id), None
            )
        else:
            selected = None
            decision = None
            for item, item_decision in reversed(versions):
                if (
                    item_decision is not None
                    and item_decision.decision is ProtocolDecisionKind.APPROVED
                ):
                    selected, decision = item, item_decision
                    break
        if (
            selected is None
            or decision is None
            or decision.decision is not ProtocolDecisionKind.APPROVED
        ):
            raise ConflictError("AI screening requires an approved protocol version")
        return selected

    async def _view(
        self,
        actor: ActorContext,
        assignment: ScreeningAssignment,
        proposal: AIOutputProposal,
        link: AIScreeningProposalLink,
        *,
        mode: AIScreeningMode,
    ) -> AIScreeningSuggestionView:
        decision = await self._screening_repository.get_decision_for_assignment(
            actor.organization_id, assignment.id
        )
        reveal = decision is not None or mode is AIScreeningMode.ASSISTED
        accessed = False
        if reveal:
            access_type = (
                AIScreeningAccessType.POST_DECISION_REVEAL
                if decision is not None
                else AIScreeningAccessType.ASSISTED_VIEW
            )
            await self._repository.record_access(
                organization_id=actor.organization_id,
                review_id=assignment.review_id,
                proposal_id=proposal.id,
                assignment_id=assignment.id,
                reviewer_user_id=actor.user_id,
                access_type=access_type.value,
                screening_decision_id=decision.id if decision is not None else None,
            )
            accessed = True
        structured_value = proposal.structured_value if reveal else None
        suggestion = None
        if structured_value is not None:
            suggestion = AIScreeningSuggestion(structured_value["suggestion"])
        return AIScreeningSuggestionView(
            assignment_id=assignment.id,
            article_id=assignment.article_id,
            proposal_id=proposal.id,
            ai_run_id=proposal.ai_run_id,
            mode=mode,
            is_revealed=reveal,
            suggestion=suggestion,
            structured_value=structured_value,
            protocol_version_id=link.protocol_version_id,
            citation_content_hash=link.citation_content_hash,
            accessed=accessed,
        )

    async def _audit(
        self,
        actor: ActorContext,
        review_id: UUID,
        entity_id: UUID,
        action: str,
        snapshot: dict[str, Any],
    ) -> None:
        await self._provenance_repository.append_audit_event(
            organization_id=actor.organization_id,
            review_id=review_id,
            entity_type="AI_SCREENING",
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
    if not isinstance(inclusion, list) or not isinstance(exclusion, list):
        raise ConflictError("protocol eligibility criteria are unavailable")
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


def _interaction_for(disagreement: AIScreeningDisagreement) -> AIScreeningInteraction:
    if disagreement in {
        AIScreeningDisagreement.AGREE_INCLUDE,
        AIScreeningDisagreement.AGREE_EXCLUDE,
    }:
        return AIScreeningInteraction.ACCEPTED
    if disagreement in {
        AIScreeningDisagreement.AI_INCLUDE_HUMAN_EXCLUDE,
        AIScreeningDisagreement.AI_EXCLUDE_HUMAN_INCLUDE,
    }:
        return AIScreeningInteraction.DISAGREED
    return AIScreeningInteraction.OVERRIDDEN
