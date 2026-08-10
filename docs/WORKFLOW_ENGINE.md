# Workflow Engine

The application uses a port-and-adapter boundary named `Orchestrator`. Application services submit idempotent jobs and react to explicit job events; they do not contain vendor-specific Temporal calls.

Initial job states are `NOT_STARTED`, `QUEUED`, `RUNNING`, `AWAITING_HUMAN`, `COMPLETED`, `FAILED`, and `PAUSED`. Every submitted job has a job ID, workflow-run ID, idempotency key, task name, and task version.

Phase 1 supplies contracts and a process entry point. Phase 4 will add persisted workflow runs, transition rules, retry policies, human checkpoints, and a local adapter. Temporal integration is evaluated against those concrete behaviors before adoption.

Activities must be small, retry-safe, and idempotent. Scientific writes and workflow transitions occur through explicit transactions and append events for diagnosis.

