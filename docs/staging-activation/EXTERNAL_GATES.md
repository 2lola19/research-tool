# External Gates and Operator Handoff

Status: COMPLETE_WITH_EXTERNAL_GATES. No external gate is treated as complete
without direct evidence. Secret values must never be pasted into these records.

## Gate A: vulnerability scanners and image supply chain

CURRENT STATUS: EXTERNAL_OPERATOR_ACTION_REQUIRED

WHY EXTERNAL: pip-audit, npm audit, names-only key scanning, and disposable
Trivy were executable locally. The application images are clean after the
recorded fixes, but both official PostgreSQL 17 Alpine and Bookworm images
retain CRITICAL/HIGH gosu findings. Docker Scout is installed but requires
Docker ID authentication.

EXACT USER ACTION: Provide an approved PostgreSQL image digest whose complete
Trivy HIGH/CRITICAL result is acceptable, or obtain security-owner risk
acceptance for the exact gosu findings. If organization policy requires Docker
Scout, run it from an approved authenticated account.

VALUES/ACCOUNTS REQUIRED: Approved image digest, scanner policy owner, and
exception owner. Docker ID only if the organization requires Docker Scout.

SECRET VARIABLE NAMES: None for local scanning.

VALIDATION TO RUN AFTERWARD: Rerun pip-audit, npm production audit, the
names-only key scan, Trivy on every Compose image, and any approved scanner.
Record tool versions, image digests, finding IDs, severities, fixes, and
exceptions.

STAGING BLOCKING?: YES.

## Gate B: malware scanning

CURRENT STATUS: EXTERNAL_OPERATOR_ACTION_REQUIRED

WHY EXTERNAL: No malware scanner adapter or approved scanner service exists in
the repository-owned stack. No actual malware was used.

EXACT USER ACTION: Supply an approved disposable scanner and the adapter
transport/configuration owner. The service must support clean-file acceptance,
EICAR-standard test detection, unavailable and timeout behavior, quarantine or
rejection, and canonical-write ordering.

VALUES/ACCOUNTS REQUIRED: Scanner endpoint or local service identity, timeout
policy, quarantine owner, and staging data-retention policy.

SECRET VARIABLE NAMES: Use only names defined by the approved adapter; record
names, never values.

VALIDATION TO RUN AFTERWARD: Health, clean PDF acceptance, EICAR detection,
scanner unavailable, timeout/failure, quarantine/rejection, retry behavior,
and proof that restricted content cannot become canonical before acceptance.

STAGING BLOCKING?: YES for document-upload staging.

## Gate C: GROBID/document parsing

CURRENT STATUS: ENVIRONMENT_BLOCKED

WHY EXTERNAL: The provider-neutral adapter and representative TEI fixture
tests exist, but no live GROBID service or non-sensitive scholarly PDF is
available in the repository-owned environment.

EXACT USER ACTION: Supply an approved disposable GROBID image or endpoint and a
non-sensitive representative PDF fixture. Do not place the PDF in Git.

VALUES/ACCOUNTS REQUIRED: Endpoint/image identity, parser version, resource
limits, and fixture owner. No paid account is inherently required.

SECRET VARIABLE NAMES: GROBID_URL only, if that is the approved configuration
name; do not record its value.

VALIDATION TO RUN AFTERWARD: Health/version, bounded timeout, title/abstract/
body extraction, page/section/block reconstruction, processing-run metadata,
chunk manifest and content hashes, retry, timeout, unavailable behavior, and
evidence reconstruction.

STAGING BLOCKING?: YES for document-processing staging; NO only for an
explicitly non-document local smoke scope.

## Gate D: S3-compatible object storage

CURRENT STATUS: EXTERNAL_CREDENTIAL_REQUIRED / EXTERNAL_OPERATOR_ACTION_REQUIRED

WHY EXTERNAL: The application has a vendor-neutral protocol and fake-client
tests, but no concrete S3 client, disposable S3 service, or approved staging
bucket. The root stack intentionally uses local storage.

EXACT USER ACTION: Provide an explicitly disposable S3-compatible service or
approved staging bucket and authorize the bounded adapter validation. Confirm
the owner for retention, deletion, access policy, and cleanup.

VALUES/ACCOUNTS REQUIRED: Endpoint, bucket, access identity, region/signing
policy, retention owner, and cleanup owner.

SECRET VARIABLE NAMES: OBJECT_STORAGE_PROVIDER, AWS_ENDPOINT_URL,
AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, and S3_BUCKET only if
the approved adapter defines those names. Never record values.

VALIDATION TO RUN AFTERWARD: Connection, opaque-key upload/retrieval, checksum,
size, metadata, nonexistent object, retry/idempotency, tamper detection,
reconciliation, tenant/review scope, parser integration, and malware ordering.

STAGING BLOCKING?: YES for document-bearing object-storage staging.

## Gate E: OIDC/test identity

CURRENT STATUS: EXTERNAL_CREDENTIAL_REQUIRED

WHY EXTERNAL: The repository has local authentication and explicit fail-closed
configuration checks, but no OIDC adapter, provider account, issuer, or test
tenant.

EXACT USER ACTION: Provide an authorized disposable identity-provider tenant,
issuer, audience, JWKS/key-rotation policy, private-staging callback URLs,
test users, tenant memberships, role mappings, and logout/revocation policy.

VALUES/ACCOUNTS REQUIRED: Issuer URL, audience, client registration,
redirect/callback URLs, test tenant, users for each required role, and provider
operator.

SECRET VARIABLE NAMES: OIDC_ISSUER_URL, OIDC_AUDIENCE, OIDC_CLIENT_ID,
OIDC_CLIENT_SECRET, OIDC_JWKS_URL, or the exact names required by the approved
adapter. Never record values.

VALIDATION TO RUN AFTERWARD: Wrong issuer/audience, expiry, malformed tokens,
missing claims, rotated keys, wrong tenant, role mapping, browser/session,
logout/revocation, and fail-closed startup behavior.

STAGING BLOCKING?: YES unless an approved strictly controlled staging identity
substitute is documented.

## Gate F: shared/distributed rate limiting

CURRENT STATUS: EXTERNAL_OPERATOR_ACTION_REQUIRED

WHY EXTERNAL: The current limiter is process-local and the repository contains
no approved shared-state abstraction. An unrelated Redis container was observed
but was not used or changed.

EXACT USER ACTION: Supply the approved shared store or edge limiter topology,
replica count, threshold policy, Retry-After policy, failure policy, and
incident owner.

VALUES/ACCOUNTS REQUIRED: Shared-store or edge endpoint, policy owner, replica
topology, and operator access.

SECRET VARIABLE NAMES: Record only names defined by the approved deployment
adapter.

VALIDATION TO RUN AFTERWARD: Send representative requests across multiple API
replicas, verify threshold enforcement and isolation, verify Retry-After, and
verify unavailable-store behavior does not fail open for security-sensitive
endpoints.

STAGING BLOCKING?: YES for multi-replica or network-exposed staging; NO for a
documented one-replica private smoke scope.

## Gate G: TLS/reverse proxy

CURRENT STATUS: EXTERNAL_OPERATOR_ACTION_REQUIRED

WHY EXTERNAL: No private reverse proxy, certificate, trusted-forwarded-header
policy, or staging hostname is present. Public DNS and public traffic are
outside this program.

EXACT USER ACTION: Supply a private staging edge topology, certificate owner,
trusted forwarded-header policy, HTTPS origin, secure-cookie policy, host
validation policy, CORS origins, and metrics restriction route.

VALUES/ACCOUNTS REQUIRED: Private hostname/certificate, proxy configuration,
internal routing, and certificate/operator owner. No public DNS change.

SECRET VARIABLE NAMES: APP_CORS_ORIGINS, APP_TRUSTED_PROXY, or exact approved
equivalents. Do not record values, certificates, or private keys.

VALIDATION TO RUN AFTERWARD: Proxy forwarding, HTTPS scheme, secure cookies,
host validation, CORS/origin restrictions, API/frontend routing, health
behavior, metrics exposure restriction, and websocket/stream behavior if
implemented.

STAGING BLOCKING?: YES for network-exposed staging; NO for localhost-only
validation.

## Gate H: broad regression and lifecycle

CURRENT STATUS: ENVIRONMENT_BLOCKED / EXTERNAL_OPERATOR_ACTION_REQUIRED

WHY EXTERNAL: The full pytest attempt and the workflow/document group were
bounded after Windows-environment stalls with partial progress and no final
summary. Broad frontend lint also stalled; frontend typecheck, tests, and
production build passed. The inherited V1 lifecycle rehearsal remains valid
evidence but does not replace the live external-service rehearsal.

EXACT USER ACTION: After the service and image gates above are supplied, run
the repository-wide backend suite, full tenant and PostgreSQL suites, worker
recovery suite, frontend lint/typecheck/tests/build, health checks, storage and
parser integration, then the complete disposable lifecycle from Review through
export/reproducibility package.

VALUES/ACCOUNTS REQUIRED: Only the already-listed disposable services and
operator-controlled staging credentials.

SECRET VARIABLE NAMES: Use the approved staging names only; never record
values.

VALIDATION TO RUN AFTERWARD: Preserve process-tree and timeout evidence. A
timeout is not a pass. Verify human gates, tenant isolation, audit/provenance
continuity, deterministic outputs, retry/resume, no autonomous canonical AI
mutation, and no duplicate scientific records.

STAGING BLOCKING?: YES for claiming controlled staging readiness.
