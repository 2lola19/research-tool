# Deployment Readiness Blockers and External Gates

Status: COMPLETE_WITH_EXTERNAL_GATES

No blocker is cleared by absence of local infrastructure. The following items are explicit
environment/credential gates; none was fabricated as a pass.

## Resolved deployment defects

| ID | Defect | Resolution | Evidence |
|---|---|---|---|
| FIX-001 | PostgreSQL migration 0033 attempted a SQLite batch rewrite that conflicted with tenant FKs | Added direct PostgreSQL column/check/index paths while retaining SQLite behavior | Live full upgrade to 0036 |
| FIX-002 | PostgreSQL migration 0035 attempted to drop FK-referenced unique indexes | Added direct PostgreSQL path and preserved SQLite batch path | Live full upgrade to 0036 |
| FIX-003 | ORM metadata drifted from migrations and omitted reporting mappings | Reconciled imports, indexes, checks, FK policies, and legacy nullable columns | Live `alembic check` |
| FIX-004 | Workflow job invariants were missing from the current head | Added migration 0036 for payload/retry bounds | Live head/constraint inspection |
| FIX-005 | Frontend/worker health probes described the wrong network/process boundary | Frontend uses IPv4 loopback; worker uses process-level probe | Four healthy named-stack services |

## Current gates

| ID | Gate | Classification | Required resolution | Status |
|---|---|---|---|---|
| DR-001 | Local deployment checkpoint | `READY_FOR_CHECKPOINT` | Run strict local commit procedure; record SHA in state/report; no GitHub push | Open until checkpoint is recorded |
| DR-002 | OIDC adapter and real identity configuration | `EXTERNAL_CREDENTIAL_REQUIRED` | Supply authorized issuer/audience/JWKS/key rotation, tenant membership, roles, expiry, revocation/logout tests, and secret owner | Open |
| DR-003 | Production-style object storage | `EXTERNAL_DEPLOYMENT_GATE` | Provide explicitly disposable/approved S3-compatible service; run upload, opaque-key, checksum, tamper, auth, retry, and reconciliation checks | Open |
| DR-004 | Malware scanning | `EXTERNAL_DEPLOYMENT_GATE` | Provide approved scanner/adapter; exercise clean, failure, unavailable, and safe known-test-signature paths | Open |
| DR-005 | Live GROBID | `ENVIRONMENT_BLOCKED_GROBID` | Run bounded representative PDF, timeout, parser identity/version, chunk/hash, retry, and reconstruction checks when service is available | Open |
| DR-006 | Multi-replica rate limiting | `EXTERNAL_DEPLOYMENT_GATE` | Provide approved edge/shared limiter and verify threshold, Retry-After, tenant/user scope, and replica consistency | Open |
| DR-007 | TLS/reverse proxy | `EXTERNAL_DEPLOYMENT_GATE` | Supply approved TLS termination, trusted-forwarded-header policy, HTTPS-only behavior, secure cookies, host/CORS, and metrics exposure checks | Open |
| DR-008 | Production secrets/provider credentials | `EXTERNAL_CREDENTIAL_REQUIRED` | Configure authorized secret manager and rotation/least-privilege ownership; do not record values | Open |
| DR-009 | Python/image vulnerability scanning | `ENVIRONMENT_BLOCKED` | Run organization-approved pip-audit and image scanner; remediate or formally disposition every high/critical finding | Open |
| DR-010 | Broad regression | `ENVIRONMENT_BLOCKED` | Diagnose target-specific timeout and rerun bounded deterministic shards in an improved environment; focused/API/unit/PG gates pass | Open |

## Release blockers that cannot be downgraded

The final result must become `NOT_READY` if any target evidence shows a critical vulnerability,
exploitable high tenant flaw, data corruption, migration corruption, failed backup restore,
canonical scientific bypass, autonomous consequential AI mutation, duplicate canonical record after
retry, exposed secret, fail-open authentication, unsafe cross-tenant storage access, unrecoverable
operational state, or inability to start in the supported target environment.

## Exact operator checklist

1. Provide authorized OIDC issuer/audience/JWKS/key-rotation and tenant-role configuration; test
   expiry, missing configuration, invalid keys, revocation/logout, and fail-closed behavior.
2. Provide a disposable/approved staging PostgreSQL and repeat migration, concurrency, backup/restore,
   tenant, workflow, audit, provenance, and scientific fixture checks with non-sensitive data.
3. Provide pinned image digests and approved Python/node/image scanners; record versions, findings,
   remediation, and time-bounded exceptions for all high/critical findings.
4. Provide encrypted/versioned object storage, malware scanner, parser/GROBID service, checksum
   reconciliation owner, retention/deletion policy, and incident contacts.
5. Provide approved TLS termination, forwarded-header trust policy, secure-cookie/CORS/host values,
   internal metrics route, and shared/edge rate limiting.
6. Diagnose the broad integration timeout and repeat bounded shards; do not turn timeout into PASS.
7. After external evidence is complete, update this file, state, security review, operations
   rehearsal, and final report. Any release-blocking failure forces `NOT_READY`.

Never remove an unresolved gate merely to obtain a green recommendation. Do not use this program to
add features, start Phase 39, push GitHub, publish traffic, repair Docker/WSL, change ACLs, or reset
databases.
