# Research Tool V1 Release Report

Date: 2026-08-19

## Release classification

**READY_WITH_DOCUMENTED_LIMITATIONS**

This classification means the repository-controlled V1 lifecycle and scientific safeguards are
validated locally, with explicit external-environment gates still required before any controlled
production deployment. It is not authorization to publish, push to GitHub, or admit production
traffic.

## Scope reviewed

The Phase 38 review covered the supported lifecycle from Review and approved protocol through
search execution/provenance, citation import and non-destructive deduplication, blinded screening,
documents/full text, Study Family links, extraction and verification, risk of bias, outcomes and
effect estimates, deterministic analysis, certainty, PRISMA/reporting/reproducibility, governed AI,
exports, workflow recovery, tenant boundaries, and operational configuration.

Deterministic scientific behavior remains repository-owned. AI providers are advisory and
human-governed; they do not become canonical scientific state or replace provenance, audit,
blinding, protocol immutability, or Article/Study separation.

## Validation evidence

### Passing local gates

- Backend: Ruff check PASS; Ruff format check PASS (384 files); strict `mypy backend workers` PASS
  (236 source files); and `python -m compileall -q backend workers` PASS.
- Deterministic scientific benchmark subset: 76 tests PASS across citation parsing, search
  translation/provider fixtures, deduplication, screening, document parsing, export rendering,
  search execution, risk of bias, outcome harmonization, statistical synthesis, reporting, and
  certainty. The golden statistical fixture and deterministic renderers are included in this set.
- All backend unit tests: 190 PASS with `--no-cov`; all API tests: 9 PASS with `--no-cov`; all
  deterministic AI unit tests: 70 PASS with `--no-cov`.
- End-to-end domain integration shards: 59 PASS with `--no-cov`, covering migrations/identity,
  PRISMA, exports, scholarly search execution, documents, Studies, extraction/schema verification,
  risk of bias, outcomes, analysis, certainty, reporting, workflow execution, and governed AI
  foundation/screening/full-text/extraction/RoB/outcome/certainty/copilot flows.
- Tenant/scientific boundary sample: 5 focused tenant-isolation tests PASS, including cross-tenant
  non-enumeration, protocol immutability/provenance, blinded screening, AI provenance scope, and
  append-only audit behavior.
- Frontend: `npm run lint` PASS; `npm run typecheck` PASS; Vitest PASS (10 tests); and
  `npm run build` PASS with Next.js 16.3.
- Schema/configuration: `docker compose config --quiet` PASS; Alembic reports one head,
  `20260819_0035`; the SQLite migration upgrade/downgrade chain passes in the focused migration
  evidence.
- Security/artifact checks: `npm audit --omit=dev --audit-level=high` reports 0 vulnerabilities;
  repository high-risk secret scan PASS; tracked generated-artifact audit PASS; worktree and
  `.git/index.lock` checks PASS.

Targeted pytest commands used `--no-cov` so their results are behavior evidence, not a repository-
wide coverage claim. The default repository-wide pytest command was attempted separately below.

### Environment-blocked gates

- The Phase 38 repository-wide `pytest` command emitted no output and timed out after 424 seconds.
  Its exact pytest/Python processes were inspected and safely terminated. No full-suite assertion
  or coverage result is claimed.
- The complete `tests/integration/test_tenant_isolation.py` module emitted no output and timed out
  after 300 seconds. The focused tenant boundary sample above passes; the broad timeout is not
  interpreted as a scientific failure or a pass.
- Live `.venv\\Scripts\\python.exe -m alembic check` emitted no output and timed out after 90
  seconds against the unavailable configured PostgreSQL endpoint. SQLite evidence does not claim
  PostgreSQL locking, concurrency, health, backup, or restore compatibility.
- `docker compose build` emitted no output within 180 seconds. No Compose services were started and
  no container health result is claimed.
- `pip-audit` and Trivy are unavailable in this environment. The npm production dependency audit
  passed, but the missing Python/image scanner evidence remains a deployment gate.

## Residual controlled-deployment gates

Before controlled production use, an authorized deployment must provide and record evidence for:

- a reviewed OIDC identity provider adapter and production secret-manager configuration;
- PostgreSQL migration, readiness, concurrency, backup, and disposable restore checks;
- successful image builds, image/dependency scans, pinned image digests, and container health;
- approved TLS/reverse-proxy forwarding, internal metrics exposure, and edge/shared-store rate
  limiting for multiple replicas;
- production object storage, malware scanning, GROBID/parser operations, and object checksum
  reconciliation; and
- an authorized operational rehearsal covering worker recovery, audit/provenance continuity,
  tenant isolation, and rollback without destructive database reset.

Paid/live scholarly and AI providers remain opt-in deployment concerns. No live claim is inferred
from deterministic fixtures or offline provider tests.

## Scientific and security review

- No critical or high finding was identified.
- Protocol versions, scientific records, approved decisions, provenance, and audit events remain
  immutable or append-only according to their existing boundaries.
- Article and Study remain distinct; Study Family links preserve multi-Article history.
- Screening remains blinded and assignment-scoped until an explicit authorized reveal; AI proposals
  remain advisory and human acceptance remains required.
- Deterministic calculations, transformations, readiness, PRISMA derivation, exports, and checksum
  validation remain in repository-owned code rather than an LLM.
- Tenant-owned reads and writes remain organization/Review scoped, and operational diagnostics do
  not expose credentials, raw provider responses, storage keys, or workflow lease capabilities.

## Model and Git policy

The currently selected model was used for normal implementation and validation. No autonomous model
switch or escalation was attempted; no unresolved scientific, security, migration, or architectural
issue required `MODEL_ESCALATION_RECOMMENDED`.

Phase 37’s validated implementation checkpoint is local commit
`4a002a45a054eb1987c6e9ae7df1df0a2e9d634f`; Phase 38’s validated release checkpoint is local
commit `add938ce0c118b56362f754d93452fa402da0870`. No GitHub push, release publication, remote
change, or prohibited Git operation was performed.

## Decision

V1 is complete at the repository-controlled boundary and may proceed to a separately authorized,
controlled deployment only after the residual environment gates above are evidenced. The known
limitations are durable, explicit, and do not justify weakening scientific safeguards or silently
claiming production readiness.
