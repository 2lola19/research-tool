# Phase 36 — Collaboration, Assignment, Quality Control and Operational UX Hardening

Date: 2026-08-19
Status: COMPLETE / CHECKPOINTED

## Objective

Make human assignment, reviewer queues, blinded states, QC conflicts, workflow status, recovery
diagnostics, provenance navigation, and operational errors usable without moving authorization or
scientific authority into the browser.

## Implementation

- Added `GET /api/v1/screening/reviews/{review_id}/rounds`, backed by tenant-scoped repository and
  Review-access service methods with deterministic sequence ordering.
- Added a shared accessible Review workspace shell with skip navigation, authenticated sign-out,
  overview/screening navigation, loading skeleton, and retryable error boundary.
- Added server-rendered operations and screening workspaces with explicit ready/restricted/
  unavailable/not-requested states, live-read timestamps, stale reconciliation warnings, PRISMA
  readiness, workflow attempts/checkpoints/reconciliation, provenance metadata, safe report/AI
  links, role-aware member/assignment visibility, reviewer queues, and manager QC outcome views.
- Added authenticated server actions for assignment and conflict adjudication; they forward bounded
  form values to the canonical screening service and surface mutation failures without assuming a
  state change.
- Added typed frontend workspace API aggregation and Vitest coverage for organization headers,
  partial role restrictions, queue loading, and restricted QC data.
- Updated API, implementation, security, provenance, and testing documentation. No migration or
  new UI architectural ADR was required.

## Validation

- `ruff check .`: PASS.
- `ruff format --check .`: PASS — 374 files.
- `mypy backend workers`: PASS — 234 source files.
- `python -m compileall -q backend workers`: PASS.
- Frontend ESLint: PASS.
- Frontend TypeScript: PASS.
- Frontend Vitest: PASS — 10 tests.
- Frontend Next.js production build: PASS.
- Focused tenant boundary test: PASS — 1 test with `pytest --no-cov`.
- Full repository pytest: `ENVIRONMENT_BLOCKED_TIMEOUT_NO_OUTPUT_424_SECONDS`; no output was
  emitted, exact descendants were inspected and safely terminated, and no full-suite pass is
  claimed. A default-coverage run of the single focused test fails only because the repository
  85% threshold is intentionally a full-suite gate.
- Secret/credential/generated-artifact/scope audit: PASS.
- Scientific/security/provenance/tenant reviews: PASS.

## Local checkpoint

- Implementation commit: `55fc1404b5fb9b0103b32521ade4ffd0cc11058d`
- Message: `feat: harden collaboration, assignment, quality control and operational UX`
- `HEAD` verified at the implementation commit before metadata reconciliation; no
  `.git/index.lock` present.
- The worktree is clean after the metadata checkpoint; Phase 37 is the next resume point.
- No GitHub push or other prohibited Git operation was performed.
