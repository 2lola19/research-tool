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

Critical future suites cover protocol immutability, deduplication, audit append-only behavior, provenance completeness, PRISMA counts, workflow transitions, and effect calculations.
