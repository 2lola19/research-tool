# AI-Native Systematic Review Platform

A local-first, production-oriented platform for reproducible systematic reviews and meta-analysis. The repository is intentionally organized around five pillars: workflow orchestration, specialized research engines, a structured evidence store, a provenance ledger, and explicit human checkpoints.

The current milestone is the verified Phase 0/1 foundation: FastAPI, SQLAlchemy/Alembic, PostgreSQL, a Next.js App Router frontend, provider contracts with local mocks, structured logging, health/readiness endpoints, Docker Compose, and automated quality checks.

## Quick start with Docker

1. Copy `.env.example` to `.env` if you need local overrides.
2. Run `docker compose up --build`.
3. Open <http://localhost:3000> for the web application and <http://localhost:8000/docs> for the API.

The database migration service runs before the API starts. PostgreSQL is exposed on port `5432` for local development.

## Native development

Requirements: Python 3.12-3.14, Node.js 22+, npm, and PostgreSQL 16+.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe backend.app.main:app --reload
```

In another terminal:

```powershell
Set-Location frontend
npm install
npm run dev
```

Run all local quality gates with `./scripts/check.ps1` after dependencies are installed.

## Repository map

- `backend/`: FastAPI application and domain/provider boundaries.
- `frontend/`: Next.js researcher interface.
- `workers/`: background worker entry points; durable implementation follows the orchestration contract.
- `services/`: integration boundaries for later standalone scientific services.
- `infrastructure/`: container and local infrastructure configuration.
- `tests/`: backend unit and API tests.
- `docs/`: product, architecture, security, workflow, provenance, and implementation ledgers.

Read [ARCHITECTURE.md](ARCHITECTURE.md), [AGENTS.md](AGENTS.md), and the relevant ADRs before changing core boundaries.

## Current scope

This is a foundation, not a scientific-feature demo. Identity, review projects, protocol versioning, citation processing, screening, extraction, PRISMA, and analysis are implemented in later phases tracked in `docs/IMPLEMENTATION_STATUS.md`.

