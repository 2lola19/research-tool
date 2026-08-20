# Staging Activation Blockers

Status: COMPLETE_WITH_EXTERNAL_GATES. These blockers are explicit and are not
downgraded by local test fixtures.

| ID | Gate | Classification | Current action | Staging impact |
|---|---|---|---|---|
| SG-001 | Python/image vulnerability scanners | EXTERNAL_OPERATOR_ACTION_REQUIRED | pip-audit 2.10.1, npm audit, Trivy 0.74.0, and names-only key scanning ran. Application images are clean; official PostgreSQL images retain one CRITICAL and multiple HIGH gosu findings. Approve a clean image digest or exact risk exception. Docker Scout 1.23.1 also needs Docker ID login. | Blocks final security classification until the database image is dispositioned |
| SG-002 | Malware scanner | EXTERNAL_OPERATOR_ACTION_REQUIRED | Supply an approved scanner and adapter; no scanner service exists in the repository-owned stack. | Blocks document-bearing staging |
| SG-003 | GROBID | ENVIRONMENT_BLOCKED | Supply a safe disposable service and non-sensitive PDF fixture; local TEI/fixture parser tests passed only. | Blocks live document-processing staging |
| SG-004 | S3-compatible storage | EXTERNAL_CREDENTIAL_REQUIRED / EXTERNAL_OPERATOR_ACTION_REQUIRED | Supply a disposable service or approved staging bucket; only the vendor-neutral adapter/fake-client boundary exists locally. | Blocks object-storage staging |
| SG-005 | OIDC/test identity | EXTERNAL_CREDENTIAL_REQUIRED | Supply an authorized issuer, audience, JWKS policy, callback URLs, users, and roles; deterministic fail-closed tests passed locally. | Blocks identity-backed staging |
| SG-006 | Shared rate limiting | EXTERNAL_OPERATOR_ACTION_REQUIRED | Supply the approved shared or edge limiter for the intended replica count; process-local behavior passed only. | Blocks multi-replica or public exposure |
| SG-007 | TLS/reverse proxy | EXTERNAL_OPERATOR_ACTION_REQUIRED | Supply a private staging proxy, certificate, trusted forwarded-header policy, host policy, and CORS policy. | Blocks network-exposed staging |
| SG-008 | Broad regression | ENVIRONMENT_BLOCKED | Full pytest was bounded at five minutes after partial progress with no output; the workflow/document group had the same stall. Frontend typecheck/test/build passed; broad lint stalled after its bounded window. | Final classification cannot claim broad regression |
| SG-009 | Staging lifecycle | EXTERNAL_OPERATOR_ACTION_REQUIRED | Inherited deterministic V1 lifecycle evidence and current PostgreSQL/worker/document/analysis evidence are preserved. Full document-bearing rehearsal needs malware, GROBID, S3, identity, and private edge services. | Blocks controlled document-bearing staging |

No secret value, real customer data, public DNS, paid service, or production traffic
was requested or used. The disposable PostgreSQL validation database was removed
after its checks.
