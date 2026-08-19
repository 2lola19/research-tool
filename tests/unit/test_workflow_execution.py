from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

import pytest

from backend.app.core.errors import InvalidJobPayloadError
from backend.app.orchestration.contracts import JobState
from backend.app.workflow.domain import WorkflowJob
from backend.app.workflow.execution_domain import (
    JobAttemptState,
    JobExecutionContext,
    JobHandlerRegistry,
    JobHandlerSpec,
    WorkerClaim,
    WorkflowJobAttempt,
)
from backend.app.workflow.execution_service import LocalWorkerRunner, WorkflowExecutionService


def _job() -> WorkflowJob:
    now = datetime.now(UTC)
    organization_id = uuid4()
    return WorkflowJob(
        id=uuid4(),
        workflow_run_id=uuid4(),
        organization_id=organization_id,
        review_id=uuid4(),
        task_name="fixture.task",
        task_version="1",
        idempotency_key="fixture-job",
        payload={"safe": "value", "secret": "must not be serialized"},
        state=JobState.RUNNING,
        paused_from_state=None,
        attempt=1,
        created_at=now,
        updated_at=now,
        payload_schema="fixture.task",
        payload_version=1,
        max_attempts=2,
    )


def _attempt(job: WorkflowJob) -> WorkflowJobAttempt:
    now = datetime.now(UTC)
    return WorkflowJobAttempt(
        id=uuid4(),
        job_id=job.id,
        organization_id=job.organization_id,
        review_id=job.review_id,
        attempt_number=1,
        worker_id="worker-test",
        lease_token="lease-token-with-enough-entropy",
        state=JobAttemptState.CLAIMED,
        claimed_at=now,
        lease_expires_at=now + timedelta(minutes=1),
        heartbeat_at=now,
        started_at=now,
        finished_at=None,
        result_snapshot=None,
        failure_code=None,
        failure_message=None,
    )


def test_handler_registry_requires_exact_payload_schema_and_redacts_unknown_fields() -> None:
    async def handler(_: JobExecutionContext) -> dict[str, Any]:
        return {"ok": True}

    registry = JobHandlerRegistry(
        (
            JobHandlerSpec(
                task_name="fixture.task",
                task_version="1",
                payload_schema="fixture.task",
                payload_version=1,
                handler=handler,
                allowed_payload_keys=frozenset({"safe"}),
            ),
        )
    )
    specification = registry.resolve("fixture.task", "1", "fixture.task", 1)
    with pytest.raises(InvalidJobPayloadError):
        specification.validate_payload(_job().payload)
    assert specification.redacted_payload(_job().payload) == {"safe": "value"}


@pytest.mark.asyncio
async def test_local_runner_completes_claimed_handler_with_bounded_capacity() -> None:
    completed: list[dict[str, Any]] = []
    claims = [_attempt(_job())]

    async def handler(context: JobExecutionContext) -> dict[str, Any]:
        return {"attempt": context.attempt.attempt_number}

    registry = JobHandlerRegistry(
        (
            JobHandlerSpec(
                task_name="fixture.task",
                task_version="1",
                payload_schema="fixture.task",
                payload_version=1,
                handler=handler,
                allowed_payload_keys=frozenset({"safe", "secret"}),
            ),
        )
    )

    class FakeExecution:
        def __init__(self) -> None:
            self.registry = registry

        async def register_worker(self, worker_id: str, capacity: int) -> None:
            assert worker_id == "worker-test"
            assert capacity == 1

        async def claim_next(self, **_: Any) -> WorkerClaim | None:
            if not claims:
                return None
            attempt = claims.pop()
            job = _job()
            return WorkerClaim(job, attempt, job.payload, {"safe": "value"})

        async def complete_attempt(self, **kwargs: Any) -> None:
            completed.append(kwargs["result_snapshot"])

        async def fail_attempt(self, **_: Any) -> None:
            raise AssertionError("the successful fixture handler must not fail")

    runner = LocalWorkerRunner(
        cast(WorkflowExecutionService, FakeExecution()),
        worker_id="worker-test",
        max_concurrency=1,
    )
    assert await runner.run_once() == 1
    assert completed == [{"attempt": 1}]
