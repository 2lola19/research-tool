# Deployment Readiness Security Review

Status: COMPLETE_WITH_EXTERNAL_GATES

This review covers the deployment boundary and current disposable evidence. The V1 scientific and
security review remains in `V1_RELEASE_REPORT.md`; no safeguard was weakened to obtain a green
result.

## Security invariants carried into deployment

- Tenant-owned reads/writes remain Organization/Review scoped and fail closed on foreign IDs.
- Article, Study, Document, workflow state, scientific data, provenance, and audit remain distinct.
- Approved versions and consequential scientific records remain immutable or append-only.
- Deterministic scientific operations remain repository-owned; AI remains advisory and human
  acceptance remains required.
- Uploaded objects use opaque keys, bounded media/size/checksum validation, authorization before key
  resolution, and checksum verification on retrieval.
- Logs/metrics must not expose bearer tokens, credentials, raw restricted content, storage keys,
  provider response bodies, or unnecessary tenant identifiers.

## Deployment review matrix

| Area | Evidence | Result |
|---|---|---|
| Authentication fail-closed | Production settings reject local auth; absent OIDC adapter raises an explicit runtime boundary | PASS_FAIL_CLOSED / EXTERNAL OIDC GATE |
| Authorization/tenant isolation | 54-test live PostgreSQL negative/scoping suite | PASS |
| Secrets | Names-only inventory, image/source pattern audit, recent log audit | PASS_AUDIT; runtime secret manager external |
| Database/migrations | Live full chain, head 0036, constraints/indexes, Alembic check | PASS |
| Object storage | Local/fake S3 checksum/auth contract tests | PASS_LOCAL; production S3 external |
| Malware | No scanner binary or adapter | EXTERNAL_DEPLOYMENT_GATE |
| Parser | Bounded fixture/GROBID TEI tests | PASS_FIXTURE; live GROBID environment-blocked |
| TLS/proxy | Production settings/docs reviewed; no disposable proxy | EXTERNAL_DEPLOYMENT_GATE |
| Rate limit | Process-local threshold/retry tests | PASS_PROCESS_LOCAL; shared multi-replica external |
| Observability | HTTP health/metrics and log-pattern audit | PASS |
| Dependencies/images | npm audit 0 findings; pip-audit/Trivy unavailable | PASS_NPM; scanner environment gate |

## Secret and credential audit

The audit examined tracked/source files, Compose/Docker configuration, environment templates,
recent backend/worker logs, and the final source scope. It recorded only names and classifications:

- No `.env`, `.env.local`, or `.env.production` file was present.
- No host process value for required application variables was recorded.
- Secret-pattern search returned zero candidate files outside excluded dependency/cache/runtime paths.
- Recent backend/worker logs returned zero matches for private keys, password assignments, API keys,
  bearer-token text, signed capabilities, secrets, or access keys.
- The final image build context contained no source credential file; no dump was staged or committed.
- Production secrets must be supplied through an authorized runtime secret manager, with named owner,
  rotation procedure, least privilege, and no persistence in logs/provenance/reports.

## Identity and authorization disposition

`AUTH_CONFIG_FAIL_CLOSED_PASS` verified that production rejects `authentication_provider=local` and
that selecting `oidc` does not silently fall back to local authentication when the adapter is absent.
The following remain external checks: issuer/audience validation, JWKS rotation/failure, expiry,
tenant membership, role mapping, session/revocation/logout, and real provider credentials.

## Storage, parser, and malware disposition

The repository-level storage and parser boundaries are tested, but this is not evidence of a live
cloud object store, malware scanner, or GROBID deployment. An authorized operator must provide
disposable/approved services and repeat clean/failure/unavailable/tamper/timeout/reconciliation
tests without recording credentials or real malware.

## TLS, forwarding, and rate-limit disposition

The production configuration requires HTTPS origins, rejects local auth, disallows wildcard/local
CORS, and enables production security headers. No public DNS, certificate, or proxy was changed.
The app's authentication limiter is explicitly process-local; it is not a global multi-replica
control. The target topology must provide an approved trusted-forwarded-header policy, secure
cookies, host/CORS rules, internal-only metrics, and an edge/shared limiter before public exposure.

## Dependency and image findings

- `npm audit --omit=dev --audit-level=high`: PASS, 0 vulnerabilities.
- `pip-audit`: unavailable on this host; no result fabricated.
- Trivy/container vulnerability scan: unavailable on this host; no result fabricated.
- No critical/high vulnerability was observed in the available evidence. Target owners must run
  approved Python/image scans and resolve or formally accept every high/critical finding.

## Finding disposition

No new critical vulnerability, exploitable high tenant issue, secret exposure, fail-open auth, unsafe
cross-tenant object access, canonical-state bypass, or duplicate canonical retry write was found.
The unresolved items are external/environment gates, not silently cleared findings. Any target scan
or live identity/storage result that violates the release-blocking conditions changes the final
classification to `NOT_READY`.
