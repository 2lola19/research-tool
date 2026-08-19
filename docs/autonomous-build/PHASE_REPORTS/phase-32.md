# Phase 32 Report — Workflow Resumability, Retry, and Operational Recovery

## Outcome

Phase 32 makes workflow execution resumable and recoverable across interruption without moving
scientific decisions into orchestration. Workflow jobs now carry bounded retry/backoff/timeout
policy, failure taxonomy, definition/step identity, and dead-letter metadata. Step progress and
resume/manual-recovery operations are durable and idempotent.

## Implementation surface

- Added immutable `WorkflowDefinition`/`WorkflowStepDefinition` contracts, deterministic definition
  hashes, structured `RetryPolicy`, and explicit failure classes.
- Added `DEAD_LETTERED` state, bounded retry scheduling, timeout deadlines distinct from worker
  leases, lease/timeout expiry classification, explicit additional-attempt recovery, and durable
  `RESUME`/`MANUAL_RETRY` idempotency records.
- Added normalized `workflow_step_checkpoints`, read-only reconciliation diagnostics, recovery API
  routes, migration `20260819_0033`, and the worker `--recover-expired` command.
- Added ADR-031 and updated workflow, API, database, domain, security, testing, provenance,
  implementation, roadmap, dependency, and autonomous-build documentation.

## Scientific, security, and provenance review

- PASS — retry, checkpoint, recovery, and reconciliation records remain operational workflow data;
  they are not Articles, Studies, evidence values, scientific judgments, reports, or human
  checkpoint decisions.
- PASS — automatic retries are limited to explicitly retryable transient/timeout/lease-loss
  classes. Permanent and unknown failures dead-letter; manual recovery requires authorization,
  reason, idempotency, and a bounded additional attempt budget when exhausted.
- PASS — definition hashes prevent silent version substitution; resume does not resolve
  `AWAITING_HUMAN`; reconciliation is read-only and never replays consequential writes.
- PASS — tenant/Review scoping and fail-closed authorization cover recovery, checkpoint, attempt,
  and reconciliation reads; no provider credential or new dependency was introduced.
- PASS — consequential scientific handlers remain responsible for existing domain-service,
  provenance, audit, idempotency, and human-acceptance boundaries.

## Validation

- PASS — repository `ruff check .`.
- PASS — repository `ruff format --check .` (353 files).
- PASS — `mypy backend workers` (224 source files).
- PASS — `python -m compileall -q backend workers tests`.
- PASS — focused unit/worker/workflow/recovery tests (14 tests).
- PASS — `tests/integration/test_workflow_execution.py` (5 tests).
- PASS — existing workflow tenant-compatibility subset (4 tests; combined focused run 9 tests).
- PASS — `tests/integration/test_migrations.py` upgraded and downgraded through `20260819_0033`.
- ENVIRONMENT_BLOCKED — full `pytest -q` produced no output for 364 seconds. Exact pytest
  descendants were inspected and terminated safely; no assertion result is claimed.
- PASS — secret/credential and generated-artifact audits found no intended-file violations.

## Checkpoint

Implementation, reviews, focused gates, and the documented full-suite environment limitation are
complete. The validated local Phase 32 implementation checkpoint exists at
`b5039cd456caf2f36e10716c29aaccde4e3fa175` with message `feat: add resumable workflow recovery
and retry orchestration`. The execution state and phase report were reconciled in the follow-on
metadata checkpoint. No GitHub operation is authorized or performed.
