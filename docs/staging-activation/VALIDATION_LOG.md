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

## 2026-08-20T10:18:43+01:00 SG-001 explicit security-owner disposition

- The security owner accepted the bounded residual risk for controlled/private
  staging of official `postgres:17-alpine` at
  `sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73`,
  Linux amd64, with the current official PostgreSQL entrypoint only.
- The acceptance is based on the recorded 22 gosu findings and the bounded
  source/binary govulncheck plus entrypoint evidence. It is not a blanket CVE
  waiver and does not authorize Trivy suppression.
- SG-001 is now `ACCEPTED_BOUNDED_RISK` for this exact controlled-staging
  scope. No PostgreSQL image, Compose configuration, scanner policy, or
  project container was modified.
- Re-review is due no later than `2026-09-19`, and immediately if the image
digest, gosu build/version, Go toolchain, architecture, entrypoint,
scanner/advisory evidence, exposure model, or upstream remediation changes.

## 2026-08-20T11:50:48+01:00 SG-002 malware-scanning validation

- Current HEAD before the SG-002 local change was
  `10f83f1541bbc8263e38cc1f1f51f7c84e3205a3`; the worktree was inspected and
  contained only the scoped SG-002 changes listed in the final diff. No
  GitHub push, paid service, host antivirus/firewall modification, public
  traffic, real malware, or secret value was used.
- Baseline documents, architecture, ADR-002, ADR-034, domain/provenance
  boundaries, upload/storage/parser/canonical-write path, restricted-content
  authorization, processing runs, and worker architecture were inspected.
  The scanner sits before parser execution and does not replace Document,
  provenance, workflow, or scientific state.
- Added provider-neutral `MalwareScanner` and structured outcomes
  `CLEAN`, `INFECTED`, `ERROR`, `TIMEOUT`, and `UNAVAILABLE`; bounded scanner
  version/signature/detection/error fields; and ClamAV TCP transport with
  timeout and fail-closed error mapping. The test-only fixture provider is
  rejected by staging/production configuration validation.
- Added migration `20260820_0037`, append-only tenant/review/document-scoped
  `document_malware_scan_attempts`, exact content SHA-256/size linkage, bounded
  retries, fail-closed document statuses, manager-only scan history, and
  scanner-aware readiness. Original acquisition bytes remain retained; no raw
  payload is persisted.
- Compose configuration passed `docker compose config --quiet`. The selected
  official image is
  `clamav/clamav:1.4.6@sha256:c3bfbf2a2c9abc1fc179e63832a9e8bfac901ede83853e3fa10acf6f1fb5c803`,
  Linux amd64, with private-network-only port 3310, official `clamdcheck.sh`,
  2g memory, and 2.0 CPU limits. The service became healthy after its bounded
  startup/database-load interval. A transient first Compose start waited on
  PostgreSQL crash recovery after the project-owned container recreation; the
  database subsequently became healthy and the migration service completed.
- `docker compose -p research-tool-readiness up -d --build clamav migrate
  backend worker`: PASS after the disposable database recovery interval.
  `docker compose -p research-tool-readiness ps` showed db, clamav, backend,
  worker, and existing frontend healthy; migrate exited successfully. Live
  `alembic current` and `alembic heads` both reported `20260820_0037 (head)`.
  `GET http://localhost:8000/health/ready` returned HTTP 200 with database and
  malware scanner `up`.
- Runtime ClamAV version was `1.4.6`; the provider `zVERSION` response reported
  signature database `28098` after service restart and database refresh.
  A harmless clean fixture scanned live through the repository adapter as
  `CLEAN`. Standard EICAR test content was generated only in one-off container
  memory and scanned live as `INFECTED` / `Eicar-Test-Signature`; no test file
  was created in the repository or retained in runtime storage.
- Trivy `0.74.0` from immutable image digest
  `sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969`
  scanned the exact ClamAV image with `vuln`, `HIGH,CRITICAL`, no suppression,
  and returned zero findings. Vulnerability DB metadata was
  `UpdatedAt=2026-08-20T00:55:38.477267043Z` and
  `DownloadedAt=2026-08-20T05:08:45.429790275Z`.
- `tests/unit/test_malware.py`: PASS for ClamAV protocol clean/infected
  parsing, unavailable endpoint, bounded timeout, scanner error, and fixture
  outcome taxonomy. `tests/integration/test_documents.py`: PASS for clean
  metadata and eligibility, infected blocking before processing runs/canonical
  writes, unavailable/timeout/error fail-closed behavior, bounded retry with
  retained attempts, exact content-hash integrity, tenant isolation,
  manager-only diagnostics, restricted authorization, and log/response
  redaction. `tests/integration/test_migrations.py` and health tests: PASS.
- `.venv\Scripts\ruff.exe check` and `format --check` on the changed scope,
  `.venv\Scripts\mypy.exe backend workers`, `python -m compileall -q backend
  workers`, Compose config, and `git diff --check`: PASS. Full repository
  regression was not claimed.
- SG-002 disposition: `MALWARE_SCANNER_GATE_PASS`. No external organizational
  action is required for this bounded controlled-staging scanner gate. This
entry does not begin SG-003; all unrelated gates remain in their prior state.

## 2026-08-20T12:42:43+01:00 SG-002 final post-rebuild checkpoint

- Final source was rebuilt into the project-owned migration, backend, and
  worker images with `docker compose -p research-tool-readiness up -d --build
  migrate backend worker`; the command completed successfully. No unrelated
  service was changed beyond the named project stack required by the Compose
  dependency/configuration update.
- Final `docker compose -p research-tool-readiness ps` showed db, clamav,
  backend, worker, and the existing frontend healthy. The final migration
  container exited successfully; `alembic current` reported
  `20260820_0037 (head)`. Final `GET /health/ready` returned HTTP 200 with
  `{"database":"up","malware_scanner":"up"}`.
- Against the final rebuilt backend image and private ClamAV service, the
  provider health result was healthy, ClamAV `1.4.6`, signature database
  `28098`; a harmless clean fixture returned `CLEAN`; standard EICAR test
  content generated in memory returned `INFECTED` / `Eicar-Test-Signature`.
- No EICAR file, malware payload, scanner database, secret, or runtime test
  artifact was committed. SG-002 remains `MALWARE_SCANNER_GATE_PASS`.

## 2026-08-20 SG-002 local commit checkpoint

- The SG-002 implementation, validation, and evidence changes were committed
  locally as `e70ca7a` (`feat: add fail-closed document malware scanning`).
No GitHub push was performed. The disposable `sg002-clamav` validation
container was removed; the project-owned Compose ClamAV service remains the
recorded staging service.

## 2026-08-20T14:54:30+01:00 SG-003 live GROBID/parser gate

- SG-003 was run alone. SG-004 through SG-009 were not started. The worktree
  was clean before the SG-003 implementation, and prior SG-001/SG-002 evidence
  remains preserved.
- The selected supported upstream service was
  `grobid/grobid:0.9.1-crf` at immutable Linux amd64 manifest digest
  `sha256:eb306e6d494f6f7e89b35bbaf3b4925afd58c6a5638c775f2a1c35bfd3c5db0d`.
  The image was pulled and its local image ID/repository digest matched. The
  disposable overlay kept GROBID on a private Compose network with no host
  port and probed real `/api/health` readiness.
- The first service start used a 2-GB bound and ended before readiness with
  exit `137`, `OOMKilled=true`; the health probe recorded connection refusal
  and the logs ended during model loading. The overlay was then corrected to
  the upstream full-text 4-GB memory guidance, retained a two-CPU bound, added
  `init`/`core=0`, and was retried once. During that retry Docker Desktop's
  Linux engine began returning HTTP 500 for container inspection, listing, and
  teardown. No live `/api/health` 200, `/api/version`, or parse request was
  obtained. Docker/WSL was not repaired or restarted.
- Docker later recovered without intervention. A bounded teardown then removed
  the exact `research-tool-sg003` containers, private network, and three
  disposable volumes; no broad Docker cleanup was attempted.
- The exact-image Trivy attempt used scanner image
  `aquasec/trivy:0.74.0` at
  `sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969`,
  with vulnerability scanning, HIGH/CRITICAL severity, unfixed findings
  included, and no suppression. It downloaded the database but exited with
  `context deadline exceeded` during Java database/layer analysis. A retry was
  blocked by the Docker API 500. HIGH/CRITICAL counts have no disposition and
  were not treated as zero.
- No runtime PDF was acquired because the service never became ready. There is
  therefore no PDF source, license/type, SHA-256, byte size, TEI artifact,
  parsed-output hash, or live processing-run result to claim.
- Implemented the provider-neutral HTTP parser adapter, pinned parser/version
  identity, bounded request/response and timeout handling, GROBID TEI
  normalization, canonical parsed-content hashing, append-only processing-run
  hash persistence, deterministic chunk/provenance linkage, parser readiness,
  migration `20260820_0038`, and the isolated SG-003 Compose overlay. GROBID
  remains a parser and does not become Article, Study, extraction, screening,
  Risk-of-Bias, or scientific source-of-truth state.
- Focused parser, health, security, config, migration, Ruff, format, strict
  mypy, and compile checks passed. Local failure taxonomy and SG-002
  malware-before-parser tests provide bounded/mock evidence only; no live
  GROBID success or live GROBID failure/retry result was inferred from them.
- Authoritative SG-003 disposition: `GROBID_GATE_EXTERNAL_REQUIRED`. The gate
  requires a supported private GROBID runtime with enough memory, an exact
  vulnerability result/disposition, and one openly shareable scholarly PDF
  before the live health, parse, retry, manifest, tenant, and evidence
  reconstruction checks can be rerun. No GitHub push was performed.

## 2026-08-20T15:27:57+01:00 SG-003 final retry and security checkpoint

- After the initial bounded teardown, the same isolated pinned image was
  started once more with the documented 4-GB/2-CPU bound. Docker inspection
  initially reported `running|OOMKilled=false|starting`; the terminal state was
  `exited|OOMKilled=true|137|unhealthy`. The real health probe saw only
  connection refused, and logs ended while loading the CRF segmentation model.
  No `/api/health` 200, `/api/version`, or full-text request was obtained.
- The exact Trivy scan then completed with scanner `0.74.0`, scanner digest
  `sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969`,
  target digest
  `sha256:eb306e6d494f6f7e89b35bbaf3b4925afd58c6a5638c775f2a1c35bfd3c5db0d`,
  vulnerability scanning, HIGH/CRITICAL, unfixed findings included, and no
  suppression. OS findings were `0`; Java findings were `4` (`HIGH=3`,
  `CRITICAL=1`): `CVE-2026-54399`, `CVE-2026-54428`, `CVE-2025-14813`, and
  `CVE-2026-10050`. Published fixes exist, but the selected image still ships
  affected versions, so no security acceptance was made.
- The exact GROBID project was removed after the final attempt; its containers,
  private network, and disposable volumes were removed. The temporary named
  Trivy cache volume was also removed. No PDF or parser output was retained.
- Final SG-003 classification remains `GROBID_GATE_EXTERNAL_REQUIRED`.
