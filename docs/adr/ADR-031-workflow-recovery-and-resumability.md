# ADR-031: Versioned Workflow Recovery and Resumability

Status: accepted for the V1 local orchestration boundary

## Context

Phase 31 made workflow jobs claimable with durable attempts and leases. A lease alone does not
define safe retry behavior: a worker can time out, a process can disappear after a claim, a
workflow definition can become stale, or a controller can pause and resume the same job more than
once. Review workflows also need durable step progress without hiding scientific state in an
opaque workflow blob.

## Decision

- Workflow definitions are explicit, immutable name/version contracts. Their canonical step
  identity, task versions, payload schema versions, retry policy, and human-checkpoint boundary
  produce a deterministic definition hash. A registry resolves exact versions; it never silently
  substitutes a newer definition.
- Retry policy is structured data with bounded attempts, exponential backoff capped by a maximum,
  timeout, and an allowlist of retryable failure classes. Permanent and unknown failures are not
  automatically replayed. Lease loss and timeout are distinct operational failure classes.
- Jobs may be `DEAD_LETTERED` after automatic retry exhaustion or a non-retryable failure. A
  controller must issue an auditable, idempotent manual recovery operation and may explicitly add a
  bounded attempt budget before requeueing an exhausted job.
- Step checkpoints are normalized, tenant/review-scoped records keyed by workflow run and step.
  They retain state, version, definition hash, output digest, and failure class. They are
  operational progress records, not Article, Study, evidence, analysis, or human scientific
  decisions.
- Resume and manual recovery use durable idempotency keys. Repeating an operation returns the
  existing result and never replays a consequential write. Pause/resume remains explicit, and an
  `AWAITING_HUMAN` job is never silently resumed by reconciliation.
- Reconciliation is read-only diagnostics over job/attempt/checkpoint invariants. Lease/timeout
  recovery is explicit and bounded; no cloud workflow runtime or production Temporal operation is
  introduced.

## Consequences

The schema gains structured retry metadata, step checkpoints, recovery-operation history, and
attempt deadlines. The local worker can run an explicit `--recover-expired` command. API recovery
operations require the same tenant/review authorization as workflow control. Scientific handlers
remain provider-neutral and must use their existing domain-service, provenance, audit, and human
acceptance boundaries.

## Rejected alternatives

- Replaying every failed job: this could repeat consequential scientific writes.
- Storing a serialized workflow state blob: it would hide version, tenant, and provenance
  invariants.
- Silently migrating a run to the newest workflow definition: it would make resume non-deterministic
  and could invalidate scientific assumptions.
- Making live Temporal/cloud infrastructure a V1 prerequisite: the local contract is testable
  without paid or unavailable infrastructure.
