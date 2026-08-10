# Implementation Status

Last updated: 2026-08-10

## Status by milestone

| Milestone | Status | Evidence and boundary |
|---|---|---|
| Foundation (Phases 0/1) | VERIFIED | Source-level backend/frontend gates pass; Docker live-stack execution remains environment-blocked. |
| Identity and multi-tenancy (Phase 2) | VERIFIED | Local SQLite integration tests cover authentication, membership revocation, tenant isolation, direct-object access, and role boundaries. |
| Review Projects (Phase 3) | VERIFIED | Project ownership, membership, archive/restore, transfer, and dashboard tests pass. |
| Workflow State Machine (Phase 4) | VERIFIED | Persisted state transitions, idempotency, ordered events, checkpoints, and control boundaries pass. |
| Provenance Ledger (Phase 5) | VERIFIED | Immutable prompt/AI/provenance/audit records, actor references, and scoped reads pass. |
| Protocol Engine (Phase 6) | VERIFIED | Structured immutable versions, final decisions, hashes, audit, and scientific provenance pass. |
| Search Strategy Domain (Phase 7) | VERIFIED | Canonical strategies, approved-protocol pinning, deterministic translators, replay, provenance, and audit pass. |
| Citation Import (Phase 8) | VERIFIED | RIS/BibTeX/CSV parsing, lossless batches, source records, idempotency, Article separation, and import provenance pass. |
| Deduplication (Phase 9) | VERIFIED | Versioned deterministic scans, reviewable decisions, non-destructive retention, provenance, audit, and screening suppression pass. |
| Screening Foundation (Phase 10) | VERIFIED | Blinded-only rounds, authorized assignments, immutable decisions, deterministic outcomes, adjudication, closure, progression, provenance, and audit pass. Unblinded rounds are explicitly deferred. |

## Validation evidence

- Backend: Ruff lint and format checks, strict mypy, and `pytest` pass: 99 tests, 96.10% coverage (configured threshold: 85%).
- Frontend: ESLint, TypeScript, Vitest (4 tests), and Next.js production build pass.
- Alembic reports one linear head at `20260810_0010`. A temporary SQLite database upgraded from foundation through Screening Foundation and downgraded step-by-step back to base successfully.
- The API router now derives its prefix from the application settings; a custom-prefix regression test passes.
- Consequential search, deduplication, and screening writes append audit events alongside their scientific provenance where applicable.

## Environment-blocked validation

- `ENVIRONMENT_BLOCKED`: Docker Compose live execution was not exercised. Docker Desktop/containerd startup remains unavailable on this host, so PostgreSQL health, PostgreSQL-specific migration behavior, container health, inter-service communication, and live-stack smoke tests remain unverified.
- No Docker reset, prune, volume/image deletion, distribution unregister, reinstall, or security-policy change was performed.
- SQLite is used only for local adapter/integration validation; PostgreSQL remains the canonical production database.

## Findings and residual risk

- CRITICAL: none found.
- HIGH: none found after targeted fixes.
- MEDIUM: immutable/versioned counters and screening round sequences use read-maximum-plus-one allocation protected by uniqueness constraints; concurrent callers may receive a retryable uniqueness failure rather than corrupting history. A database-native allocator/retry policy is deferred.
- LOW: the worker dispatch implementation remains a lifecycle shell; durable claiming/execution is deferred until workflow runtime work is scheduled.
- The screening foundation intentionally rejects `blinded=false` until an explicit reveal policy exists; this prevents a configuration flag from silently weakening reviewer confidentiality.

## Deferred and planned

- Next scoped milestone: Documents, extraction, and verification (Phase 11), after this checkpoint is accepted.
- Temporal server integration remains deferred behind the orchestration contract.
- GROBID, ASReview, external scholarly APIs, dedupe libraries, R/metafor, paid AI providers, and production identity/cloud deployment remain deferred. No post-Screening feature expansion was started in this recovery.

## Architecture decisions

- PostgreSQL is canonical; SQLite is permitted only for fast adapter and local integration tests.
- The platform remains a modular monolith with extractable service boundaries.
- Workflow state, scientific data, provenance, audit, and human checkpoints remain physically distinct.
- A local orchestration adapter is used before Temporal.
- Tenant actor context is resolved from active database membership on every request; authentication remains provider-pluggable.

## External dependencies / future APIs

See `docs/API_REQUIREMENTS.md` and `docs/OPEN_SOURCE_COMPONENTS.md`.
