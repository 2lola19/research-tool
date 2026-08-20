# Staging Activation Blockers

Status: COMPLETE_WITH_EXTERNAL_GATES. These blockers are explicit and are not
downgraded by local test fixtures.

| ID | Gate | Classification | Current action | Staging impact |
|---|---|---|---|---|
| SG-001 | Python/image vulnerability scanners | POSTGRES_IMAGE_GATE_ACCEPTED_RISK_REQUIRED | Fresh Trivy 0.74.0 evidence for official `postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73` found one CRITICAL and 21 HIGH gosu/Go-stdlib findings. govulncheck found no reachable symbols for the actual entrypoint, but a security owner must accept or reject the exact bounded exception; Docker Scout 1.23.1 still needs Docker ID login if policy requires it. | Blocks final security classification until human disposition or an upstream-remediated official digest |
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

## 2026-08-20 SG-001 correction

The SG-001 row is superseded by the targeted evidence in
`docs/staging-activation/SECURITY_SCAN_REPORT.md`. The classification is not a
scanner waiver: all 22 findings remain recorded, individually assessed as
`NOT_AFFECTED_REACHABILITY_PROVEN` for the bounded gosu invocation, and require
explicit security-owner acceptance because no clean supported official digest
exists.

## 2026-08-20 SG-001 explicit security-owner decision

The security owner accepted the bounded residual risk for controlled/private
staging of the exact official PostgreSQL image and Linux amd64 digest recorded
in the SG-001 evidence. The current SG-001 classification is
`ACCEPTED_BOUNDED_RISK`; all 22 scanner findings remain recorded and unsuppressed.
The acceptance does not authorize public production use. Re-review is due by
2026-09-19 or sooner on the documented image, gosu, Go, architecture,
entrypoint, scanner/advisory, exposure, or upstream-remediation triggers.

## 2026-08-20 SG-002 correction and closure

The SG-002 table row above is retained as the historical pre-investigation
blocker. The targeted investigation implemented the provider-neutral boundary,
official private ClamAV service, fail-closed document ordering, append-only
tenant-scoped scan evidence, clean/EICAR/unavailable/timeout/error/retry and
security tests, and exact-image Trivy validation. The current SG-002
classification is `MALWARE_SCANNER_GATE_PASS`; it is no longer a blocker for
the bounded controlled-staging scope. SG-003 and all other rows are unchanged.
