from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from backend.app.core.errors import InvalidStateTransitionError
from backend.app.orchestration.contracts import JobState
from backend.app.workflow.recovery_domain import FailureClass, RetryPolicy


class WorkflowRunState(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CheckpointState(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class JobEventType(StrEnum):
    SUBMITTED = "SUBMITTED"
    STATE_CHANGED = "STATE_CHANGED"
    CHECKPOINT_REQUESTED = "CHECKPOINT_REQUESTED"
    CHECKPOINT_RESOLVED = "CHECKPOINT_RESOLVED"
    ATTEMPT_CLAIMED = "ATTEMPT_CLAIMED"
    ATTEMPT_HEARTBEAT = "ATTEMPT_HEARTBEAT"
    ATTEMPT_COMPLETED = "ATTEMPT_COMPLETED"
    ATTEMPT_FAILED = "ATTEMPT_FAILED"
    ATTEMPT_REQUEUED = "ATTEMPT_REQUEUED"
    ATTEMPT_DEAD_LETTERED = "ATTEMPT_DEAD_LETTERED"
    MANUAL_RECOVERY = "MANUAL_RECOVERY"
    STEP_CHECKPOINTED = "STEP_CHECKPOINTED"


ALLOWED_JOB_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.NOT_STARTED: frozenset({JobState.QUEUED, JobState.CANCELLED}),
    JobState.QUEUED: frozenset(
        {
            JobState.RUNNING,
            JobState.PAUSED,
            JobState.FAILED,
            JobState.DEAD_LETTERED,
            JobState.CANCELLED,
        }
    ),
    JobState.RUNNING: frozenset(
        {
            JobState.AWAITING_HUMAN,
            JobState.COMPLETED,
            JobState.FAILED,
            JobState.PAUSED,
            JobState.CANCELLED,
        }
    ),
    JobState.AWAITING_HUMAN: frozenset(
        {JobState.RUNNING, JobState.FAILED, JobState.PAUSED, JobState.CANCELLED}
    ),
    JobState.PAUSED: frozenset(
        {JobState.QUEUED, JobState.RUNNING, JobState.AWAITING_HUMAN, JobState.CANCELLED}
    ),
    JobState.FAILED: frozenset({JobState.QUEUED, JobState.DEAD_LETTERED, JobState.CANCELLED}),
    JobState.DEAD_LETTERED: frozenset({JobState.QUEUED, JobState.CANCELLED}),
    JobState.COMPLETED: frozenset(),
    JobState.CANCELLED: frozenset(),
}


def validate_job_transition(current: JobState, target: JobState) -> None:
    if target not in ALLOWED_JOB_TRANSITIONS[current]:
        raise InvalidStateTransitionError(
            f"job cannot transition from {current.value} to {target.value}"
        )


@dataclass(frozen=True, slots=True)
class WorkflowRun:
    id: UUID
    organization_id: UUID
    review_id: UUID
    workflow_name: str
    workflow_version: str
    idempotency_key: str
    state: WorkflowRunState
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowJob:
    id: UUID
    workflow_run_id: UUID
    organization_id: UUID
    review_id: UUID
    task_name: str
    task_version: str
    idempotency_key: str
    payload: dict[str, Any]
    state: JobState
    paused_from_state: JobState | None
    attempt: int
    created_at: datetime
    updated_at: datetime
    payload_schema: str = "workflow.generic"
    payload_version: int = 1
    max_attempts: int = 3
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    next_retry_at: datetime | None = None
    failure_class: FailureClass | None = None
    dead_lettered_at: datetime | None = None
    recovery_count: int = 0
    step_key: str | None = None
    step_order: int | None = None
    definition_hash: str | None = None


@dataclass(frozen=True, slots=True)
class JobEvent:
    id: UUID
    job_id: UUID
    sequence: int
    event_type: JobEventType
    from_state: JobState | None
    to_state: JobState
    actor_user_id: UUID | None
    reason: str | None
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class HumanCheckpoint:
    id: UUID
    job_id: UUID
    organization_id: UUID
    review_id: UUID
    state: CheckpointState
    request_message: str
    requested_by_user_id: UUID
    requested_at: datetime
    decision_note: str | None
    resolved_by_user_id: UUID | None
    resolved_at: datetime | None
