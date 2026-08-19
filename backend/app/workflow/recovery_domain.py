from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from backend.app.core.errors import (
    InvalidJobPayloadError,
    ResourceNotFoundError,
    StaleWorkflowDefinitionError,
)


class FailureClass(StrEnum):
    TRANSIENT = "TRANSIENT"
    TIMEOUT = "TIMEOUT"
    LEASE_LOST = "LEASE_LOST"
    PERMANENT = "PERMANENT"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class WorkflowStepState(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    AWAITING_HUMAN = "AWAITING_HUMAN"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DEAD_LETTERED = "DEAD_LETTERED"
    CANCELLED = "CANCELLED"


class RecoveryOperationType(StrEnum):
    RESUME = "RESUME"
    MANUAL_RETRY = "MANUAL_RETRY"


class ReconciliationSeverity(StrEnum):
    WARNING = "WARNING"
    ERROR = "ERROR"


_DEFAULT_RETRYABLE_FAILURES = frozenset(
    {FailureClass.TRANSIENT, FailureClass.TIMEOUT, FailureClass.LEASE_LOST}
)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: int = 0
    max_backoff_seconds: int = 300
    timeout_seconds: int = 300
    retryable_failure_classes: frozenset[FailureClass] = field(
        default_factory=lambda: _DEFAULT_RETRYABLE_FAILURES
    )

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 100:
            raise ValueError("retry policy attempts must be from 1 through 100")
        if not 0 <= self.backoff_seconds <= 86_400:
            raise ValueError("retry policy backoff must be from 0 through 86400 seconds")
        if not self.backoff_seconds <= self.max_backoff_seconds <= 86_400:
            raise ValueError("retry policy maximum backoff is invalid")
        if not 5 <= self.timeout_seconds <= 86_400:
            raise ValueError("retry policy timeout must be from 5 through 86400 seconds")

    def should_retry(self, failure_class: FailureClass, attempt_number: int) -> bool:
        return (
            attempt_number < self.max_attempts and failure_class in self.retryable_failure_classes
        )

    def delay_for_attempt(self, attempt_number: int) -> int:
        if self.backoff_seconds == 0:
            return 0
        exponent = min(max(attempt_number - 1, 0), 10)
        return int(min(self.max_backoff_seconds, self.backoff_seconds * (2**exponent)))

    def to_json(self) -> dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "backoff_seconds": self.backoff_seconds,
            "max_backoff_seconds": self.max_backoff_seconds,
            "timeout_seconds": self.timeout_seconds,
            "retryable_failure_classes": sorted(
                failure_class.value for failure_class in self.retryable_failure_classes
            ),
        }

    @classmethod
    def from_json(
        cls,
        value: dict[str, Any] | None,
        *,
        fallback_max_attempts: int = 3,
        fallback_timeout_seconds: int = 300,
    ) -> RetryPolicy:
        if not value:
            return cls(
                max_attempts=fallback_max_attempts,
                timeout_seconds=fallback_timeout_seconds,
            )
        if not isinstance(value, dict):
            raise InvalidJobPayloadError("retry policy must be a JSON object")
        try:
            failure_classes = frozenset(
                FailureClass(item)
                for item in value.get(
                    "retryable_failure_classes",
                    [failure_class.value for failure_class in _DEFAULT_RETRYABLE_FAILURES],
                )
            )
            return cls(
                max_attempts=int(value.get("max_attempts", fallback_max_attempts)),
                backoff_seconds=int(value.get("backoff_seconds", 0)),
                max_backoff_seconds=int(value.get("max_backoff_seconds", 300)),
                timeout_seconds=int(value.get("timeout_seconds", fallback_timeout_seconds)),
                retryable_failure_classes=failure_classes,
            )
        except (TypeError, ValueError) as exc:
            raise InvalidJobPayloadError("retry policy contains invalid values") from exc


@dataclass(frozen=True, slots=True)
class WorkflowStepDefinition:
    step_key: str
    step_order: int
    task_name: str
    task_version: str
    payload_schema: str
    payload_version: int
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    requires_human_checkpoint: bool = False

    def __post_init__(self) -> None:
        if not self.step_key.strip() or len(self.step_key) > 120:
            raise ValueError("workflow step key must be from 1 through 120 characters")
        if self.step_order < 0:
            raise ValueError("workflow step order cannot be negative")
        if not self.task_name.strip() or not self.task_version.strip():
            raise ValueError("workflow step task identity cannot be empty")
        if self.payload_version < 1:
            raise ValueError("workflow step payload version must be positive")


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    name: str
    version: str
    steps: tuple[WorkflowStepDefinition, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.version.strip():
            raise ValueError("workflow definition identity cannot be empty")
        keys = [step.step_key for step in self.steps]
        orders = [step.step_order for step in self.steps]
        if len(keys) != len(set(keys)) or len(orders) != len(set(orders)):
            raise ValueError("workflow definition steps must have unique keys and orders")

    @property
    def definition_hash(self) -> str:
        document = {
            "name": self.name,
            "version": self.version,
            "steps": [
                {
                    "step_key": step.step_key,
                    "step_order": step.step_order,
                    "task_name": step.task_name,
                    "task_version": step.task_version,
                    "payload_schema": step.payload_schema,
                    "payload_version": step.payload_version,
                    "retry_policy": step.retry_policy.to_json(),
                    "requires_human_checkpoint": step.requires_human_checkpoint,
                }
                for step in sorted(self.steps, key=lambda item: item.step_order)
            ],
        }
        encoded = json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def step(self, step_key: str) -> WorkflowStepDefinition:
        for step in self.steps:
            if step.step_key == step_key:
                return step
        raise ResourceNotFoundError("workflow step is not defined in this version")


class WorkflowDefinitionRegistry:
    """Exact, immutable workflow definitions selected by name and version."""

    def __init__(self, definitions: tuple[WorkflowDefinition, ...] = ()) -> None:
        self._definitions: dict[tuple[str, str], WorkflowDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: WorkflowDefinition) -> None:
        key = (definition.name, definition.version)
        if key in self._definitions:
            raise ValueError("workflow definition version is already registered")
        self._definitions[key] = definition

    def resolve(
        self,
        name: str,
        version: str,
        definition_hash: str | None = None,
    ) -> WorkflowDefinition:
        definition = self._definitions.get((name, version))
        if definition is None:
            raise ResourceNotFoundError("workflow definition version is not registered")
        if definition_hash is not None and definition.definition_hash != definition_hash:
            raise StaleWorkflowDefinitionError("workflow definition hash is stale")
        return definition

    def contains(self, name: str, version: str) -> bool:
        return (name, version) in self._definitions


@dataclass(frozen=True, slots=True)
class WorkflowStepCheckpoint:
    id: UUID
    workflow_run_id: UUID
    job_id: UUID | None
    organization_id: UUID
    review_id: UUID
    step_key: str
    step_order: int
    definition_hash: str | None
    state: WorkflowStepState
    checkpoint_version: int
    output_digest: str | None
    failure_class: FailureClass | None
    checkpointed_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowRecoveryOperation:
    id: UUID
    job_id: UUID
    organization_id: UUID
    review_id: UUID
    operation: RecoveryOperationType
    idempotency_key: str
    actor_user_id: UUID | None
    reason: str
    additional_attempts: int
    resulting_state: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ReconciliationIssue:
    code: str
    severity: ReconciliationSeverity
    job_id: UUID
    attempt_id: UUID | None
    message: str


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    organization_id: UUID
    review_id: UUID
    generated_at: datetime
    issues: tuple[ReconciliationIssue, ...]

    @property
    def healthy(self) -> bool:
        return not self.issues
