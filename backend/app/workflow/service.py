from __future__ import annotations

from uuid import UUID

from backend.app.core.errors import AuthorizationError, ConflictError, ResourceNotFoundError
from backend.app.identity.contracts import IdentityRepository
from backend.app.identity.domain import ActorContext, Permission
from backend.app.orchestration.contracts import JobState
from backend.app.reviews.contracts import ReviewRepository
from backend.app.reviews.domain import ReviewProject
from backend.app.reviews.service import ReviewService
from backend.app.workflow.contracts import WorkflowRepository
from backend.app.workflow.domain import (
    CheckpointState,
    HumanCheckpoint,
    JobEvent,
    WorkflowJob,
    WorkflowRun,
    WorkflowRunState,
)
from backend.app.workflow.recovery_domain import RetryPolicy


class WorkflowService:
    def __init__(
        self,
        repository: WorkflowRepository,
        review_repository: ReviewRepository,
        identity_repository: IdentityRepository,
    ) -> None:
        self._repository = repository
        self._review_service = ReviewService(review_repository, identity_repository)

    async def create_run(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        workflow_name: str,
        workflow_version: str,
        idempotency_key: str,
    ) -> WorkflowRun:
        review = await self._review_service.get(actor, review_id)
        self._require_controller(actor, review)
        existing = await self._repository.get_run_by_idempotency(
            actor.organization_id,
            review.id,
            idempotency_key,
        )
        if existing is not None:
            if (
                existing.workflow_name != workflow_name.strip()
                or existing.workflow_version != workflow_version.strip()
            ):
                raise ConflictError("workflow idempotency key was reused with different input")
            return existing
        return await self._repository.create_run(
            organization_id=actor.organization_id,
            review_id=review.id,
            workflow_name=workflow_name.strip(),
            workflow_version=workflow_version.strip(),
            idempotency_key=idempotency_key.strip(),
            created_by_user_id=actor.user_id,
        )

    async def submit_job(
        self,
        actor: ActorContext,
        *,
        review_id: UUID,
        workflow_run_id: UUID,
        task_name: str,
        task_version: str,
        idempotency_key: str,
        payload: dict[str, object],
        payload_schema: str = "workflow.generic",
        payload_version: int = 1,
        max_attempts: int = 3,
        retry_policy: RetryPolicy | None = None,
        step_key: str | None = None,
        step_order: int | None = None,
        definition_hash: str | None = None,
    ) -> WorkflowJob:
        effective_retry_policy = retry_policy or RetryPolicy(max_attempts=max_attempts)
        if effective_retry_policy.max_attempts != max_attempts:
            raise ConflictError("retry policy attempts must match max_attempts")
        review = await self._review_service.get(actor, review_id)
        self._require_controller(actor, review)
        run = await self._repository.get_run(
            actor.organization_id,
            review.id,
            workflow_run_id,
        )
        if run is None:
            raise ResourceNotFoundError("workflow run was not found")
        if run.state != WorkflowRunState.ACTIVE:
            raise ConflictError("workflow run is not active")
        existing = await self._repository.get_job_by_idempotency(
            actor.organization_id,
            run.id,
            idempotency_key,
        )
        if existing is not None:
            if (
                existing.task_name != task_name.strip()
                or existing.task_version != task_version.strip()
                or existing.payload != payload
                or existing.payload_schema != payload_schema.strip()
                or existing.payload_version != payload_version
                or existing.max_attempts != max_attempts
                or existing.retry_policy != effective_retry_policy
                or existing.step_key != step_key
                or existing.step_order != step_order
                or existing.definition_hash != definition_hash
            ):
                raise ConflictError("job idempotency key was reused with different input")
            return existing
        return await self._repository.create_job(
            organization_id=actor.organization_id,
            review_id=review.id,
            workflow_run_id=run.id,
            task_name=task_name.strip(),
            task_version=task_version.strip(),
            idempotency_key=idempotency_key.strip(),
            payload=payload,
            actor_user_id=actor.user_id,
            payload_schema=payload_schema.strip(),
            payload_version=payload_version,
            max_attempts=max_attempts,
            retry_policy=effective_retry_policy,
            step_key=step_key,
            step_order=step_order,
            definition_hash=definition_hash,
        )

    async def transition_job(
        self,
        actor: ActorContext,
        job_id: UUID,
        target_state: JobState,
        reason: str | None,
    ) -> WorkflowJob:
        job = await self._repository.get_job(actor.organization_id, job_id)
        if job is None:
            raise ResourceNotFoundError("workflow job was not found")
        review = await self._review_service.get(actor, job.review_id)
        self._require_controller(actor, review)
        if job.state == JobState.PAUSED and target_state != job.paused_from_state:
            raise ConflictError("a paused job must resume to its prior state")
        return await self._repository.transition_job(
            organization_id=actor.organization_id,
            job_id=job.id,
            target_state=target_state,
            actor_user_id=actor.user_id,
            reason=reason,
        )

    async def list_events(self, actor: ActorContext, job_id: UUID) -> list[JobEvent]:
        job = await self._repository.get_job(actor.organization_id, job_id)
        if job is None:
            raise ResourceNotFoundError("workflow job was not found")
        await self._review_service.get(actor, job.review_id)
        return await self._repository.list_job_events(actor.organization_id, job.id)

    async def request_checkpoint(
        self,
        actor: ActorContext,
        job_id: UUID,
        request_message: str,
    ) -> HumanCheckpoint:
        job, _ = await self._controlled_job(actor, job_id)
        if job.state != JobState.RUNNING:
            raise ConflictError("human checkpoints can only be requested for running jobs")
        await self._repository.transition_job(
            organization_id=actor.organization_id,
            job_id=job.id,
            target_state=JobState.AWAITING_HUMAN,
            actor_user_id=actor.user_id,
            reason="human checkpoint requested",
        )
        return await self._repository.create_checkpoint(
            organization_id=actor.organization_id,
            job_id=job.id,
            requested_by_user_id=actor.user_id,
            request_message=request_message,
        )

    async def resolve_checkpoint(
        self,
        actor: ActorContext,
        checkpoint_id: UUID,
        decision: CheckpointState,
        decision_note: str | None,
    ) -> HumanCheckpoint:
        if decision not in {CheckpointState.APPROVED, CheckpointState.REJECTED}:
            raise ConflictError("checkpoint decision must be APPROVED or REJECTED")
        checkpoint = await self._repository.get_checkpoint(actor.organization_id, checkpoint_id)
        if checkpoint is None:
            raise ResourceNotFoundError("human checkpoint was not found")
        job, _ = await self._controlled_job(actor, checkpoint.job_id)
        if job.state != JobState.AWAITING_HUMAN:
            raise ConflictError("workflow job is not awaiting a human decision")
        resolved = await self._repository.resolve_checkpoint(
            organization_id=actor.organization_id,
            checkpoint_id=checkpoint.id,
            decision=decision,
            resolved_by_user_id=actor.user_id,
            decision_note=decision_note,
        )
        await self._repository.transition_job(
            organization_id=actor.organization_id,
            job_id=job.id,
            target_state=(
                JobState.RUNNING if decision == CheckpointState.APPROVED else JobState.FAILED
            ),
            actor_user_id=actor.user_id,
            reason=decision_note or f"checkpoint {decision.value.casefold()}",
        )
        return resolved

    async def _controlled_job(
        self, actor: ActorContext, job_id: UUID
    ) -> tuple[WorkflowJob, ReviewProject]:
        job = await self._repository.get_job(actor.organization_id, job_id)
        if job is None:
            raise ResourceNotFoundError("workflow job was not found")
        review = await self._review_service.get(actor, job.review_id)
        self._require_controller(actor, review)
        return job, review

    @staticmethod
    def _require_controller(actor: ActorContext, review: ReviewProject) -> None:
        if not actor.has_permission(Permission.MANAGE_REVIEW_ACCESS):
            raise AuthorizationError("the current role cannot control workflow state")
        if (
            not actor.has_permission(Permission.VIEW_ALL_REVIEWS)
            and review.owner_user_id != actor.user_id
        ):
            raise AuthorizationError("only the review owner may control workflow state")
