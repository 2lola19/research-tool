from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID


class JobState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    AWAITING_HUMAN = "AWAITING_HUMAN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
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
