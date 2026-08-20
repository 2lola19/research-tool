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
