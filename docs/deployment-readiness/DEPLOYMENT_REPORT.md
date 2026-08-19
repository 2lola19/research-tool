# Controlled Deployment Readiness Report

Status: COMPLETE_PENDING_LOCAL_CHECKPOINT

Final classification: `READY_WITH_EXTERNAL_GATES`

This is an evidence-backed controlled-staging recommendation, not a production-launch approval.
The V1 development program is complete; no Phase 39 or product feature work was created.

## Decision rule

No unresolved release-blocking defect was found. The repository and project-scoped disposable
stack passed the safely executable database, container, health, tenant, provenance, worker,
frontend, and focused security gates. OIDC, production object storage, malware scanning, live
GROBID, TLS/reverse-proxy, shared multi-replica rate limiting, approved Python/image scanning,
and the broad integration run remain external or environment-blocked gates. They are not silently
treated as passes.

## Baseline and scope

- Expected V1 baseline: `a4156e32c969efcbf4363f02413b58dabf6d4dd1` (`a4156e3`).
- Baseline branch/worktree was clean and `origin/master` matched at start.
- Inherited V1 classification: `READY_WITH_DOCUMENTED_LIMITATIONS`.
- Validation scope: only `research-tool-readiness`, its named disposable PostgreSQL databases,
  repository tooling, and non-sensitive deterministic fixtures.
- GitHub: out of scope; no push, release, remote, or repository-setting operation occurred.

## Gate summary

| Gate | Result | Evidence |
|---|---|---|
| Environment/inventory | PASS | `ENVIRONMENT_INVENTORY.md`; versions and configuration names recorded without values |
| Containers/build/health | PASS_WITH_FIXES | Compose config, final backend/frontend builds, non-root inspection, four healthy services |
| PostgreSQL/migrations | PASS | Disposable PostgreSQL, full chain, head `20260819_0036`, Alembic check, readiness |
| PostgreSQL concurrency | PASS | Four concurrent repository claims were unique; lease recovery passed |
| Backup/restore | PASS_DISPOSABLE | Custom-format backups restored into separate named databases; checksums and counts recorded |
| Local object storage/S3 boundary | PASS_LOCAL / EXTERNAL S3 GATE | Focused local and fake S3 contract tests pass; no disposable S3 service available |
| Malware scanning | EXTERNAL_DEPLOYMENT_GATE | No scanner or adapter available; no real malware used |
| Parser/GROBID | PASS_FIXTURE / ENVIRONMENT_BLOCKED_GROBID | Fixture and TEI adapter tests pass; no live GROBID service available |
| OIDC/identity | FAIL-CLOSED / EXTERNAL_CREDENTIAL_REQUIRED | Production local-auth rejection and absent OIDC boundary verified |
| Secrets | PASS_AUDIT / EXTERNAL PRODUCTION BOUNDARY | No candidate secret files or log findings; runtime secret manager still required |
| TLS/proxy | EXTERNAL_DEPLOYMENT_GATE | No disposable reverse proxy/certificate topology available |
| Rate limiting | PASS_PROCESS_LOCAL / EXTERNAL SHARED GATE | Local threshold/retry tests pass; limiter is not multi-replica global |
| Observability | PASS | Live health/readiness/metrics/frontend checks and redacted log scan pass |
| Worker/workflow recovery | PASS_BOUNDED | PG lease expiry/retry and process restart evidence pass |
| Tenant isolation | PASS | 54-test live PostgreSQL tenant suite passes |
| Scientific/provenance integrity | PASS_WITH_LIMITATIONS | Focused PG provenance test and inherited V1 lifecycle evidence pass |
| Rollback | PASS_APPLICATION_ONLY | Final image recreation/migration compatibility passed; no destructive DB downgrade attempted |
| Frontend | PASS | lint, typecheck, 10 Vitest tests, and production build pass |
| Dependency/image scans | PASS_NPM / ENVIRONMENT_BLOCKED_PYTHON_IMAGE | `npm audit` found 0 vulnerabilities; pip-audit/Trivy unavailable |
| Broad regression | ENVIRONMENT_BLOCKED | Full integration and integration-minus-tenant runs timed out without a result |

## Required report sections 1-30

1. **Baseline.** Reconciled at `a4156e3`; no unrelated work was discarded.
2. **Environment.** Windows 10 build 19045, Python 3.14.5, Node 24.16.0, npm 11.13.0, Git
   2.55.0, Docker Engine 29.6.1, Compose 5.3.0. Host PostgreSQL clients, pip-audit, Trivy,
   and ClamAV are unavailable; the project DB container supplied PostgreSQL tooling.
3. **Containers.** `docker compose config --quiet` passed. Final backend and frontend images
   built; backend/worker/frontend/db were recreated or started under the named project and became
   healthy. Worker and frontend healthcheck defects were corrected.
4. **PostgreSQL.** Disposable PostgreSQL connectivity, application startup, readiness, constraints,
   indexes, tenant composite keys, and transaction paths passed.
5. **Migrations.** The complete chain applied through `20260819_0036`; `alembic current`, `heads`,
   and `check` all report the expected head with no pending operations.
6. **Concurrency.** Four concurrent application-repository claims used live PostgreSQL locking and
   produced four unique jobs, leaving four queued. No duplicate sequence/lease result was observed.
7. **Backup/restore.** Custom-format backups were created inside the project DB container and
   restored into separate databases without overwriting the source. Evidence included backup
   `553abbd737582001a73a36298142e84668815ed8a6b403f0ad14d087ef30ef34` (632116 bytes) restoring
   head 0036, four reviews, one workflow job, and four job events; a provenance fixture backup
   `99ce38b53120b52b698790e68272c07de1ff2625504a9b53055890398cdd477d` (632106 bytes) restored
   head 0036, four reviews, three audit events, one scientific-provenance record, two organizations,
   and nine memberships. Dumps were not committed.
8. **Object storage.** Local atomic/checksum behavior and the vendor-neutral fake S3 contract pass.
   No disposable S3-compatible service or production bucket was available; this remains external.
9. **Malware scanner.** No scanner implementation/tool was available. This remains an explicit
   external gate; no real malware was used.
10. **Parser/GROBID.** Fixture parsing, bounded TEI normalization, malformed-input and limit tests
    pass. Live GROBID operation, timeout, version, and representative PDF evidence are blocked by
    the absent service.
11. **OIDC.** Production settings reject local authentication. Selecting the absent OIDC adapter
    fails explicitly rather than silently using local auth. A real issuer/JWKS/tenant-role test is
    an external credential gate.
12. **Secrets.** Required names and owners/boundaries are documented without values. Source/image
    audit and recent backend/worker log pattern audit found no candidate secret exposure. Runtime
    secret manager injection and rotation remain required externally.
13. **TLS/proxy.** Repository assumptions and secure production settings are documented, but no
    disposable reverse proxy or certificate topology was available. Public DNS/certificates were
    not changed.
14. **Rate limiting.** Process-local auth rate limiting, thresholds, headers, and retry behavior
    pass. It is not claimed as global across replicas; an approved shared/edge limiter remains a
    gate.
15. **Observability.** Live `/health/live`, `/health/ready`, `/health/metrics`, and frontend
    `/api/health` returned HTTP 200. Metrics were Prometheus text; recent service logs contained
    zero audited secret-pattern findings.
16. **Worker recovery.** Project worker stop/start was limited to the named service and returned
    healthy. A live PostgreSQL lease probe expired one attempt, reclaimed it once, completed the
    retry, and recorded two attempts with no duplicate canonical record.
17. **Workflow recovery.** PostgreSQL workflow integration tests passed: claim/heartbeat/complete,
    failure/requeue, terminal recovery, idempotent resume, and scoped reconciliation. Human gates
    remained explicit in the tested paths.
18. **Tenant isolation.** The live PostgreSQL suite passed 54 tests covering cross-organization
    enumeration/read/write boundaries and same-organization review scoping across the requested
    scientific, workflow, AI, export, audit, and provenance surfaces.
19. **Scientific lifecycle.** Deterministic mock-provider, canonical-state, human-gate, and
    provenance safeguards are inherited from the V1 report; focused PostgreSQL provenance and
    audit tests passed. The timed-out broad integration run prevents claiming a fresh full-stack
    production-style lifecycle pass.
20. **Rollback.** The candidate image was rebuilt from final source, migration compatibility was
    verified, and application/worker containers were recreated without DB reset. A destructive
    database downgrade or production rollback was neither required nor attempted.
21. **Frontend.** `npm run lint`, `npm run typecheck`, `npm test` (10 tests), and `npm run build`
    pass. The final container health route also returned HTTP 200.
22. **Security scans.** `npm audit --omit=dev --audit-level=high` reported 0 vulnerabilities;
    secret-pattern audit reported zero candidate files. pip-audit and Trivy are unavailable and
    must be run by the target environment owner.
23. **Regression.** API/unit shard passed in full; migration tests passed; focused PostgreSQL
    tenant/workflow/provenance/recovery tests passed. Full integration and integration-minus-tenant
    runs timed out at 904 and 604 seconds respectively without output/result; their processes were
    inspected and stopped safely. This is `ENVIRONMENT_BLOCKED`, not PASS.
24. **Environment blockers.** Host scanner/client gaps, absent S3/GROBID/malware/proxy services,
    and broad regression timeout are recorded in `BLOCKERS.md` and state.
25. **External credential gates.** OIDC issuer/configuration, production secret manager, approved
    object storage, malware service, edge/TLS configuration, shared limiter, and approved scanners
    require an authorized operator checklist; no values were fabricated.
26. **Defects discovered.** PostgreSQL portability failures in migrations 0033 and 0035, ORM/migration
    metadata drift, missing reporting model imports, insufficient workflow invariants, and false
    frontend/worker health probes were found during this program.
27. **Fixes made.** Direct PostgreSQL migration paths, metadata/index/check/FK alignment, reporting
    imports, migration 0036 invariants, explicit frontend IPv4 probe, process-level worker probe,
    expected-head updates, and opt-in PostgreSQL tenant-test plumbing were implemented and tested.
28. **Local commits.** No GitHub operation occurred. The validated local checkpoint is pending the
    strict commit procedure; its SHA will be recorded in this report and state before completion.
29. **Remaining risks.** External identity/storage/scanner/parser/proxy/shared-limit evidence,
    approved Python/image scans, and the broad integration timeout remain. These prevent a claim of
    full production readiness and require target-environment acceptance evidence.
30. **Final recommendation.** `READY_WITH_EXTERNAL_GATES`. A tightly isolated staging rehearsal
    with non-sensitive or explicitly authorized test data is justified only within the documented
    boundary; user-facing or production-like acceptance should wait for the listed external gates.

## Defects and corrective actions

- `20260819_0033_workflow_recovery.py` and `20260819_0035_document_processing_hardening.py` were
  corrected to avoid SQLite batch rewrites that attempted to drop PostgreSQL indexes referenced by
  tenant foreign keys.
- ORM metadata was reconciled to the migration chain, including reporting imports, indexes, check
  constraints, FK delete policies, and legacy nullable timestamps; `alembic check` now passes.
- `20260819_0036_workflow_job_invariants.py` adds workflow payload-version and bounded-retry checks.
- Compose/frontend/worker health probes were corrected to reflect actual service boundaries.
- Validation-only PostgreSQL tenant fixture setup is opt-in and only truncates an explicitly supplied
  disposable test database; the default SQLite fixture remains unchanged.

## Final recommendation and stop boundary

`READY_WITH_EXTERNAL_GATES` is the final classification. It permits only the controlled, non-sensitive
staging boundary described above. It does not authorize production traffic, clinical use, public
marketing, autonomous scientific publication, paid provider activation, or GitHub push. After the
local checkpoint SHA is recorded and the worktree is verified, stop; do not start another development
phase.
