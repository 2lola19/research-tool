# ADR-030: Durable Local Workflow Job Execution

- Status: Accepted
- Date: 2026-08-19

## Context

The persisted workflow state machine already records tenant-scoped jobs, transitions, and ordered
events, but a worker could not claim work safely or recover from a crashed process. A durable local
execution layer is required before evaluating Temporal or another runtime adapter.

## Decision

Keep the existing `Orchestrator` and workflow domain contracts vendor-neutral. Add explicit payload
schema/version metadata and bounded attempt limits to each job. Persist each claim as a
`workflow_job_attempts` row with a worker identity, lease token, expiry, heartbeat, result/failure
snapshot, and terminal attempt state. Persist worker health separately in `workflow_workers`.

Claims are tenant/review scoped, capacity bounded, idempotent through the existing job key, and
filtered through an allowlisted handler registry. Claim, heartbeat, completion, failure, requeue,
and lease-expiry recovery append operational `JobEvent` records. The deterministic local runner
executes registered handlers only; scientific services remain responsible for scientific writes,
provenance, and human checkpoints.

## Consequences

- A worker cannot claim an unsupported task or payload schema, and API claim responses expose only
  the handler's redacted payload allowlist.
- Expired leases become failed attempts and are requeued only while the job's bounded attempt limit
  remains; a later recovery phase may add richer retry/backoff and workflow resume semantics.
- Worker health is operational metadata, not tenant scientific state. Job ownership and all job/
  attempt reads remain organization/Review scoped.
- The local `--once` runner and SQLAlchemy adapter provide deterministic offline behavior without
  Temporal, provider credentials, or a second scientific state machine.
