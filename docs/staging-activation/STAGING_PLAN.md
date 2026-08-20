# Controlled Staging Activation Plan

Status: COMPLETE_WITH_EXTERNAL_GATES

This program closes only the external deployment gates that can be validated with
repository-scoped, disposable, non-sensitive infrastructure. It does not create a
product phase, change scientific behavior, deploy public traffic, or authorize
production use.

## Baseline

- Expected starting commit: `7be7a605c63e00069881da86a899e71e68ade846`
  (`7be7a60`).
- Current deployment-readiness classification: `READY_WITH_EXTERNAL_GATES`.
- The V1 development and deployment-readiness programs are complete.
- The named local validation project is `research-tool-readiness`.

## Gate order

1. Baseline reconciliation
2. Vulnerability and secret scanners
3. Malware scanning
4. GROBID/document parsing
5. S3-compatible object storage
6. OIDC/test identity
7. Shared/distributed rate limiting
8. TLS/reverse proxy
9. Broad regression
10. Disposable staging lifecycle rehearsal
11. Final classification and handoff

Completed evidence is preserved. An unavailable credential, account, service, or
operator-controlled topology is recorded as an explicit external/environment gate,
never as a pass. A critical or exploitable high finding, data-integrity failure,
tenant leak, authentication fail-open, canonical scientific bypass, exposed secret,
or unsafe supported-target startup changes the classification to `NOT_READY`.

## Safety boundary

Only the repository, the explicitly named disposable Compose project, and newly
created disposable resources that are proven to belong to this program are in scope.
No production/customer data, paid provider usage, public DNS, public traffic, ACL
change, Docker/WSL repair, GitHub push, destructive database reset, or secret value
is permitted.

## Execution disposition (2026-08-20)

The named Compose project was reconciled and refreshed after the scoped security
fixes. PostgreSQL, the migration runner, backend, worker, and frontend were
healthy; the database was at Alembic head 20260819_0036. A separately named
disposable PostgreSQL database was created for live migration and tenant
isolation checks and was dropped after those checks completed.

Safe local evidence closed or partially closed:

- pip-audit, npm production audit, names-only high-risk key scanning, and Trivy
  scanning were run. The backend, worker, migration, and frontend images have
  zero HIGH/CRITICAL Trivy findings after the local fixes.
- A pytest dev dependency advisory and application-image findings were fixed
  minimally and committed locally in 95446647d25af3708b7b579fcd4769018d6b990d.
- The official PostgreSQL 17 Alpine and Bookworm images still contain a bundled
  gosu helper with one CRITICAL and multiple HIGH findings. This remains an
  operator-controlled image supply-chain gate.
- Local parser, storage, identity, rate-limit, health, metrics, tenant, worker,
  scientific benchmark, migration, document, and frontend typecheck/test/build
  evidence passed. The repository-wide pytest attempt and broad frontend lint
  hit bounded Windows-environment stalls and are not called passes.
- Malware scanning, live GROBID, real S3, OIDC, distributed limiting, and TLS
  edge evidence were not fabricated. Their exact handoffs are in
  EXTERNAL_GATES.md.

The final classification is READY_WITH_EXTERNAL_GATES. No public or production
deployment was started.
