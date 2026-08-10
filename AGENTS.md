# Repository Instructions

This file is authoritative for automated contributors working in this repository.

## Before changing core systems

1. Read `ARCHITECTURE.md`.
2. Read the ADRs relevant to the change.
3. Read the applicable domain document under `docs/`.
4. Preserve the separation of workflow state, scientific data, and provenance.

## Engineering rules

- Work only inside this repository unless the user explicitly expands scope.
- Keep HTTP handlers thin; domain services and engines own behavior.
- Deterministic scientific operations must not be delegated to an LLM.
- Business logic depends on provider protocols, not vendor SDKs.
- Consequential scientific writes require provenance and append-only audit events.
- Approved protocol versions are immutable; create a new version for changes.
- Never collapse Study and Article into the same entity.
- Every tenant-owned query must be scoped by organization/review access.
- Use migrations for schema changes and update domain/database documentation.
- Add tests for behavior, tenant boundaries, state transitions, and scientific invariants.
- Never commit secrets, generated local data, or paid-provider credentials.
- Update `docs/IMPLEMENTATION_STATUS.md`, `docs/API_REQUIREMENTS.md`, and `docs/OPEN_SOURCE_COMPONENTS.md` when relevant.

## Quality gates

Backend changes: `ruff check .`, `ruff format --check .`, `mypy backend workers`, and `pytest`.

Frontend changes: `npm run lint`, `npm run typecheck`, `npm test`, and `npm run build`.

Container changes: validate `docker compose config` and exercise health checks when Docker is available.

Do not weaken a gate or remove a test to make a build pass. Fix the underlying issue or document a genuine environment blocker.

