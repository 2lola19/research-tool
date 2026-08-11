# Testing

The quality pyramid uses unit tests for deterministic domain logic, API tests for transport/error contracts, repository tests against PostgreSQL, workflow tests for transitions/retries/idempotency, and focused frontend unit/build tests.

Run backend checks:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe backend workers
.\.venv\Scripts\pytest.exe
```

Run frontend checks from `frontend/`:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
```

Phase 2 includes negative tenant-isolation integration tests for cross-organization reads, writes, enumeration, identifier inference, invalid actor context, membership removal, role restrictions, ownership, and review assignment. The Alembic chain is also applied to a disposable SQLite database in the automated suite. PostgreSQL remains canonical and its database-specific execution gate is tracked as `ENVIRONMENT_BLOCKED` until the host Docker engine is available.

Review Projects adds tests for organization-unique metadata, archive/restore, member listing/removal, immediate project-access revocation, ownership transfer, and cross-tenant transfer rejection. Frontend tests assert that server-side review fetches always send both bearer identity and organization context.

Critical suites cover protocol immutability, audit append-only behavior, provenance completeness, workflow transitions, deterministic deduplication, and screening. Screening tests exercise blinded queues, immutable decisions, exclusion rationale, deterministic consensus/conflict outcomes, conflict adjudication, closure completeness, idempotent full-text progression, retained-versus-suppressed duplicate behavior, role restrictions, assignment ownership, and cross-tenant identifier non-enumeration.

Phase 10.5 tests exercise ordinary sequential allocation, scoped uniqueness, savepoint retry after a simulated concurrent winner, simulated concurrent workers, and rollback after exhausted retries. Phase 11 tests cover PDF signature and size validation, safe filenames, checksum duplicate rejection, unchanged object retrieval, tenant-scoped document access, parser fixture normalization and malformed output, processing failure state, warnings, evidence locations, approved-protocol full-text judgments, structured exclusion reasons, and viewer mutation denial. SQLite writer-lock limitations are not treated as PostgreSQL concurrency validation; the contention test uses a deterministic database-behavior simulation.

The PRISMA/export foundation tests database-derived record/report/Study distinctions, readiness
blockers, structured full-text exclusion reasons, immutable tenant-scoped snapshots, deterministic
byte rendering, CSV formula neutralization, valid XLSX archives, all four download formats,
manifests, checksums, prior-artifact preservation, role restrictions, tenant non-enumeration, and the
complete Alembic upgrade/downgrade chain. Deterministic effect calculations remain deferred.

Search Execution tests cover all structured source groups, strategy/translation and exact-query
retention, repeated execution history, terminal immutability, completed/partial/failed readiness,
provider/import reconciliation, file-import linkage, multiple discovery paths, pre-dedup PRISMA
counts, database/register versus other-method separation, stable JSON/XLSX documentation, raw
artifact checksum retrieval, cross-tenant/cross-review non-enumeration, role restrictions, and the
`20260811_0018` upgrade/downgrade chain.

Risk of Bias tests cover instrument normalization, domain/question order, instrument-defined choices,
deterministic suggestions, Study-design compatibility, independent assessor ownership and blindness,
agreement/conflict comparison, submitted-record immutability, current-revision comparison,
authorized adjudication, audit/provenance, and cross-tenant/cross-review non-enumeration. Study Family
tests cite protocol and results Documents in one Study and reject evidence linked only to another
Study. Export tests verify stable JSON/XLSX RoB sections, instrument hashes/versions, sheet ordering,
and `review-export-3`. Migration tests validate the complete `20260811_0019` SQLite upgrade and
downgrade chain; PostgreSQL-specific execution remains environment-blocked.
