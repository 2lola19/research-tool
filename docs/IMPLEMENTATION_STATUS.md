# Implementation Status

Last updated: 2026-08-10

## Completed

- Repository architecture and contributor standards.
- Phase 0/1 scaffolding for FastAPI, SQLAlchemy/Alembic, Next.js, local providers, Docker Compose, and quality tooling.
- Architecture decisions for PostgreSQL, orchestration deferral/port, provenance separation, and modular-monolith boundaries.
- Frontend dependency lock generated and local Python/frontend development dependencies installed.
- Backend quality gates pass: Ruff lint/format, strict mypy, and 20 pytest tests with 87.27% coverage.
- Frontend quality gates pass: ESLint, TypeScript, 2 Vitest tests, and the Next.js production build.
- Docker Compose configuration validated with Docker Compose 5.1.4.
- Alembic migration graph resolves to the foundation head `20260809_0001`.

## Environment-blocked validation

- `ENVIRONMENT_BLOCKED`: live Docker Compose execution is not an application failure. Docker Desktop 4.80.0 starts its WSL guest but stalls while opening containerd metadata, so PostgreSQL health, live Alembic execution, backend/worker/frontend container health, inter-service communication, and the live-stack smoke path cannot currently be exercised.
- Docker/WSL diagnostics preserved all existing projects and data. No Docker reset, prune, volume/image deletion, distribution unregister, reinstall, or security-policy change was performed.
- Continue repository-local development and quality-gate validation without Docker until the host environment is repaired separately.

## Planned

- Phase 2 identity, organizations, memberships, roles, and tenant-isolation tests.
- Phase 3 reviews and review-membership dashboard shell.
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

## Technical debt

- Worker contains only the lifecycle foundation until persisted jobs land in Phase 4.
- PostgreSQL-specific integration tests will be expanded with the first domain migration.

## External dependencies / future APIs

See `docs/API_REQUIREMENTS.md` and `docs/OPEN_SOURCE_COMPONENTS.md`.
