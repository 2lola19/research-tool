from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from backend.app.core.errors import InvalidJobPayloadError, ResourceNotFoundError
from backend.app.workflow.domain import WorkflowJob

MAX_JOB_PAYLOAD_BYTES = 64 * 1024
MAX_JOB_RESULT_BYTES = 64 * 1024


class JobAttemptState(StrEnum):
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class WorkerStatus(StrEnum):
    STARTING = "STARTING"
    HEALTHY = "HEALTHY"
    DRAINING = "DRAINING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class WorkflowJobAttempt:
    id: UUID
    job_id: UUID
    organization_id: UUID
    review_id: UUID
    attempt_number: int
    worker_id: str
    lease_token: str
    state: JobAttemptState
    claimed_at: datetime
    lease_expires_at: datetime
    heartbeat_at: datetime
    started_at: datetime
    finished_at: datetime | None
    result_snapshot: dict[str, Any] | None
    failure_code: str | None
    failure_message: str | None
    deadline_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class WorkerHealth:
    worker_id: str
    status: WorkerStatus
    capacity: int
    active_jobs: int
    started_at: datetime
    last_heartbeat_at: datetime
    stopped_at: datetime | None
    last_error: str | None


@dataclass(frozen=True, slots=True)
class JobExecutionContext:
    job: WorkflowJob
    attempt: WorkflowJobAttempt
    payload: dict[str, Any]


JobHandler = Callable[[JobExecutionContext], Awaitable[dict[str, Any]]]
JobSignature = tuple[str, str, str, int]


@dataclass(frozen=True, slots=True)
class JobHandlerSpec:
    task_name: str
    task_version: str
    payload_schema: str
    payload_version: int
    handler: JobHandler
    max_attempts: int = 3
    allowed_payload_keys: frozenset[str] = frozenset()

    @property
    def signature(self) -> JobSignature:
        return (
            self.task_name,
            self.task_version,
            self.payload_schema,
            self.payload_version,
        )

    def validate_payload(self, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            raise InvalidJobPayloadError("job payload must be a JSON object")
        unknown_keys = set(payload) - self.allowed_payload_keys
        if unknown_keys:
            raise InvalidJobPayloadError("job payload contains keys outside the registered schema")
        try:
            encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise InvalidJobPayloadError("job payload must contain JSON values") from exc
        if len(encoded.encode("utf-8")) > MAX_JOB_PAYLOAD_BYTES:
            raise InvalidJobPayloadError("job payload exceeds the bounded size limit")

    def redacted_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {key: payload[key] for key in sorted(self.allowed_payload_keys) if key in payload}


class JobHandlerRegistry:
    def __init__(self, specifications: tuple[JobHandlerSpec, ...] = ()) -> None:
        self._specifications: dict[JobSignature, JobHandlerSpec] = {}
        for specification in specifications:
            self.register(specification)

    def register(self, specification: JobHandlerSpec) -> None:
        if specification.payload_version < 1 or specification.max_attempts < 1:
            raise ValueError("job handler versions and attempts must be positive")
        if specification.signature in self._specifications:
            raise ValueError("duplicate job handler signature")
        self._specifications[specification.signature] = specification

    def resolve(
        self,
        task_name: str,
        task_version: str,
        payload_schema: str,
        payload_version: int,
    ) -> JobHandlerSpec:
        signature = (task_name, task_version, payload_schema, payload_version)
        try:
            return self._specifications[signature]
        except KeyError:
            raise ResourceNotFoundError("no worker handler is registered for this job") from None

    def signatures(self) -> tuple[JobSignature, ...]:
        return tuple(self._specifications)


@dataclass(frozen=True, slots=True)
class WorkerClaim:
    job: WorkflowJob
    attempt: WorkflowJobAttempt
    execution_payload: dict[str, Any]
    redacted_payload: dict[str, Any]


def validate_result_snapshot(result: dict[str, Any]) -> None:
    if not isinstance(result, dict):
        raise InvalidJobPayloadError("worker result must be a JSON object")
    try:
        encoded = json.dumps(result, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise InvalidJobPayloadError("worker result must contain JSON values") from exc
    if len(encoded.encode("utf-8")) > MAX_JOB_RESULT_BYTES:
        raise InvalidJobPayloadError("worker result exceeds the bounded size limit")


async def _deterministic_noop(context: JobExecutionContext) -> dict[str, Any]:
    return {
        "status": "completed",
        "task_name": context.job.task_name,
        "attempt_number": context.attempt.attempt_number,
    }


def default_job_handler_registry() -> JobHandlerRegistry:
    return JobHandlerRegistry(
        (
            JobHandlerSpec(
                task_name="workflow.noop",
                task_version="1",
                payload_schema="workflow.noop",
                payload_version=1,
                handler=_deterministic_noop,
            ),
        )
    )
