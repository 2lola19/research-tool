# ADR-006: Persist Workflow State Before Adopting an Orchestrator Runtime

- Status: Accepted
- Date: 2026-08-10

## Context

Research workflows require durable identity, retry-safe submission, explicit state changes, and human decisions. Adopting a vendor runtime before these application semantics exist would place business rules inside infrastructure-specific code.

Workflow history also serves a different purpose from scientific provenance: it explains operational execution, while provenance explains the evidence and method behind a scientific result.

## Decision

Persist tenant- and review-scoped workflow runs, versioned jobs, ordered job events, and human checkpoints in the application database. Enforce a deterministic transition table in the domain layer. Bind idempotency keys to their original task or workflow input and reject conflicting reuse.

Paused jobs remember their prior state and may resume only to it. Completed and cancelled jobs are terminal. Human checkpoint requests move a running job to `AWAITING_HUMAN`; approval resumes it and rejection fails it. The decision record and state changes commit in one request transaction.

The application service depends on a repository protocol and the existing orchestration contract. No Temporal or other runtime SDK enters the domain or API layers.

## Consequences

- Workflow resources inherit the review's organization boundary and cannot be queried by unscoped identifier.
- Event rows are append-only through application APIs and carry a monotonic per-job sequence.
- Operational payloads may use JSON, but scientific evidence and outcomes must use their dedicated structured stores.
- A future runtime adapter must preserve these state, idempotency, checkpoint, and tenant-isolation semantics.
