from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import UUID

from backend.app.ai.copilot_domain import (
    COPILOT_VALIDATOR_VERSION,
    AICopilotPolicy,
    AICopilotQuery,
    AICopilotQueryStatus,
    AICopilotTaskKey,
    build_copilot_context,
    copilot_task_registry,
    validate_copilot_output,
)
from backend.app.ai.copilot_persistence import SqlAlchemyAICopilotRepository
from backend.app.ai.domain import AIRunState, AITaskType
from backend.app.ai.service import AIExecutionService
from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.identity.domain import ActorContext, Permission
from backend.app.identity.service import AuthorizationService
from backend.app.prisma.contracts import PrismaRepository
from backend.app.provenance.service import ProvenanceService
from backend.app.reviews.service import ReviewService
from backend.app.workflow.contracts import WorkflowRepository


class AICopilotService:
    def __init__(
        self,
        repository: SqlAlchemyAICopilotRepository,
        reviews: ReviewService,
        provenance: ProvenanceService,
        execution: AIExecutionService,
        prisma: PrismaRepository,
        workflows: WorkflowRepository,
    ) -> None:
        self._repository = repository
        self._reviews = reviews
        self._provenance = provenance
        self._execution = execution
        self._prisma = prisma
        self._workflows = workflows

    async def create_policy(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        maximum_query_characters: int,
        maximum_context_items: int,
    ) -> AICopilotPolicy:
        AuthorizationService.require(actor, Permission.MANAGE_AI)
        await self._reviews.get(actor, review_id)
        if not 100 <= maximum_query_characters <= 4_000:
            raise ValueError("maximum query characters must be from 100 through 4000")
        if not 2 <= maximum_context_items <= 200:
            raise ValueError("maximum context items must be from 2 through 200")
        return await self._repository.create_policy(
            organization_id=actor.organization_id,
            review_id=review_id,
            maximum_query_characters=maximum_query_characters,
            maximum_context_items=maximum_context_items,
            created_by_user_id=actor.user_id,
        )

    async def get_policy(self, actor: ActorContext, review_id: UUID) -> AICopilotPolicy:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        policy = await self._repository.current_policy(actor.organization_id, review_id)
        if policy is None:
            raise ResourceNotFoundError("AI copilot policy is not configured")
        return policy

    async def query(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        task_key: AICopilotTaskKey,
        query_text: str,
        maximum_attempts: int = 3,
        timeout_seconds: int = 30,
        per_run_token_ceiling: int | None = 8_192,
    ) -> AICopilotQuery:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        review = await self._reviews.get(actor, review_id)
        policy = await self._repository.current_policy(actor.organization_id, review_id)
        if policy is None:
            raise ConflictError("AI copilot is not configured for this review")
        normalized_query = query_text.strip()
        if not normalized_query:
            raise ValueError("copilot query cannot be empty")
        if len(normalized_query) > policy.maximum_query_characters:
            raise ValueError("copilot query exceeds the configured maximum length")

        summary, readiness, source_references = await self._prisma.summarize(
            actor.organization_id, review.id
        )
        workflow_runs = await self._workflows.list_runs(actor.organization_id, review.id)
        workflow_jobs = await self._workflows.list_jobs(actor.organization_id, review.id)
        context, citations, context_hash = build_copilot_context(
            review,
            summary,
            readiness,
            source_references,
            workflow_runs,
            workflow_jobs,
            maximum_context_items=policy.maximum_context_items,
        )
        input_data: dict[str, Any] = {
            "review_id": str(review.id),
            "task_key": task_key.value,
            "query": normalized_query,
            "context": context,
            "citations": citations,
            "references": citations,
        }
        run, proposal = await self._execution.create_and_execute(
            actor,
            review_id=review.id,
            task_type=AITaskType.REVIEW_COPILOT,
            input_data=input_data,
            maximum_attempts=maximum_attempts,
            timeout_seconds=timeout_seconds,
            per_run_token_ceiling=per_run_token_ceiling,
            target_type="REVIEW_COPILOT_QUERY",
        )

        answer: dict[str, Any] | None = None
        validation_errors: list[dict[str, str]] = []
        if proposal is not None:
            answer = proposal.structured_value
            validation_errors = validate_copilot_output(answer, input_data)
        if proposal is not None and not validation_errors:
            status = (
                AICopilotQueryStatus.ABSTAINED
                if answer and answer.get("abstention")
                else AICopilotQueryStatus.SUCCEEDED
            )
            failure_reason = None
        elif run.state is AIRunState.INVALID_OUTPUT:
            status = AICopilotQueryStatus.INVALID_OUTPUT
            failure_reason = "AI output failed the copilot validation contract."
            answer = None
        else:
            status = AICopilotQueryStatus.FAILED
            failure_reason = "AI execution did not produce a validated copilot answer."
            answer = None

        item = await self._repository.create_query(
            organization_id=actor.organization_id,
            review_id=review.id,
            task_key=task_key.value,
            query_text=normalized_query,
            context_snapshot=context,
            context_hash=context_hash,
            citations=citations,
            ai_run_id=run.id,
            proposal_id=proposal.id if proposal is not None else None,
            answer_snapshot=answer,
            validation_results={
                "validator_version": COPILOT_VALIDATOR_VERSION,
                "valid": not validation_errors,
                "errors": validation_errors,
            },
            status=status.value,
            failure_reason=failure_reason,
            created_by_user_id=actor.user_id,
        )
        await self._provenance.record_audit_event(
            actor,
            review_id=review.id,
            entity_type="ai_copilot_query",
            entity_id=item.id,
            action="created",
            before_snapshot=None,
            after_snapshot={
                "status": item.status.value,
                "task_key": item.task_key.value,
                "context_hash": item.context_hash,
                "ai_run_id": str(item.ai_run_id),
                "proposal_id": str(item.proposal_id) if item.proposal_id else None,
                "citation_ids": [entry["citation_id"] for entry in item.citations],
            },
            reason=None,
        )
        return item

    async def _current_context_hash(
        self,
        actor: ActorContext,
        review_id: UUID,
        policy: AICopilotPolicy,
    ) -> str:
        review = await self._reviews.get(actor, review_id)
        summary, readiness, source_references = await self._prisma.summarize(
            actor.organization_id, review.id
        )
        workflow_runs = await self._workflows.list_runs(actor.organization_id, review.id)
        workflow_jobs = await self._workflows.list_jobs(actor.organization_id, review.id)
        _, _, context_hash = build_copilot_context(
            review,
            summary,
            readiness,
            source_references,
            workflow_runs,
            workflow_jobs,
            maximum_context_items=policy.maximum_context_items,
        )
        return context_hash

    async def _mark_stale(
        self,
        actor: ActorContext,
        review_id: UUID,
        items: list[AICopilotQuery],
    ) -> list[AICopilotQuery]:
        if not items:
            return items
        policy = await self._repository.current_policy(actor.organization_id, review_id)
        if policy is None:
            return [
                replace(item, stale=True, stale_reasons=("COPILOT_POLICY_MISSING",))
                for item in items
            ]
        current_hash = await self._current_context_hash(actor, review_id, policy)
        return [
            replace(
                item,
                stale=item.context_hash != current_hash,
                stale_reasons=("CURRENT_CANONICAL_CONTEXT_CHANGED",)
                if item.context_hash != current_hash
                else (),
            )
            for item in items
        ]

    async def list_queries(self, actor: ActorContext, review_id: UUID) -> list[AICopilotQuery]:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        items = await self._repository.list_queries(actor.organization_id, review_id)
        return await self._mark_stale(actor, review_id, items)

    async def get_query(
        self, actor: ActorContext, review_id: UUID, query_id: UUID
    ) -> AICopilotQuery:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        await self._reviews.get(actor, review_id)
        item = await self._repository.get_query(actor.organization_id, review_id, query_id)
        if item is None:
            raise ResourceNotFoundError("AI copilot query was not found")
        return (await self._mark_stale(actor, review_id, [item]))[0]

    @staticmethod
    def task_registry(actor: ActorContext) -> list[dict[str, Any]]:
        AuthorizationService.require(actor, Permission.REVIEW_AI_PROPOSALS)
        return copilot_task_registry()
