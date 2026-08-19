from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from backend.app.workflow.recovery_domain import RetryPolicy


class JobState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    AWAITING_HUMAN = "AWAITING_HUMAN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DEAD_LETTERED = "DEAD_LETTERED"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class JobSubmission:
    organization_id: UUID
    review_id: UUID
    workflow_run_id: UUID
    task_name: str
    task_version: str
    idempotency_key: str
    payload: dict[str, Any]
    payload_schema: str = "workflow.generic"
    payload_version: int = 1
    max_attempts: int = 3
    retry_policy: RetryPolicy | None = None
    step_key: str | None = None
    step_order: int | None = None
    definition_hash: str | None = None


@dataclass(frozen=True, slots=True)
class JobHandle:
    job_id: UUID
    workflow_run_id: UUID
    state: JobState


class Orchestrator(Protocol):
    async def submit(self, submission: JobSubmission) -> JobHandle: ...

    async def pause(self, organization_id: UUID, job_id: UUID) -> JobHandle: ...

    async def resume(self, organization_id: UUID, job_id: UUID) -> JobHandle: ...

    async def cancel(self, organization_id: UUID, job_id: UUID) -> JobHandle: ...
