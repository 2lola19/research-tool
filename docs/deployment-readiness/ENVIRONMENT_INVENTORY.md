# Deployment Readiness Environment Inventory

Inventory status: COMPLETE_WITH_EXTERNAL_GATES. Secret values are intentionally omitted.

## Classification vocabulary

`AVAILABLE` means the dependency/tool is present and exercised or ready for bounded validation.
`AVAILABLE_BUT_UNCONFIGURED` means present but no safe configuration/evidence is available.
`MISSING` means not installed or not implemented in this repository.
`ENVIRONMENT_BLOCKED` means an otherwise relevant check could not complete safely in this host.
`EXTERNAL_CREDENTIAL_REQUIRED` means a user/account-owned credential or institutional setup is
required and was not fabricated.

## Baseline

| Item | Result | Evidence |
|---|---|---|
| Repository | `C:\Users\USER\Documents\Reasearch Tool` | User-provided workspace |
| Expected baseline | `a4156e3` / full SHA recorded in `DEPLOYMENT_STATE.json` | `git log`, state |
| Branch/worktree | `master`; baseline was clean at `a4156e3`; scoped deployment-readiness changes are now in progress | `git status`, `VALIDATION_LOG.md` |
| V1 release classification | `READY_WITH_DOCUMENTED_LIMITATIONS` | `V1_RELEASE_REPORT.md` |
| V1 development scope | Complete; no Phase 39 | User program and V1 report |

## Runtime/tool versions

| Dependency | Version/status | Classification | Evidence |
|---|---|---|---|
| Windows | Windows 10 Pro, 10.0.19045 build 19045 | `AVAILABLE` | `Get-CimInstance Win32_OperatingSystem` |
| System Python | 3.14.5 | `AVAILABLE` | `python --version` |
| Repository `.venv` Python | 3.14.5; Alembic 1.19.1; psycopg 3.3.4 | `AVAILABLE` | `.venv` probes |
| Node.js | v24.16.0 | `AVAILABLE` | `node --version` |
| npm | 11.13.0 | `AVAILABLE` | `npm --version` |
| Docker Engine/Desktop | CLI/Engine 29.6.1; `docker version`, build, run, health, and `ps` passed; `docker info` timed out once | `AVAILABLE` | Non-destructive Docker probes |
| Docker Compose | v5.3.0 | `AVAILABLE` | `docker compose version` |
| PostgreSQL client tools (`psql`, `pg_dump`, `pg_restore`) | Not on host PATH; project PostgreSQL container provides `psql` | `MISSING` on host | `Get-Command`; container probe |
| Git | 2.55.0.windows.3 | `AVAILABLE` | `git --version` |
| `pip-audit` | Not installed/on PATH | `MISSING` | `Get-Command` / module probe |
| Trivy | Not installed/on PATH | `MISSING` | `Get-Command` |
| npm audit | npm 11.13.0; repository lockfile available; 0 vulnerabilities | `AVAILABLE` | `npm audit --omit=dev --audit-level=high` |
| Malware scanner (`clamscan`/`freshclam`) | Not installed/on PATH; no repository scanner adapter | `MISSING` / external gate | `Get-Command` and adapter review |

## Project services and ports

| Service | Definition | Expected port/endpoint | Intended scope | Status |
|---|---|---|---|---|
| PostgreSQL | `compose.yaml` `db` | 5432 | Disposable project-local DB only | Healthy; Alembic head 20260819_0036 |
| Alembic migration | `compose.yaml` `migrate` | N/A | One-shot project service | Applied successfully; exit 0 |
| FastAPI | `compose.yaml` `backend` | 8000; `/health/live`, `/health/ready`, `/health/metrics` | Project validation only | Healthy; 200 on all three |
| Python worker | `compose.yaml` `worker` | No public port | Project validation only | Healthy process probe; DB heartbeat inspected |
| Next.js | `compose.yaml` `frontend` | 3000; `/api/health` | Project validation only | Healthy; 200 |
| GROBID | No root Compose service | `.env.example` name `GROBID_URL` | External/disposable parser if available | `ENVIRONMENT_BLOCKED_GROBID` |
| S3-compatible storage | No root Compose service; local/fake adapter tests pass | Adapter boundary only | Existing disposable service only | `EXTERNAL_DEPLOYMENT_GATE` |
| Malware scanner | No repository service identified; host `clamscan`/`freshclam` absent | Adapter/deployment boundary | External gate unless safely available | `EXTERNAL_DEPLOYMENT_GATE` |
| Reverse proxy/TLS | No root service or disposable proxy | Deployment boundary | Operator checklist | `EXTERNAL_DEPLOYMENT_GATE` |

## Required environment variable names only

The following names are defined by `.env.example` or Compose. Values must never be copied here:

`APP_ENV`, `APP_LOG_LEVEL`, `APP_API_PREFIX`, `APP_CORS_ORIGINS`, `APP_SECURITY_HEADERS_ENABLED`,
`APP_METRICS_ENABLED`, `APP_RATE_LIMIT_ENABLED`, `APP_AUTH_RATE_LIMIT_REQUESTS`,
`APP_AUTH_RATE_LIMIT_WINDOW_SECONDS`, `DATABASE_URL`, `DATABASE_ECHO`,
`DATABASE_REQUIRE_MIGRATIONS`, `DATABASE_EXPECTED_REVISION`, `API_BASE_URL`, `AI_PROVIDER`,
`OBJECT_STORAGE_PROVIDER`, `LOCAL_STORAGE_PATH`, `NOTIFICATION_PROVIDER`,
`AUTHENTICATION_PROVIDER`, `LOCAL_AUTH_SECRET`, `LOCAL_AUTH_TOKEN_TTL_SECONDS`,
`LOCAL_ADMIN_EMAIL`, `LOCAL_ADMIN_PASSWORD`, `LOCAL_ADMIN_DISPLAY_NAME`,
`LOCAL_ORGANIZATION_NAME`, `LOCAL_ORGANIZATION_SLUG`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
`GEMINI_API_KEY`, `OPENALEX_MAILTO`, `GROBID_URL`, `TEMPORAL_ADDRESS`, `POSTGRES_DB`,
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `WORKER_POLL_INTERVAL_SECONDS`.

Configuration status will be recorded as present/absent by variable name only. Local development
defaults are not production configuration; local authentication is rejected outside development or
test, and production OIDC/secret-manager configuration remains an external gate.

## Configuration-name presence probe

No `.env`, `.env.local`, or `.env.production` file was present, and no required application
environment variable names were present in the host process environment. Compose development
defaults were used only for the named disposable stack; no value was copied into this inventory.

## Provider/configuration posture from repository inspection

| Boundary | Repository posture | Deployment implication |
|---|---|---|
| Database | PostgreSQL canonical; SQLite fast-test only | Live disposable PostgreSQL evidence required |
| Identity | Local HMAC development provider; no OIDC adapter in checkout | `EXTERNAL_CREDENTIAL_REQUIRED` / implementation gate |
| AI | Deterministic mock by default; paid providers opt-in | No live paid call without explicit authorization |
| Object storage | Atomic local provider and vendor-neutral S3 adapter | S3 service/credentials must be supplied externally |
| Parser | Fixture parser and GROBID adapter boundary | Live GROBID evidence requires available service |
| Malware | No scanner service identified | External deployment gate unless scanner is available |
| Rate limiting | Process-local authentication limiter | Shared/edge limiter required for multi-replica exposure |
| Observability | Structured logs, request/trace IDs, health, low-cardinality metrics | Verify endpoint exposure/redaction in target topology |

## Updates

Append dated results here after each inventory or environment change. Never add secret values,
tokens, database URLs containing credentials, object keys, raw documents, dumps, or provider payloads.

### 2026-08-19 — baseline and disposable runtime inventory

- Initial baseline was clean at `a4156e3`; current worktree changes are intentionally scoped to this
  deployment-readiness program and its validated deployment fixes.
- Unrelated Docker project `school-erp-staging` was observed and left untouched. The validation
  stack uses Compose project `research-tool-readiness` and only its named network/volumes.
- Docker build, project startup, PostgreSQL migration, API/frontend health, and worker process health
  are available. Final image rebuild, migration, health, frontend, worker, and focused quality gates
  passed. Host scanner/client-tool gaps and production configuration boundaries are recorded as
  external/environment gates in `BLOCKERS.md`.
