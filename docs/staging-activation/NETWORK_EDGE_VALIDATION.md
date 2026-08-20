# Network Edge and Shared Limiter Validation

Status: EXTERNAL_OPERATOR_ACTION_REQUIRED

## Local evidence

The process-local authentication limiter passed its deterministic threshold,
remaining, and Retry-After unit checks, and the API security suite passed the
local 429 behavior. The live named stack exposes only its private local Docker
ports; direct liveness, readiness, metrics, and frontend health requests
returned 200 after the image refresh. Metrics and security-header behavior are
covered by focused API tests.

The application intentionally does not claim a distributed security authority:
the limiter is process-local and there is no approved shared-state abstraction.
No proxy, TLS certificate, forwarded-header trust boundary, secure-cookie
topology, host policy, or private staging edge exists in the repository-owned
Compose project. The unrelated school-erp Docker project was observed but not
used or changed.

## Required external evidence

For the intended replica count, supply an approved shared or edge limiter and
rerun cross-replica threshold enforcement, tenant/user isolation, Retry-After,
unavailable-store behavior, and security-sensitive fail-closed behavior.

Supply a private reverse proxy and certificate owner, without public DNS
changes. Rerun trusted forwarded headers, HTTPS scheme, secure cookies, host
validation, CORS/origin restrictions, API/frontend routing, health behavior,
metrics exposure restriction, and stream behavior if implemented. Record
configuration variable names only; do not store certificates or private keys.
