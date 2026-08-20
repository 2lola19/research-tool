# Final Staging Activation Report

Status: COMPLETE

Final classification: READY_WITH_EXTERNAL_GATES

## Scope and baseline

The activation resumed from commit 7be7a605c63e00069881da86a899e71e68ade846
with a clean initial worktree. The named Docker project was
research-tool-readiness. No production traffic, public DNS, GitHub push, paid
provider, customer data, secret value, Docker/WSL repair, ACL change, reset, or
unrelated Docker project was used.

## Gates closed or locally validated

- Baseline Git, Compose configuration, PostgreSQL, migration head, backend,
  worker, frontend, and health endpoints were reconciled.
- pip-audit 2.10.1 and npm production audit passed after a minimal pytest
  dependency fix. Names-only private-key/cloud-access-key scanning found no
  matches.
- Fresh backend, worker, migration, and frontend images have zero HIGH/CRITICAL
  Trivy findings. The application image fixes are in local commit
  95446647d25af3708b7b579fcd4769018d6b990d.
- The live project migration runner completed successfully. A disposable
  PostgreSQL database passed the Alembic migration test and all 54 tenant
  isolation tests; that database was removed afterward.
- Focused storage, parser, identity, rate-limit, health, metrics, security,
  worker, recovery, document, deterministic analysis, and frontend checks
  passed. The worker completed a real one-shot cycle with zero jobs.
- Frontend typecheck, tests, and production build passed. The refreshed
  Compose backend, worker, frontend, and PostgreSQL services were healthy.
- Inherited V1 lifecycle, human-gate, audit, provenance, scientific, tenant,
  and reproducibility evidence remains valid and was preserved rather than
  restarted.

## Remaining gates

- Official postgres:17-alpine and postgres:17-bookworm both retain one CRITICAL
  and multiple HIGH gosu findings. An approved remediated digest or security
  owner exception is required.
- Malware scanning, live GROBID, real S3, OIDC/test identity, shared/distributed
  rate limiting, and TLS/reverse proxy have no repository-owned disposable
  service or authorized external configuration.
- Repository-wide pytest and broad frontend lint were bounded after Windows
  environment stalls. They are recorded as ENVIRONMENT_BLOCKED, not passes.
- The full document-bearing staging lifecycle cannot be claimed until the
  malware, parser, storage, identity, and private edge gates are supplied.

## Vulnerabilities found and fixed

- PYSEC-2026-1845 in the development pytest dependency was fixed by raising
  the supported dev range to pytest 9.0.3 or later and below 10.
- Debian util-linux-family findings and runtime toolchain findings were fixed
  in the backend image by applying package upgrades and removing pip from the
  final runtime.
- Frontend runtime Node toolchain findings were removed from the standalone
  runtime by deleting npm, npx, corepack, and Yarn after the build stage.
- PostgreSQL gosu findings remain an external image-supply-chain blocker and
  are not waived.

## Exact user actions

1. Approve a clean PostgreSQL image digest or a security-owner exception for
   the exact gosu findings; optionally run Docker Scout from an approved
   authenticated account.
2. Supply an approved malware scanner and adapter, then rerun clean, EICAR,
   unavailable, timeout, quarantine, and canonical-write ordering tests.
3. Supply disposable GROBID and S3-compatible services plus a non-sensitive
   PDF and approved staging configuration. Rerun parser, storage, integrity,
   reconciliation, and integration tests.
4. Supply an authorized OIDC test tenant, issuer, audience, JWKS rotation
   policy, callbacks, test users, roles, and secret-managed variable names.
5. Supply the approved shared or edge limiter and private TLS reverse proxy;
   rerun cross-replica, forwarded-header, HTTPS, cookie, host, CORS, routing,
   health, and metrics checks without public DNS.
6. Rerun only the bounded broad regression and the complete disposable
   lifecycle after those dependencies are available. Preserve timeout evidence
   and do not convert a timeout to PASS.

## Private staging decision

The current localhost-only Compose stack may remain available for private
smoke validation with local storage, local authentication, and no document
claim. The requested controlled, document-bearing staging deployment cannot
safely proceed yet because the external security, parser, storage, identity,
edge, and broad-regression gates are not closed. No public exposure or
production deployment should begin.

## Local commits

- 7be7a605c63e00069881da86a899e71e68ade846: deployment-readiness recovery
  baseline.
- 95446647d25af3708b7b579fcd4769018d6b990d: harden audited staging images.

The durable state, blockers, validation log, recovery instructions, and
operator handoff are in this directory. No GitHub push was performed.

READY_WITH_EXTERNAL_GATES

## 2026-08-20 SG-001 targeted correction and disposition

The prior aggregate PostgreSQL statement is retained as historical staging
evidence. The targeted refresh used the exact official Compose candidate
`postgres:17-alpine`, PostgreSQL 17.11, Linux amd64, immutable digest
`sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73`,
gosu 1.19, and Go 1.24.6. Trivy 0.74.0 with a refreshed database found one
CRITICAL and 21 HIGH findings in the bundled gosu binary; the full advisory
table and evidence are in `SECURITY_SCAN_REPORT.md`.

Official default/trixie, Bookworm, Alpine 3.24, and Alpine 3.23 PostgreSQL
17.11 variants were also resolved and scanned. No supported official digest
was clean. The Debian variants added 58 and 52 OS findings, while both Alpine
variants retained the same 22 gosu findings. The signed upstream gosu binary
was verified by SHA-256, and govulncheck source/binary analysis found no
reachable vulnerable symbols for the actual official entrypoint invocation.
Those findings are individually dispositioned as
`NOT_AFFECTED_REACHABILITY_PROVEN`, but they are not suppressed or waived.

No Compose/configuration change, project restart, downgrade, unofficial image,
manual gosu replacement, or custom base image was made. Disposable migration
and focused PostgreSQL compatibility checks passed for the candidate variants;
the project-owned stack remained untouched. The SG-001 gate classification is
`POSTGRES_IMAGE_GATE_ACCEPTED_RISK_REQUIRED`: a security owner must explicitly
accept or reject the exact digest and 22 advisories. If accepted, re-review is
required by 2026-09-19 or sooner on an upstream image/gosu/Go/Trivy,
entrypoint, architecture, or exposure change. The overall staging report
classification remains `READY_WITH_EXTERNAL_GATES` pending all other gates.

## 2026-08-20 explicit SG-001 security-owner decision

The security owner accepted the documented bounded residual risk for controlled/
private staging of official `postgres:17-alpine` at
`sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73`,
Linux amd64, with the current official PostgreSQL entrypoint. The acceptance is
limited to that exact image scope and does not waive the 22 Trivy findings or
authorize scanner suppression. SG-001 is now `ACCEPTED_BOUNDED_RISK`.

Re-review is required no later than 2026-09-19, or immediately if the image
digest, gosu version/build, Go toolchain, architecture, entrypoint/invocation,
scanner/advisory evidence, network/exposure model, or upstream remediation
availability changes. No PostgreSQL image or configuration change was made;
the remaining staging gates are unaffected.

## 2026-08-20 SG-002 malware scanning gate disposition

SG-002 is closed for the bounded controlled-staging scope as
`MALWARE_SCANNER_GATE_PASS`. The repository now uses a provider-neutral
malware-scanner protocol with official ClamAV `1.4.6` in a private,
project-isolated Compose service. The exact scanner image is
`clamav/clamav:1.4.6@sha256:c3bfbf2a2c9abc1fc179e63832a9e8bfac901ede83853e3fa10acf6f1fb5c803`,
Linux amd64; ClamAV reported signature database `28098` after startup refresh.
The service has no host port, an official healthcheck, and bounded 2g/2 CPU
resources. Its pinned Trivy 0.74.0 scan found zero HIGH/CRITICAL findings.

The document path retains original bytes as `MALWARE_SCAN_PENDING`, persists
tenant-scoped append-only hash-linked scan attempts, and fails closed for
infection, scanner errors, timeouts, unavailability, and retry exhaustion.
Only an exact clean scan can precede parser execution, canonical block writes,
and scientific provenance. Live clean and standard EICAR scans passed; focused
unit, integration, tenant/auth/redaction, migration, readiness, compile,
Ruff, mypy, Compose, and image-scan validation passed. No real malware, EICAR
artifact, raw payload, scanner database, or secret was committed.

This disposition does not begin SG-003. The overall staging program remains
`READY_WITH_EXTERNAL_GATES` because the unrelated gates remain unchanged.
