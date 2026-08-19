from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from backend.app.orchestration.contracts import JobState
from backend.app.workflow.domain import (
    CheckpointState,
    HumanCheckpoint,
    JobEvent,
    WorkflowJob,
    WorkflowRun,
)


class WorkflowRepository(Protocol):
    async def create_run(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        workflow_name: str,
        workflow_version: str,
        idempotency_key: str,
        created_by_user_id: UUID,
    ) -> WorkflowRun: ...

    async def get_run_by_idempotency(
        self,
        organization_id: UUID,
        review_id: UUID,
        idempotency_key: str,
    ) -> WorkflowRun | None: ...

    async def get_run(
        self,
        organization_id: UUID,
        review_id: UUID,
        workflow_run_id: UUID,
    ) -> WorkflowRun | None: ...

    async def list_runs(self, organization_id: UUID, review_id: UUID) -> list[WorkflowRun]: ...

    async def create_job(
        self,
        *,
        organization_id: UUID,
        review_id: UUID,
        workflow_run_id: UUID,
        task_name: str,
        task_version: str,
        idempotency_key: str,
        payload: dict[str, Any],
        actor_user_id: UUID | None,
    ) -> WorkflowJob: ...

    async def get_job_by_idempotency(
        self,
        organization_id: UUID,
        workflow_run_id: UUID,
        idempotency_key: str,
    ) -> WorkflowJob | None: ...

    async def get_job(self, organization_id: UUID, job_id: UUID) -> WorkflowJob | None: ...

    async def list_jobs(self, organization_id: UUID, review_id: UUID) -> list[WorkflowJob]: ...

    async def transition_job(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        target_state: JobState,
        actor_user_id: UUID | None,
        reason: str | None,
    ) -> WorkflowJob: ...

    async def list_job_events(
        self,
        organization_id: UUID,
        job_id: UUID,
    ) -> list[JobEvent]: ...

    async def create_checkpoint(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        requested_by_user_id: UUID,
        request_message: str,
    ) -> HumanCheckpoint: ...

    async def get_checkpoint(
        self,
        organization_id: UUID,
        checkpoint_id: UUID,
    ) -> HumanCheckpoint | None: ...

    async def resolve_checkpoint(
        self,
        *,
        organization_id: UUID,
        checkpoint_id: UUID,
        decision: CheckpointState,
        resolved_by_user_id: UUID,
        decision_note: str | None,
    ) -> HumanCheckpoint: ...
