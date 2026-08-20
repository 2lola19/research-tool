# Staging Activation Validation Log

All entries are repository-scoped, disposable, or read-only. No public traffic,
production DNS, paid provider, customer data, secret value, ACL change, Docker
repair, WSL repair, GitHub push, reset, or clean operation was performed.

## 2026-08-20 baseline reconciliation

- Expected baseline and starting HEAD: 7be7a605c63e00069881da86a899e71e68ade846.
- Initial worktree was clean. The branch was master, ahead of origin/master by
  three local commits; no push was attempted.
- docker compose -p research-tool-readiness config --quiet: PASS.
- Initial named project services: backend, db, frontend, and worker running
  healthy; migrate exited successfully.
- Docker client/server: 29.6.1.
- PostgreSQL database review_platform on the named project was healthy and at
  Alembic head 20260819_0036. Direct live requests to backend liveness,
  readiness, metrics, and frontend health returned 200.
- The root stack has no GROBID, malware scanner, S3, OIDC, shared limiter, or
  reverse proxy service. The process-local limiter, local storage provider,
  provider-neutral S3 protocol, and GROBID TEI adapter were inspected.
- An unrelated school-erp-staging Docker project and its Redis container were
  observed but not touched.

## 2026-08-20 security scanners and scoped fixes

- pip-audit was installed safely in the existing repository .venv. Version:
  2.10.1.
- Initial pip-audit finding: pytest 8.4.2, PYSEC-2026-1845, fixed in 9.0.3.
  pyproject.toml was changed minimally to pytest>=9.0.3,<10. The environment
  installed pytest 9.1.1.
- Post-fix pip-audit --local --progress-spinner off: PASS. The local
  review-platform package was skipped because it is not published on PyPI.
  pip check: PASS.
- npm 12.0.2 / Node v24.16.0. npm audit --omit=dev --audit-level=high:
  PASS, zero vulnerabilities.
- Names-only tracked-content scan for PEM private-key and AKIA/ASIA
  cloud-access-key patterns: no matches. No secret values were printed.
- Trivy 0.74.0 ran in a disposable container. Trivy image digest:
  sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969.
- Previous backend image findings were nine HIGH Debian util-linux-family
  findings plus bundled toolchain entries. backend/Dockerfile now upgrades
  affected packages and removes pip from the final image.
- Previous frontend image findings were one CRITICAL and six HIGH Node
  toolchain entries. frontend/Dockerfile now removes npm, npx, corepack, and
  Yarn from the final standalone runtime.
- Fresh backend, worker, migrate, and frontend images scanned with zero
  HIGH/CRITICAL Trivy findings. Image digests are recorded in
  SECURITY_SCAN_REPORT.md.
- postgres:17-alpine digest
  sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73
  retained one CRITICAL and 21 HIGH gosu findings. postgres:17-bookworm
  digest sha256:84560e3b9c6874893fc4e2854f5dc3e7c1a37bc9d1dfd7a8c641310ae22ba5ad
  had the same profile. This remains an external/operator gate.
- Docker Scout 1.23.1 is installed but quickview requires Docker ID
  authentication. No login was attempted.

## 2026-08-20 image refresh and health

- docker compose config --quiet after changes: PASS.
- Fresh backend, worker, migrate, and frontend images were built with pull.
  The frontend Next production build completed successfully in the image build.
- The one-shot migration runner was executed against the project PostgreSQL
  service: exit 0.
- Only the named readiness project backend, worker, and frontend were
  force-recreated because their image contents changed for the security fix.
- After refresh, backend, db, frontend, and worker were healthy. Alembic current
  reported 20260819_0036 (head). All four health URLs returned 200.
- The worker command python -m workers.review_worker --once completed with
  worker_started, worker_cycle_completed processed_jobs=0, and worker_stopped.

## 2026-08-20 live PostgreSQL validation

- A disposable database named staging_activation_20260820 was created in the
  named PostgreSQL service. No customer data was used.
- tests/integration/test_postgresql_migrations.py with the disposable database:
  PASS. Alembic upgraded the current schema successfully.
- tests/integration/test_tenant_isolation.py against the same database:
  PASS, 54 tests. Cross-tenant reads/writes, memberships, roles, and direct-ID
  non-enumeration remained covered.
- The disposable database was dropped after these checks completed.

## 2026-08-20 focused application evidence

- ruff check: PASS.
- ruff format --check: PASS, 406 files already formatted.
- mypy backend workers: PASS.
- pytest -q --no-cov tests/unit tests/api: PASS.
- Focused storage, parser, configuration, authentication, health, metrics,
  rate-limit, and API security selectors: PASS.
- Focused workflow, execution, and recovery unit selectors: PASS.
- Statistical synthesis golden benchmark plus analysis integration:
  PASS.
- Document and identity integration selectors: PASS.
- Frontend npm run typecheck: PASS.
- Frontend npm test -- --run: PASS, one file and ten tests.
- Frontend npm run build: PASS. Next compiled, TypeScript completed, eight
  static pages generated, and route optimization completed.

## 2026-08-20 bounded limitations

- Repository-wide pytest -q --no-cov was attempted with the disposable
  PostgreSQL URL. It produced partial dots, then no output for the final
  bounded minute and was stopped at five minutes after its exact pytest
  process tree was inspected. It is ENVIRONMENT_BLOCKED, not PASS.
- A combined workflow/document integration group showed the same Windows
  environment stall and was stopped at its five-minute bound. Its isolated
  workflow unit selectors and document/identity selectors passed.
- Frontend npm run lint was attempted twice and produced no result after its
  bounded window. The validation process tree was inspected and only the
  related lint process was stopped. It is ENVIRONMENT_BLOCKED, not PASS.
- No test was weakened, removed, or marked as passing because of a timeout.

## 2026-08-20 external/environment disposition

- No repository malware scanner or approved scanner service exists.
- No live GROBID service or non-sensitive PDF fixture exists.
- No live S3 client/service or authorized bucket exists. Fake-client adapter
  tests are not network evidence.
- No OIDC adapter or provider account exists. Local fail-closed checks are not
  provider evidence.
- No shared limiter or TLS/reverse-proxy topology exists.
- Inherited V1 lifecycle, human-gate, audit, provenance, tenant, deterministic
  scientific, and export/reproducibility evidence remains valid in the prior
  deployment-readiness report and operations rehearsal; this activation did
  not restart completed gates or claim live external-service coverage.

## Checkpoint

Scoped code fixes were committed locally as
95446647d25af3708b7b579fcd4769018d6b990d. Documentation finalization remains
the only uncommitted work at this point. The final classification is
READY_WITH_EXTERNAL_GATES.

## 2026-08-20 control-plane correction: append-only ledger restoration

- On resumption after the control-plane correction request, this file was
  present at 7,045 bytes. It was not absent, and no Git reset, Git clean,
  history rewrite, or destructive recovery was performed.
- The 2026-08-20 baseline reconciliation evidence above remains part of this
  ledger: starting HEAD 7be7a605c63e00069881da86a899e71e68ade846, initially
  clean worktree, named Compose configuration and service health, Docker
  29.6.1, PostgreSQL head 20260819_0036, four direct health responses at 200,
  repository-owned external-service inventory, and the untouched unrelated
  Redis project.
- This dated entry is a correction and reconciliation record. It does not
  silently delete, reorder, or downgrade prior evidence. From this point
  forward, VALIDATION_LOG.md is append-only; factual corrections must be
  appended with their date and reason.
- STAGING_STATE.json and BLOCKERS.md were reconciled to the evidence above:
  current gate FINAL_STAGING_REPORT, final report COMPLETE, final
  classification READY_WITH_EXTERNAL_GATES, with unresolved PostgreSQL image,
  malware, GROBID, S3, OIDC, shared-limiter, TLS, broad-regression, and
  document-bearing lifecycle gates explicitly retained.
- No independent validation was stopped by this correction. No public traffic,
  production deployment, secret handling, unrelated Docker change, or paid
  provider use occurred.

## 2026-08-20 recovered ledger control template

The original staging activation ledger requires each new evidence entry to
record:

- timestamp and current HEAD;
- exact bounded command or test selector without secret values;
- target scope and disposable-resource ownership;
- tool/version and relevant exit status;
- result classification and evidence path or checksum where appropriate;
- process-tree and cleanup notes for a timeout;
- scientific, security, tenant, and provenance impact;
- state-file update and next action.

## 2026-08-20 pre-checkpoint correction

- The earlier Checkpoint entry was accurate when written: the scoped code
  commit existed and the staging documentation was still uncommitted.
- Since that entry, all twelve staging-activation records, including this
  append-only ledger, have been reviewed, reconciled, and staged as the
  documentation checkpoint. This entry records the transition and does not
  replace the earlier checkpoint fact.

## 2026-08-20T09:56:34+01:00 SG-001 targeted PostgreSQL image gate

- Current HEAD was `6fdb35f526a1ea9c54a46eb86bde4d3b0e4740ad`; the worktree was
  clean before this evidence-only update. No Git reset, clean operation,
  public traffic, production deployment, paid service, secret value, or GitHub
  push was used.
- Compose still declares `postgres:17-alpine`. The intended official amd64
  digest was resolved and scanned as
  `sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73`.
  It is PostgreSQL 17.11 / Alpine 3.24.1 with gosu 1.19 built by Go 1.24.6.
- The running `research-tool-readiness-db-1` container was separately
  identified as untagged local image ID
  `sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193`,
  PostgreSQL 17.10 / gosu 1.19 / Go 1.24.6. It has no retained registry
  RepoDigest. A scan by that image ID returned the same 22 gosu findings. The
  project DB was not restarted because no clean official digest exists.
- Trivy 0.74.0 was run from the pinned image digest
  `sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969`
  with scanners `vuln`, package types `os,library`, severity `HIGH,CRITICAL`,
  and no `ignore-unfixed` or suppression. The project-scoped cache volume was
  retained. Database metadata was UpdatedAt `2026-08-20T00:55:38Z` and
  DownloadedAt `2026-08-20T05:08:45Z`.
- The exact final digest scan was created at `2026-08-20T08:43:54Z` and found
  22 gosu findings: CVE-2025-68121 (CRITICAL), CVE-2025-61726,
  CVE-2025-61729, CVE-2026-25679, CVE-2026-27145, CVE-2026-32280,
  CVE-2026-32281, CVE-2026-32283, CVE-2026-33811, CVE-2026-33814,
  CVE-2026-33818, CVE-2026-39820, CVE-2026-39821, CVE-2026-39822,
  CVE-2026-39836, CVE-2026-42499, CVE-2026-42504, CVE-2026-56853,
  CVE-2026-56858, CVE-2026-56859, CVE-2026-56860, and CVE-2026-56862
  (all other records HIGH). Installed module was `stdlib v1.24.6`; Trivy
  marked all 22 `fixed` with newer Go versions. The Alpine OS target was
  clean at HIGH/CRITICAL.
- Current official candidate scans were equivalent and ran against Linux amd64
  images: default/trixie digest `sha256:e38411452a464af89e5adadb8d223bf53b898d47d6ef918b2d58c08707350449`
  returned 80 findings (18 CRITICAL, 62 HIGH); Bookworm digest
  `sha256:84560e3b9c6874893fc4e2854f5dc3e7c1a37bc9d1dfd7a8c641310ae22ba5ad`
  returned 74 (20 CRITICAL, 54 HIGH); Alpine 3.23 digest
  `sha256:9ae4e8f8d0284836a505f0b2e825144e32e20499856e7dc5f7b99e19d10eedd6`
  returned 22 (1 CRITICAL, 21 HIGH). Alpine 3.24 aliases shared the final
  `18cfe3...` digest. All official variants used gosu 1.19 / Go 1.24.6.
- Official source inspection found `GOSU_VERSION 1.19`, signed release
  verification, and the entrypoint path `exec gosu postgres "$BASH_SOURCE"
  "$@"` only for a root-started container. The gosu binary SHA-256 was
  `52c8749d0142edd234e9d6bd5237dff2d81e71f43537e2f4f66f75dd4b243dd0`, matching
  the upstream 1.19 amd64 release asset.
- `govulncheck@v1.7.0` with Go 1.26.7 used the Go vulnerability database last
  updated `2026-08-19 17:06:06 +0000 UTC`. Source mode on gosu tag 1.19 and
  binary mode on the exact upstream gosu-amd64 artifact both reported no
  reachable symbol vulnerabilities. All 22 Trivy CVEs mapped to Go advisory
  IDs that appeared only as non-reachable module/package information.
- Disposable compatibility checks did not touch the project DB: Alpine 3.24
  ran `test_postgresql_migrations.py` plus `test_tenant_isolation.py` (54
  tenant tests), all PASS; default/trixie, Bookworm, and Alpine 3.23 each ran
  `test_postgresql_migrations.py`, all PASS. Each temporary candidate passed
  `pg_isready` and was removed after the check.
- No official PostgreSQL 17 digest with acceptable HIGH/CRITICAL evidence was
  found. No tag downgrade, unofficial image, manual gosu replacement, custom
  base image, scanner suppression, or project container restart was performed.
  Existing project health/migration/tenant evidence remains valid and no
  workflow, scientific data, provenance, or tenant state was changed.
- SG-001 disposition: `POSTGRES_IMAGE_GATE_ACCEPTED_RISK_REQUIRED`. This is a
  bounded security-owner handoff, not self-authorized acceptance. Re-review is
  required by 2026-09-19 and sooner on an official image/gosu/Go/Trivy update,
  entrypoint or architecture change, or increased exposure. The complete
  finding table and risk assessment are in `SECURITY_SCAN_REPORT.md`.
