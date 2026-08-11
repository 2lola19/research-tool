# Implementation Status

Last updated: 2026-08-11

## Status by milestone

| Milestone | Status | Evidence and boundary |
|---|---|---|
| Foundation (Phases 0/1) | VERIFIED | Source-level backend/frontend gates pass; Docker live-stack execution remains environment-blocked. |
| Identity and multi-tenancy (Phase 2) | VERIFIED | SQLite integration tests cover authentication, membership revocation, tenant isolation, direct-object access, and role boundaries. |
| Review Projects (Phase 3) | VERIFIED | Project ownership, membership, archive/restore, transfer, and dashboard tests pass. |
| Workflow State Machine (Phase 4) | VERIFIED | Persisted transitions, idempotency, ordered events, checkpoints, and control boundaries pass. |
| Provenance Ledger (Phase 5) | VERIFIED | Immutable prompt/AI/provenance/audit records, actor references, and scoped reads pass. |
| Protocol Engine (Phase 6) | VERIFIED | Structured immutable versions, decisions, hashes, audit, and provenance pass. |
| Search Strategy Domain (Phase 7) | VERIFIED | Canonical strategies, approved-protocol pinning, deterministic translators, replay, provenance, and audit pass. |
| Citation Import (Phase 8) | VERIFIED | RIS/BibTeX/CSV parsing, lossless batches, source records, idempotency, Article separation, and provenance pass. |
| Deduplication (Phase 9) | VERIFIED | Versioned deterministic scans, reviewable decisions, non-destructive retention, provenance, audit, and screening suppression pass. |
| Screening Foundation (Phase 10) | VERIFIED | Blinded-only rounds, authorized assignments, immutable decisions, deterministic outcomes, adjudication, closure, progression, provenance, and audit pass. |
| Concurrency Hardening (Phase 10.5) | VERIFIED | Five scoped sequential allocators use database uniqueness plus bounded savepoint retry; ordinary, uniqueness, retry, simulated contention, and rollback tests pass. |
| Document/Full-Text Foundation (Phase 11) | VERIFIED | Local-first PDF storage, checksum/provenance, retrieval states, canonical parser boundary, GROBID TEI fixture adapter, evidence locations, warnings, manual criterion screening, and tenant tests pass. Mature extraction remains deferred. |
| Study Families (Phase 12) | VERIFIED | Stable Review-scoped Study identity, non-destructive multi-Article links, role/method metadata, soft unlink history, provenance, audit, duplicate-link rejection, and tenant/review tests pass. |
| Versioned Extraction Schemas (Phase 13) | VERIFIED | Typed ordered field definitions, explicit allowed options, deterministic content hashes, immutable prior versions, review/tenant boundaries, and migration tests pass. |
| Provenance-First Manual Extraction (Phase 14) | VERIFIED | Study/schema-version pinned runs, typed values, explicit missingness, linked Article/Document evidence, resumable saves, audit/provenance, and permission tests pass. |
| Extraction Verification (Phase 15) | VERIFIED | Deterministic canonical comparison, evidence-aware conflicts, immutable original snapshots, authorized adjudication, verification state transitions, audit/provenance, and tenant tests pass. |

## Validation evidence

- Backend: Ruff lint and format checks, strict mypy, and pytest pass: 119 tests, 94.06% coverage (configured threshold: 85%).
- Frontend: ESLint, TypeScript, Vitest (4 tests), and Next.js production build pass; no frontend code changed in Phase 11.
- Alembic is linear through `20260811_0015`. A temporary SQLite database upgrades from foundation through extraction verification and downgrades to base.
- Focused document tests cover valid/invalid uploads, size and filename checks, PDF signature validation, exact checksum duplicates, unchanged content retrieval, parser fixtures/malformed output, processing failure, warnings, structured full-text decisions, evidence linkage, and tenant boundaries.

## Environment-blocked validation

- `ENVIRONMENT_BLOCKED`: Docker Compose live execution was not exercised. PostgreSQL health, PostgreSQL-specific migration behavior, container health, inter-service communication, and live GROBID execution remain unverified.
- No Docker recovery, reset, prune, volume/image deletion, distribution unregister, reinstall, or security-policy change was performed.
- SQLite is used only for local adapter/integration validation; PostgreSQL remains the canonical production database.

## Findings and residual risk

- CRITICAL: none found.
- HIGH: none found.
- MEDIUM resolved: all read-maximum-plus-one allocators now use scoped database uniqueness and bounded savepoint retries; PostgreSQL remains the production concurrency validation target.
- LOW: worker dispatch remains a lifecycle shell. Phase 11 keeps processing synchronous behind a parser/service boundary; durable claiming and retries remain deferred.
- Unblinded screening remains rejected until an explicit reveal policy exists.
- GROBID is evaluated and adapter-ready, but its live service and resource profile are not validated on this host.

## Deferred and planned

- Next phase: deterministic PRISMA/export foundations or a separately reviewed extraction-provider interface; do not add paid AI providers until the manual/verification foundation is reviewed.
- GROBID live deployment, ASReview, external scholarly APIs, R/metafor, paid AI providers, production identity, and cloud object storage remain deferred.

## Architecture decisions

- PostgreSQL is canonical; SQLite is permitted only for fast adapter and local integration tests.
- Workflow state, scientific data, provenance, audit, and human checkpoints remain physically distinct.
- Documents remain distinct from Articles and Studies and preserve multiple source files per Article.
- Original full-text bytes are immutable storage artifacts; parser output is separate, versioned by processing run, and referenced by evidence locations.
- Tenant actor context is resolved from active database membership on every request; storage keys never substitute for authorization.

See [ADR-012](adr/ADR-012-concurrent-sequential-allocation.md), [ADR-013](adr/ADR-013-document-processing-and-grobid-adapter.md), [ADR-014](adr/ADR-014-study-extraction-verification.md), [API_REQUIREMENTS.md](API_REQUIREMENTS.md), and [OPEN_SOURCE_COMPONENTS.md](OPEN_SOURCE_COMPONENTS.md).
