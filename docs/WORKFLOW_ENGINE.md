# Workflow Engine

The application uses a port-and-adapter boundary named `Orchestrator`. Application services submit idempotent jobs and react to explicit job events; they do not contain vendor-specific Temporal calls.

Job states are `NOT_STARTED`, `QUEUED`, `RUNNING`, `AWAITING_HUMAN`, `COMPLETED`, `FAILED`, `PAUSED`, and `CANCELLED`. Every submitted job has a job ID, workflow-run ID, tenant/review scope, idempotency key, task name, and task version.

The persisted local state machine supplies workflow runs, versioned jobs, deterministic transition rules, pause/resume memory, ordered append-only events, and separately modeled human checkpoints. Submission is retry-safe: replaying the same idempotency key and input returns the original resource, while changed input is rejected.

All repository lookups require organization scope. Application services also resolve review access before returning or changing workflow data. Reviewers with project access can observe job events; workflow control requires an authorized review controller. Cross-tenant job or checkpoint identifiers are indistinguishable from missing resources.

A human checkpoint can be requested only from `RUNNING`. The job moves to `AWAITING_HUMAN`; approval returns it to `RUNNING`, and rejection moves it to `FAILED`. Checkpoint records retain requester, resolver, notes, and timestamps. Workflow events diagnose execution and do not replace scientific provenance or audit history.

Temporal integration remains deferred and will be evaluated against these concrete semantics before adoption.

Activities must be small, retry-safe, and idempotent. Scientific writes and workflow transitions occur through explicit transactions and append events for diagnosis.

## Phase 31 durable execution

Jobs now carry an explicit payload schema/version and bounded maximum-attempt policy. A registered
local handler is the only task eligible for claiming. `workflow_job_attempts` records the worker,
lease token, expiry, heartbeat, result/failure snapshot, and terminal attempt state; worker health
is separate in `workflow_workers`.

Claims are tenant/review scoped and capacity bounded. Completion, failure, explicit requeue, and
lease-expiry recovery update the workflow job through the existing deterministic transition table and
append operational job events. API claim responses use the handler's allowlisted redacted payload;
raw operational payloads are never exposed in history or to the copilot. The local runner executes
the deterministic registry through `python -m workers.review_worker --once`. Scientific handlers
must call their existing domain services and carry their own provenance; this worker layer does not
make scientific decisions or accept proposals.
