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

Critical suites cover protocol immutability, audit append-only behavior, provenance completeness, workflow transitions, deterministic deduplication, and screening. Screening tests exercise blinded queues, immutable decisions, exclusion rationale, deterministic consensus/conflict outcomes, conflict adjudication, closure completeness, idempotent full-text progression, retained-versus-suppressed duplicate behavior, role restrictions, assignment ownership, and cross-tenant identifier non-enumeration. Future suites add PRISMA counts and deterministic effect calculations as those domains land.
