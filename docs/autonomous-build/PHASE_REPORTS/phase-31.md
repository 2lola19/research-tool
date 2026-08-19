# Phase 31 Report — Durable Background Jobs and Worker Execution

## Outcome

Phase 31 turns the persisted workflow lifecycle shell into a durable, claimable local worker
contract. Workflow jobs now carry explicit payload schema/version and bounded attempt metadata.
Claims persist tenant/Review-scoped attempts with unique lease capabilities, expiry, heartbeats,
bounded result/failure snapshots, and operational event history. Worker health and capacity remain
separate from workflow and scientific state.

## Implementation surface

- Added exact task/version/payload-schema handler registry, deterministic payload/result bounds,
  allowlisted claim redaction, local `--once` runner, and a provider-neutral SQLAlchemy orchestrator.
- Added `workflow_job_attempts` and `workflow_workers`, linear migration `20260819_0032`, lease
  claim/heartbeat/complete/fail/requeue/expiry recovery, worker health, and API routes.
- Extended workflow submission/API/domain contracts with payload schema/version and max attempts;
  preserved existing state-transition, idempotency, pause/resume, checkpoint, and event semantics.
- Added ADR-030 and updated workflow, API, database, domain, security, testing, provenance,
  implementation, roadmap, dependency, and autonomous-build documentation.

## Scientific, security, and provenance review

- PASS — worker state and attempts are operational workflow records, not Articles, Studies, evidence
  values, scientific judgments, report artifacts, or human checkpoint decisions.
- PASS — claims require exact registered handlers, bounded capacity, tenant/Review scope, and active
  leases; claim responses redact payloads and ordinary attempt history withholds lease tokens.
- PASS — operational events do not substitute for scientific provenance. Future scientific handlers
  must call existing domain services and provenance/audit boundaries for consequential writes.
- PASS — no provider credentials, Temporal SDK, arbitrary retrieval, autonomous acceptance, or new
  scientific calculation authority was introduced.

## Validation

- PASS — repository `ruff check .`.
- PASS — repository `ruff format --check .` (349 files).
- PASS — `mypy backend workers` (222 source files).
- PASS — `python -m compileall -q backend workers tests`.
- PASS — focused unit/worker/workflow tests (12 tests).
- PASS — `tests/integration/test_workflow_execution.py` (3 tests).
- PASS — existing workflow tenant-compatibility subset (4 tests).
- PASS — `tests/integration/test_migrations.py` through `20260819_0032` (SQLite upgrade/downgrade).
- ENVIRONMENT_BLOCKED — full `pytest -q` produced no output for 364 seconds. Exact pytest
  processes were inspected and terminated; no assertion result is claimed.
- PASS — secret/credential and generated-artifact audits found no intended-file violations.

## Checkpoint

Implementation and required reviews are complete. The validated local Phase 31 implementation
checkpoint exists at `65de1a90ffbc81f3ed3ca1ac5f4ba030648f76d9` with message `feat: add durable
background jobs and worker execution`. The execution state and phase report were reconciled after
the scoped Git verification in the follow-on metadata checkpoint. No GitHub operation is
authorized or performed.
