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

Outcome configuration uses centralized `MANAGE_OUTCOMES`, `HARMONIZE_OUTCOMES`, and
`PREPARE_SYNTHESIS` permissions. Every definition, version, window, unit, scale, mapping, estimate,
candidate set, and readiness query repeats Organization and Review scope. Composite foreign keys
also constrain Study, extraction value, protocol version, evidence location, mapping sources, and
candidate estimates to the same tenant/review. Effect evidence must resolve through an Article in the
target Study Family. Foreign and cross-review identifiers return not-found semantics, viewers cannot
mutate, and scientific history is append-only. Context-keyed unit conversion prevents a generic unit
rule from crossing analytes or dimensions.

Statistical synthesis uses centralized `MANAGE_ANALYSIS` and `RUN_ANALYSIS` permissions. Owner,
Administrator, assigned Lead Reviewer, and assigned Statistician may configure/run; all reads still
require active Review access. Every specification, set, selected estimate, run, weight, sensitivity
result, and artifact lookup repeats Organization and Review scope, with composite foreign keys as a
second boundary. Cross-review candidate/estimate IDs and foreign direct IDs return not-found
semantics. Forest bytes are resolved only after Review authorization and are served through an
authenticated server proxy. Terminal records are immutable and artifact checksums are verified
before use; no statistical provider receives tenant credentials or direct database authority.
