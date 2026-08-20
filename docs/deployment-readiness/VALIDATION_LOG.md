# Deployment Readiness Validation Log

This log records deployment evidence only. V1 development evidence remains in
`V1_RELEASE_REPORT.md` and `docs/autonomous-build/VALIDATION_LOG.md`.

## 2026-08-19 — control-plane creation and baseline

- Program scope: deployment readiness and controlled-staging GO/NO-GO only. No Phase 39 or product
  feature work is authorized.
- Required V1 documents, architecture, security, testing, database, provenance, open-source,
  autonomous-build plan/state/log/blockers/recovery, Compose, Dockerfiles, environment template,
  deployment/operations docs, and ADR-035 were read.
- Expected baseline: `a4156e3`; exact local `HEAD` and worktree reconciliation are recorded in the
  next baseline entry before any environment mutation.
- Inherited V1 evidence: repository scientific/static/frontend/configuration gates pass; live
  PostgreSQL, Docker build/health, backup/restore, Python/image scanners, OIDC, external storage,
  malware scanning, shared rate limiting, TLS/proxy, and broad regression were not claimed.
- Result: `IN_PROGRESS`; no deployment gate is promoted to `PASS` from inherited fixture evidence.

## Evidence-entry template

For each stage, record:

- timestamp and current `HEAD`;
- exact bounded command or test selector (without secret values);
- target scope and disposable-resource ownership;
- tool/version and relevant exit status;
- result classification and evidence path/checksum where appropriate;
- process-tree/cleanup notes for a timeout;
- scientific, security, tenant, and provenance review impact;
- state-file update and next action.

## Stage entries

### 2026-08-19 — baseline reconciliation and inventory

- `git -c safe.directory=... status --short --branch`: baseline was clean on `master` at
  `a4156e32c969efcbf4363f02413b58dabf6d4dd1`; `origin/master` matched. No unrelated work was
  discarded. The current worktree contains only scoped deployment documentation/fixes and the
  optional PostgreSQL migration test.
- Required V1, architecture, security, testing, database, provenance, deployment, operations,
  Compose, Dockerfile, environment, ADR, and autonomous-build control-plane documents were read.
- Host inventory: Windows 10 Pro build 19045; Python 3.14.5; repository `.venv` Python 3.14.5;
  Node v24.16.0; npm 11.13.0; Git 2.55.0.windows.3; Docker Engine 29.6.1; Compose v5.3.0.
  `psql`, `pg_dump`, `pg_restore`, `pip-audit`, Trivy, and ClamAV commands were unavailable on
  the host. No secret values were printed or recorded.
- Docker `info` timed out once, but `docker version`, `docker ps`, project build, project startup,
  and project health operations succeeded. The unrelated `school-erp-staging` project was not
  touched.
- Result: baseline and inventory `PASS`; environment classification remains partial because host
  scanners/client tools and production credential boundaries are not present.

### 2026-08-19 — container validation

- `docker compose -p research-tool-readiness config --quiet`: `PASS`.
- Required images built successfully. The corrected backend image was built directly from
  `backend/Dockerfile` with exit 0; the frontend image was built directly from `frontend/Dockerfile`
  with exit 0. Image inspection confirmed intended non-root users and no source-secret layers.
- A disposable stack was started only under Compose project `research-tool-readiness`, creating only
  its project network and named volumes. `db`, `backend`, `worker`, and `frontend` are healthy.
- Deployment defects fixed during this gate: the worker no longer inherits an API HTTP probe and
  uses a process-level healthcheck; the frontend probe uses explicit IPv4 loopback so it does not
  report false unhealthy when `localhost` resolves to IPv6.
- API `GET /health/live`, `GET /health/ready`, and `GET /health/metrics` returned HTTP 200; frontend
  `/api/health` returned HTTP 200. Result: `PASS_WITH_FIXES`.

### 2026-08-19 — PostgreSQL migration and metadata validation

- Disposable PostgreSQL was reached through the named Compose `db` service; no customer or
  production data was used.
- The first live upgrade exposed two actual PostgreSQL portability failures: migrations `20260819_0033`
  and `20260819_0035` used SQLite-style batch rewrites that attempted to drop unique indexes still
  referenced by tenant-scoped foreign keys. The migrations were corrected with direct PostgreSQL
  column/check-constraint paths while retaining SQLite batch paths.
- Live migration was re-run from the existing disposable head and completed through the new
  deployment correction `20260819_0036` with exit 0. The correction adds the workflow
  `payload_version > 0` and bounded `max_attempts` checks already required by the ORM mapping.
- `alembic current`: `20260819_0036 (head)`. Host `.venv` `alembic check` against the live
  disposable PostgreSQL target: `No new upgrade operations detected`, exit 0. The check required
  importing reporting persistence mappings, migration-created indexes/checks, accurate legacy
  nullable timestamp metadata, and matching Risk-of-Bias FK delete policy.
- Focused SQLite migration/metadata tests: `.s`, PostgreSQL-specific optional hook skipped because
  no host test URL was supplied. The live disposable PostgreSQL migration is the authoritative
  target evidence and is not substituted by the skip.
- Result: PostgreSQL connectivity, full migration chain/head, and metadata validation `PASS`;
  bounded concurrency/schema/backup/tenant exercises remain in progress.

Subsequent entries must remain chronological and distinguish `PASS` from `ENVIRONMENT_BLOCKED`,
`EXTERNAL_CREDENTIAL_REQUIRED`, `EXTERNAL_DEPLOYMENT_GATE`, `TEST_FAILURE`, and `CHECKPOINT_PENDING`.

### 2026-08-19 - PostgreSQL concurrency, tenant, and workflow recovery

- The named project worker was stopped and restarted only around validation selectors; it returned
  healthy and no unrelated process was touched.
- `tests/integration/test_tenant_isolation.py` with the opt-in disposable
  `POSTGRES_TEST_DATABASE_URL`: PASS, 54 tests. The fixture uses the already migrated PostgreSQL
  schema and truncates only the explicitly supplied disposable database.
- `tests/integration/test_workflow_execution.py` with the same target: PASS, five workflow tests,
  including claim/heartbeat/completion, retry/dead-letter/manual recovery, idempotent resume, and
  scoped reconciliation.
- A bounded application-repository probe against eight live PostgreSQL jobs produced
  `POSTGRES_CONCURRENCY_PASS workers=4 claimed=4 unique=4 remaining_queued=4`; no duplicate claim
  occurred.
- A bounded lease probe produced
  `POSTGRES_LEASE_RECOVERY_PASS attempts=2 expired_then_completed=1 duplicate_canonical_records=0`.
  The uncompleted five-second lease expired, was requeued once, reclaimed once, and completed.
- Result: PostgreSQL concurrency, tenant isolation, workflow recovery, and provenance scoping
  `PASS`.

### 2026-08-19 - backup and disposable restore

- Using only the named disposable source database, custom-format `pg_dump` backups were created in
  the project DB container while the project worker was paused. No dump entered the repository.
- Backup `553abbd737582001a73a36298142e84668815ed8a6b403f0ad14d087ef30ef34` was 632116 bytes and
  restored to `research_tool_readiness_restore_20260819`: head 0036, four reviews, one workflow
  job, and four job events.
- After a focused live provenance fixture, backup
  `99ce38b53120b52b698790e68272c07de1ff2625504a9b53055890398cdd477d` was 632106 bytes and restored
  to `research_tool_readiness_restore_20260819_v3`: head 0036, four reviews, three audit events,
  one scientific-provenance record, two organizations, and nine memberships.
- The initial verification query used a nonexistent table name; the restore was already successful,
  the query was corrected to `scientific_provenance`, and the evidence was rerun successfully.
- Result: backup/restore `PASS_DISPOSABLE`; source was not overwritten and dumps were not committed.

### 2026-08-19 - storage, parser, identity, security, and observability

- Focused local boundary selector covering storage, parser, rate limiting, auth, health, metrics,
  and API security: PASS. Local/fake S3 behavior is not substituted for a live S3 service.
- `AUTH_CONFIG_FAIL_CLOSED_PASS local_auth_rejected_in_production=1 oidc_adapter_absent_is_explicit=1`.
  No OIDC credentials or provider account were created.
- No S3-compatible service, malware scanner, or GROBID service was available. Results are
  respectively `EXTERNAL_DEPLOYMENT_GATE`, `EXTERNAL_DEPLOYMENT_GATE`, and
  `ENVIRONMENT_BLOCKED_GROBID`.
- `npm audit --omit=dev --audit-level=high`: PASS, 0 vulnerabilities. `pip-audit`, Trivy, and
  ClamAV were unavailable; no result was fabricated. Names-only secret audit found zero candidate
  files and recent backend/worker log audit found zero audited secret-pattern findings.
- Final live `/health/live`, `/health/ready`, `/health/metrics`, and frontend `/api/health` all
  returned HTTP 200; all four named-stack services were healthy.
- Process-local rate-limit tests pass, but multi-replica global enforcement remains an external
  shared/edge limiter gate. TLS/reverse-proxy evidence likewise remains external because no safe
  disposable proxy topology was available.

### 2026-08-19 - frontend, regression, and final source validation

- Frontend `npm run lint`: PASS; `npm run typecheck`: PASS; `npm test`: PASS, 10 tests; `npm run
  build`: PASS. The prior invalid Vitest `--runInBand` invocation was corrected and is not a test
  failure.
- API/unit backend shard `pytest -q --no-cov tests/api tests/unit`: PASS. Migration selector
  `tests/integration/test_migrations.py tests/integration/test_postgresql_migrations.py`: PASS with
  the optional PostgreSQL hook skipped because the live PostgreSQL evidence was run separately.
- Full `pytest -q --no-cov tests/integration`: timed out at 904 seconds with no result. The exact
  pytest parent/child process pair was inspected and stopped. An integration-minus-tenant retry
  timed out at 604 seconds; its exact pair was likewise stopped. These are
  `ENVIRONMENT_BLOCKED` broad-regression results, not passes.
- Final `docker build -f backend/Dockerfile -t research-tool-readiness-backend:latest .`: PASS;
  the final source image was retagged for migration/worker, migration ran successfully, and
  backend/worker were force-recreated and became healthy.
- Final `ruff check .`, `ruff format --check .`, `mypy backend workers`, and compileall: PASS.
- Result: focused final regression and deployment gates pass; broad integration remains
  `ENVIRONMENT_BLOCKED`; final recommendation is `READY_WITH_EXTERNAL_GATES`.

### 2026-08-19 - durable GO/NO-GO boundary before local checkpoint

- Scientific, security, tenant, and provenance reviews are complete with the external limitations
  recorded in `BLOCKERS.md`, `SECURITY_REVIEW.md`, and `OPERATIONS_REHEARSAL.md`.
- `DEPLOYMENT_STATE.json` is set to `GO_NO_GO`, `READY_FOR_CHECKPOINT`, and `commit_pending=true`.
- The next action is the strict local Git checkpoint procedure. Until its SHA is recorded, the
  control-plane status is `COMPLETE_PENDING_LOCAL_CHECKPOINT` and the checkpoint state is
  `READY_FOR_CHECKPOINT`, not silently `CHECKPOINTED`.

### 2026-08-19 - local checkpoint recorded

- Strict pre-commit checks passed: current phase implementation and scientific/security/tenant/
  provenance reviews were complete; required gates were PASS or truthfully blocked; `git status`,
  unstaged diff inspection, `git diff --check`, names-only secret audit, staged-scope review,
  `git diff --cached --check`, and artifact/credential exclusion checks passed.
- Local commit created and verified:
  `208de49f8b16e6ef3b90104157876fd01b472831` - `fix: harden controlled deployment readiness`.
- Resulting worktree was clean and `master` was ahead of `origin/master` by one local commit. No
  push, remote change, release, reset, clean, ACL operation, or unrelated repository operation was
  performed.
- `DEPLOYMENT_STATE.json` now records `current_stage=COMPLETE`, `checkpoint_status=CHECKPOINTED`,
  `commit_pending=false`, and the checkpoint SHA. The final recommendation remains
  `READY_WITH_EXTERNAL_GATES`.

### 2026-08-20 - recovery reconciliation after local checkpoint

- Safe-directory Git reconciliation used only per-command `safe.directory` overrides: `HEAD` is
  `476ad71445855f00edcb84f741d25d6dbdee621b` (`docs: record deployment readiness checkpoint`),
  the recorded implementation checkpoint `208de49f8b16e6ef3b90104157876fd01b472831` is an
  ancestor, `master` is ahead of `origin/master` by two local commits, and the worktree is clean.
  No GitHub, remote, ACL, reset, clean, or unrelated-repository operation occurred.
- Docker Engine 29.6.1 / Docker Desktop 4.80.0 remained available. The explicitly named
  `research-tool-readiness` project contained only its expected network and PostgreSQL/object-data
  volumes; `docker compose -p research-tool-readiness config --quiet` passed.
- The existing one-shot migration container was an historical pre-fix attempt whose recorded exit
  was 1 at migration `0033` due to the already documented PostgreSQL FK/index dependency. It was
  reconciled without resetting or overwriting the database by running
  `docker compose -p research-tool-readiness up --build --no-deps migrate` from the current source;
  the rebuilt migration service exited 0.
- The disposable `review_platform` database accepted connections and remained at Alembic head
  `20260819_0036`; the expected scientific/provenance/workflow tables and workflow constraints were
  present. Backend `/health/live`, `/health/ready`, and `/health/metrics`, plus frontend
  `/api/health`, each returned HTTP 200. Backend, worker, frontend, and database remained healthy.
- Result: container and PostgreSQL evidence remain valid `PASS`/`PASS_WITH_FIXES`; no durable gate was
  reopened or advanced. The control plane remains `COMPLETE`/`CHECKPOINTED` with final classification
  `READY_WITH_EXTERNAL_GATES`; the first remaining gates are the explicitly recorded external or
  environment-blocked identity, storage, scanner, parser, proxy/shared-limiter, scanner-tool, and
  broad-regression gates.
