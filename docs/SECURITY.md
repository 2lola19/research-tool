# Security

The local foundation uses environment configuration, validates input, separates liveness from dependency readiness, applies restricted CORS, emits request identifiers, and avoids secrets in source.

Upcoming identity work must use established password hashing, short-lived sessions/tokens, organization-scoped RBAC, review membership checks, and negative tenant-isolation tests. Uploaded files require MIME/signature validation, size limits, generated storage keys, malware-scanning compatibility, and no direct path trust.

Phase 2 implements local development/test authentication with scrypt password hashing and short-lived HMAC-signed bearer tokens. Local authentication cannot be configured for staging or production. Tokens identify a user but do not cache roles or organization access. Every tenant request requires `X-Organization-ID` and resolves the active database membership again, so removal revokes an already-issued token's tenant access immediately.

Tenant-owned repository calls require organization scope. Cross-organization and unauthorized same-organization review lookups return the same not-found response to prevent identifier inference. Owner/Administrator have organization-wide review visibility; Lead Reviewer, Reviewer, Statistician, and Viewer visibility is ownership/assignment scoped, with independent mutation permissions. See ADR-005 for the accepted policy.

The local Next.js sign-in route exchanges credentials server-to-server, verifies organization context before establishing a session, and stores the bearer token and organization ID in HTTP-only, SameSite=Lax cookies. Browser code never receives or persists the token. Production sets Secure cookies. Review ownership transfer, archive/restore, and member changes repeat backend authorization and same-tenant membership checks.

Production hardening will add secure headers, rate limiting, signed object access, TLS termination, secret management, dependency scanning, backup/restore tests, and security-event monitoring. Authentication must never be weakened to make tests pass.

Export creation is restricted to Owner, Administrator, and assigned Lead Reviewer roles; metadata
and downloads still require active Review access and tenant scope. Artifact downloads recompute the
SHA-256 checksum before returning bytes. CSV cells beginning with spreadsheet formula prefixes are
neutralized, XLSX text is emitted as inline strings rather than formulas, filenames are generated
from sanitized project slugs, and export responses are served through an authenticated server-side
proxy in the UI.

Identification sources, executions, event histories, citation links, and raw artifacts repeat
Organization and Review scope in persistence and repository predicates. Composite foreign keys
reject cross-tenant sources, strategies, translations, citations, actors, and correction links.
Raw artifact reads authorize the Review before resolving the opaque storage key and verify size and
SHA-256 before returning bytes. Completed execution fields and all discovery links are append-only;
corrections preserve the original scientific record.

Risk of Bias routes use centralized `MANAGE_ROB_INSTRUMENT`, `PERFORM_ROB_ASSESSMENT`, and
`ADJUDICATE_ROB` permissions. Ordinary assessors can retrieve only their own assessment records;
authorized comparison is the reveal boundary. Every instrument, version, assessment, evidence,
comparison, and adjudication lookup repeats Organization and Review scope, and foreign direct IDs
return not-found semantics. Evidence locations are accepted only when their Document's Article has
an active link to the assessment Study. Viewers cannot mutate; reviewers cannot approve instruments
or adjudicate; completed submissions cannot be silently edited.
