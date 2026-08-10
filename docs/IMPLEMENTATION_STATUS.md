# Implementation Status

Last updated: 2026-08-10

## Completed

- Repository architecture and contributor standards.
- Phase 0/1 scaffolding for FastAPI, SQLAlchemy/Alembic, Next.js, local providers, Docker Compose, and quality tooling.
- Architecture decisions for PostgreSQL, orchestration deferral/port, provenance separation, and modular-monolith boundaries.
- Frontend dependency lock generated and local Python/frontend development dependencies installed.
- Backend quality gates pass: Ruff lint/format, strict mypy, and 46 pytest tests with 90.57% coverage.
- Frontend quality gates pass: ESLint, TypeScript, 2 Vitest tests, and the Next.js production build.
- Docker Compose configuration validated with Docker Compose 5.1.4.
- Alembic migration graph resolves to `20260810_0002` and applies successfully to the available isolated SQLite migration environment.
- Phase 2 identity and multi-tenancy: users, organizations, soft-removable memberships, six organization roles, local credentials, signed short-lived bearer tokens, and database-resolved actor context.
- Tenant-owned review foundation: organization/creator/owner constraints, explicit review membership, tenant-scoped repository methods, and role/ownership authorization.
- Tenant security tests pass for same-organization reads/writes, cross-organization reads/writes/enumeration, malformed and unauthorized organization context, missing/removed membership, immediate revocation, role restrictions, ownership boundaries, assignment isolation, and unauthorized review access.
- ADR-005 records the local authentication abstraction and tenant authorization policy. A credential-safe local owner bootstrap command keeps development runnable without external APIs.

## Environment-blocked validation

- `ENVIRONMENT_BLOCKED`: live Docker Compose execution is not an application failure. Docker Desktop 4.80.0 starts its WSL guest but stalls while opening containerd metadata, so PostgreSQL health, live Alembic execution, backend/worker/frontend container health, inter-service communication, and the live-stack smoke path cannot currently be exercised.
- Docker/WSL diagnostics preserved all existing projects and data. No Docker reset, prune, volume/image deletion, distribution unregister, reinstall, or security-policy change was performed.
- Continue repository-local development and quality-gate validation without Docker until the host environment is repaired separately.

## Planned

- Phase 3 expands Review Projects beyond the Phase 2 ownership/access foundation and adds the review dashboard shell.
- Phase 4 persisted workflow orchestration and checkpoints.
- Phase 5 provenance/audit/AI-run foundation.
- Subsequent scientific domains follow `docs/ROADMAP.md`.

## Deferred

- Temporal server integration until Phase 4 has concrete workflow semantics.
- GROBID, ASReview, dedupe, OpenAlex/PyAlex, and R/metafor runtime integration until their domain phases.
- Paid AI providers and production cloud deployment.

## Known issues

- No source-level issues recorded.
- Live infrastructure verification remains `ENVIRONMENT_BLOCKED` by the host Docker Desktop/containerd startup failure described above.

## Architecture decisions

- PostgreSQL is canonical; SQLite is permitted only for fast adapter tests.
- Begin as a modular monolith with extractable service boundaries.
- Keep workflow state, scientific data, and provenance physically distinct.
- Use a local orchestration adapter before Temporal.
- Resolve tenant actor context from active database membership on every request; keep authentication provider-pluggable.

## Technical debt

- Worker contains only the lifecycle foundation until persisted jobs land in Phase 4.
- PostgreSQL-specific execution of migration `20260810_0002` remains part of the live Docker `ENVIRONMENT_BLOCKED` validation; the available SQLite migration and repository suites pass.

## External dependencies / future APIs

See `docs/API_REQUIREMENTS.md` and `docs/OPEN_SOURCE_COMPONENTS.md`.
