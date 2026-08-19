from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from backend.app.core.errors import InvalidJobPayloadError
from backend.app.workflow.domain import WorkflowJob
from backend.app.workflow.execution_domain import (
    JobExecutionContext,
    JobHandlerRegistry,
    WorkerClaim,
    WorkerHealth,
    WorkerStatus,
    WorkflowJobAttempt,
    default_job_handler_registry,
    validate_result_snapshot,
)
from backend.app.workflow.execution_persistence import SqlAlchemyWorkflowExecutionRepository
from backend.app.workflow.recovery_domain import (
    FailureClass,
    ReconciliationReport,
    WorkflowStepCheckpoint,
)


class WorkflowExecutionService:
    def __init__(
        self,
        repository: SqlAlchemyWorkflowExecutionRepository,
        registry: JobHandlerRegistry | None = None,
    ) -> None:
        self._repository = repository
        self._registry = registry or default_job_handler_registry()

    @property
    def registry(self) -> JobHandlerRegistry:
        return self._registry

    async def register_worker(self, worker_id: str, capacity: int) -> WorkerHealth:
        self._validate_worker(worker_id, capacity)
        return await self._repository.register_worker(worker_id.strip(), capacity)

    async def heartbeat_worker(
        self,
        worker_id: str,
        *,
        active_jobs: int | None = None,
        status: WorkerStatus = WorkerStatus.HEALTHY,
    ) -> WorkerHealth:
        self._validate_worker_id(worker_id)
        return await self._repository.heartbeat_worker(
            worker_id.strip(), active_jobs=active_jobs, status=status
        )

    async def stop_worker(self, worker_id: str, last_error: str | None = None) -> WorkerHealth:
        self._validate_worker_id(worker_id)
        return await self._repository.stop_worker(worker_id.strip(), last_error)

    async def list_workers(self) -> list[WorkerHealth]:
        return await self._repository.list_workers()

    async def claim_next(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
        organization_id: UUID | None = None,
        review_id: UUID | None = None,
    ) -> WorkerClaim | None:
        self._validate_worker_id(worker_id)
        if not 5 <= lease_seconds <= 3_600:
            raise ValueError("lease seconds must be from 5 through 3600")
        signatures = self._registry.signatures()
        if not signatures:
            return None
        claimed = await self._repository.claim_next_job(
            worker_id=worker_id.strip(),
            lease_seconds=lease_seconds,
            organization_id=organization_id,
            review_id=review_id,
            task_signatures=signatures,
        )
        if claimed is None:
            return None
        job, attempt = claimed
        try:
            specification = self._registry.resolve(
                job.task_name,
                job.task_version,
                job.payload_schema,
                job.payload_version,
            )
            specification.validate_payload(job.payload)
        except InvalidJobPayloadError:
            await self._repository.fail_attempt(
                worker_id=worker_id.strip(),
                attempt_id=attempt.id,
                lease_token=attempt.lease_token,
                failure_code="INVALID_PAYLOAD",
                failure_message="job payload failed its registered schema",
                requeue=False,
            )
            return None
        return WorkerClaim(
            job=job,
            attempt=attempt,
            execution_payload=job.payload,
            redacted_payload=specification.redacted_payload(job.payload),
        )

    async def heartbeat_attempt(
        self,
        *,
        worker_id: str,
        attempt_id: UUID,
        lease_token: str,
        lease_seconds: int,
    ) -> WorkflowJobAttempt:
        if not 5 <= lease_seconds <= 3_600:
            raise ValueError("lease seconds must be from 5 through 3600")
        return await self._repository.heartbeat_attempt(
            worker_id=worker_id.strip(),
            attempt_id=attempt_id,
            lease_token=lease_token,
            lease_seconds=lease_seconds,
        )

    async def complete_attempt(
        self,
        *,
        worker_id: str,
        attempt_id: UUID,
        lease_token: str,
        result_snapshot: dict[str, Any],
    ) -> tuple[WorkflowJob, WorkflowJobAttempt]:
        validate_result_snapshot(result_snapshot)
        return await self._repository.complete_attempt(
            worker_id=worker_id.strip(),
            attempt_id=attempt_id,
            lease_token=lease_token,
            result_snapshot=result_snapshot,
        )

    async def fail_attempt(
        self,
        *,
        worker_id: str,
        attempt_id: UUID,
        lease_token: str,
        failure_code: str,
        failure_message: str,
        failure_class: FailureClass = FailureClass.UNKNOWN,
        requeue: bool | None = None,
    ) -> tuple[WorkflowJob, WorkflowJobAttempt]:
        if not failure_code.strip():
            raise ValueError("failure code cannot be empty")
        return await self._repository.fail_attempt(
            worker_id=worker_id.strip(),
            attempt_id=attempt_id,
            lease_token=lease_token,
            failure_code=failure_code.strip(),
            failure_message=failure_message.strip(),
            failure_class=failure_class,
            requeue=requeue,
        )

    async def requeue_job(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        reason: str,
        actor_user_id: UUID | None,
        idempotency_key: str | None = None,
        additional_attempts: int = 0,
    ) -> WorkflowJob:
        if not reason.strip():
            raise ValueError("requeue reason cannot be empty")
        return await self._repository.requeue_job(
            organization_id=organization_id,
            job_id=job_id,
            reason=reason.strip(),
            actor_user_id=actor_user_id,
            idempotency_key=idempotency_key,
            additional_attempts=additional_attempts,
        )

    async def resume_job(
        self,
        *,
        organization_id: UUID,
        job_id: UUID,
        idempotency_key: str,
        reason: str,
        actor_user_id: UUID | None,
    ) -> WorkflowJob:
        if not idempotency_key.strip():
            raise ValueError("resume idempotency key cannot be empty")
        if not reason.strip():
            raise ValueError("resume reason cannot be empty")
        return await self._repository.resume_job(
            organization_id=organization_id,
            job_id=job_id,
            idempotency_key=idempotency_key.strip(),
            actor_user_id=actor_user_id,
            reason=reason.strip(),
        )

    async def requeue_expired(self, limit: int = 100) -> int:
        if not 1 <= limit <= 1_000:
            raise ValueError("expired-attempt limit must be from 1 through 1000")
        return await self._repository.requeue_expired(limit)

    async def get_attempt(
        self, organization_id: UUID, attempt_id: UUID
    ) -> tuple[WorkflowJob, WorkflowJobAttempt] | None:
        return await self._repository.get_attempt(organization_id, attempt_id)

    async def get_job(self, organization_id: UUID, job_id: UUID) -> WorkflowJob | None:
        return await self._repository.get_job(organization_id, job_id)

    async def list_attempts(
        self, organization_id: UUID, review_id: UUID
    ) -> list[WorkflowJobAttempt]:
        return await self._repository.list_attempts(organization_id, review_id)

    async def list_step_checkpoints(
        self, organization_id: UUID, review_id: UUID
    ) -> list[WorkflowStepCheckpoint]:
        return await self._repository.list_step_checkpoints(organization_id, review_id)

    async def reconcile(self, organization_id: UUID, review_id: UUID) -> ReconciliationReport:
        return await self._repository.reconcile(organization_id, review_id)

    @staticmethod
    def _validate_worker_id(worker_id: str) -> None:
        if not worker_id.strip() or len(worker_id.strip()) > 160:
            raise ValueError("worker id must be from 1 through 160 characters")

    @classmethod
    def _validate_worker(cls, worker_id: str, capacity: int) -> None:
        cls._validate_worker_id(worker_id)
        if not 1 <= capacity <= 100:
            raise ValueError("worker capacity must be from 1 through 100")


class LocalWorkerRunner:
    """Deterministic local worker loop over the provider-neutral execution service."""

    def __init__(
        self,
        execution: WorkflowExecutionService,
        *,
        worker_id: str,
        max_concurrency: int = 1,
        lease_seconds: int = 60,
    ) -> None:
        if not 1 <= max_concurrency <= 100:
            raise ValueError("worker concurrency must be from 1 through 100")
        self._execution = execution
        self._worker_id = worker_id
        self._max_concurrency = max_concurrency
        self._lease_seconds = lease_seconds

    async def run_once(
        self,
        *,
        organization_id: UUID | None = None,
        review_id: UUID | None = None,
    ) -> int:
        await self._execution.register_worker(self._worker_id, self._max_concurrency)
        claims: list[WorkerClaim] = []
        for _ in range(self._max_concurrency):
            claim = await self._execution.claim_next(
                worker_id=self._worker_id,
                lease_seconds=self._lease_seconds,
                organization_id=organization_id,
                review_id=review_id,
            )
            if claim is None:
                break
            claims.append(claim)
        if not claims:
            return 0
        await asyncio.gather(*(self._execute_claim(claim) for claim in claims))
        return len(claims)

    async def _execute_claim(self, claim: WorkerClaim) -> None:
        specification = self._execution.registry.resolve(
            claim.job.task_name,
            claim.job.task_version,
            claim.job.payload_schema,
            claim.job.payload_version,
        )
        try:
            result = await specification.handler(
                JobExecutionContext(
                    job=claim.job,
                    attempt=claim.attempt,
                    payload=claim.execution_payload,
                )
            )
            await self._execution.complete_attempt(
                worker_id=self._worker_id,
                attempt_id=claim.attempt.id,
                lease_token=claim.attempt.lease_token,
                result_snapshot=result,
            )
        except Exception as exc:
            await self._execution.fail_attempt(
                worker_id=self._worker_id,
                attempt_id=claim.attempt.id,
                lease_token=claim.attempt.lease_token,
                failure_code=type(exc).__name__.upper()[:80],
                failure_message="worker handler failed; inspect the attempt and retry policy",
                failure_class=FailureClass.TRANSIENT,
                requeue=None,
            )
