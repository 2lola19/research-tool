from __future__ import annotations

from uuid import UUID

from backend.app.core.errors import ConflictError, ResourceNotFoundError
from backend.app.orchestration.contracts import JobHandle, JobState, JobSubmission, Orchestrator
from backend.app.workflow.domain import WorkflowRunState
from backend.app.workflow.persistence import SqlAlchemyWorkflowRepository


class SqlAlchemyOrchestrator(Orchestrator):
    """Small provider-neutral adapter used by the local worker and API tests."""

    def __init__(self, repository: SqlAlchemyWorkflowRepository) -> None:
        self._repository = repository

    async def submit(self, submission: JobSubmission) -> JobHandle:
        run = await self._repository.get_run(
            submission.organization_id,
            submission.review_id,
            submission.workflow_run_id,
        )
        if run is None:
            raise ResourceNotFoundError("workflow run was not found")
        if run.state != WorkflowRunState.ACTIVE:
            raise ConflictError("workflow run is not active")
        existing = await self._repository.get_job_by_idempotency(
            submission.organization_id,
            submission.workflow_run_id,
            submission.idempotency_key,
        )
        if existing is not None:
            if (
                existing.task_name != submission.task_name
                or existing.task_version != submission.task_version
                or existing.payload != submission.payload
                or existing.payload_schema != submission.payload_schema
                or existing.payload_version != submission.payload_version
                or existing.max_attempts != submission.max_attempts
            ):
                raise ConflictError("job idempotency key was reused with different input")
            return JobHandle(existing.id, existing.workflow_run_id, existing.state)
        job = await self._repository.create_job(
            organization_id=submission.organization_id,
            review_id=submission.review_id,
            workflow_run_id=submission.workflow_run_id,
            task_name=submission.task_name,
            task_version=submission.task_version,
            idempotency_key=submission.idempotency_key,
            payload=submission.payload,
            actor_user_id=None,
            payload_schema=submission.payload_schema,
            payload_version=submission.payload_version,
            max_attempts=submission.max_attempts,
        )
        return JobHandle(job.id, job.workflow_run_id, job.state)

    async def pause(self, organization_id: UUID, job_id: UUID) -> JobHandle:
        return await self._transition(
            organization_id, job_id, JobState.PAUSED, "orchestrator pause"
        )

    async def resume(self, organization_id: UUID, job_id: UUID) -> JobHandle:
        job = await self._repository.get_job(organization_id, job_id)
        if job is None:
            raise ResourceNotFoundError("workflow job was not found")
        if job.state != JobState.PAUSED or job.paused_from_state is None:
            raise ConflictError("only paused jobs can resume through the orchestrator")
        return await self._transition(
            organization_id,
            job_id,
            job.paused_from_state,
            "orchestrator resume",
        )

    async def cancel(self, organization_id: UUID, job_id: UUID) -> JobHandle:
        return await self._transition(
            organization_id, job_id, JobState.CANCELLED, "orchestrator cancel"
        )

    async def _transition(
        self,
        organization_id: UUID,
        job_id: UUID,
        target_state: JobState,
        reason: str,
    ) -> JobHandle:
        job = await self._repository.transition_job(
            organization_id=organization_id,
            job_id=job_id,
            target_state=target_state,
            actor_user_id=None,
            reason=reason,
        )
        return JobHandle(job.id, job.workflow_run_id, job.state)
