# Security

The local foundation uses environment configuration, validates input, separates liveness from dependency readiness, applies restricted CORS, emits request identifiers, and avoids secrets in source.

Upcoming identity work must use established password hashing, short-lived sessions/tokens, organization-scoped RBAC, review membership checks, and negative tenant-isolation tests. Uploaded files require MIME/signature validation, size limits, generated storage keys, malware-scanning compatibility, and no direct path trust.

Phase 2 implements local development/test authentication with scrypt password hashing and short-lived HMAC-signed bearer tokens. Local authentication cannot be configured for staging or production. Tokens identify a user but do not cache roles or organization access. Every tenant request requires `X-Organization-ID` and resolves the active database membership again, so removal revokes an already-issued token's tenant access immediately.

Tenant-owned repository calls require organization scope. Cross-organization and unauthorized same-organization review lookups return the same not-found response to prevent identifier inference. Owner/Administrator have organization-wide review visibility; Lead Reviewer, Reviewer, Statistician, and Viewer visibility is ownership/assignment scoped, with independent mutation permissions. See ADR-005 for the accepted policy.

Production hardening will add secure headers, rate limiting, signed object access, TLS termination, secret management, dependency scanning, backup/restore tests, and security-event monitoring. Authentication must never be weakened to make tests pass.
