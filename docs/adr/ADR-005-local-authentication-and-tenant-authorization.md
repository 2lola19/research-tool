# ADR-005: Local Authentication and Tenant-Scoped Authorization

- Status: Accepted
- Date: 2026-08-10

## Context

The platform needs a runnable identity system before selecting a production identity provider. Organization isolation is a security invariant: caller-supplied organization and review identifiers cannot be trusted, removed memberships must stop working immediately, and protected identifiers must not reveal resources across tenant boundaries.

## Decision

Define authentication and identity-repository protocols that application services consume. The development/test provider uses scrypt password hashes and short-lived HMAC-signed bearer tokens. Tokens identify only the user; every tenant request resolves a fresh active membership from the database using the required `X-Organization-ID` context.

Organization roles are Owner, Administrator, Lead Reviewer, Reviewer, Statistician, and Viewer. Owner and Administrator can access every review in their organization. Other roles see only reviews they own or are explicitly assigned. Mutation permissions are checked independently from visibility. Repository operations require organization scope, and inaccessible review identifiers return the same 404 response as nonexistent identifiers.

Membership removal is soft and immediately invalidates existing tokens because actor context is database-resolved per request. The final Owner and members who still own reviews cannot be removed. Local authentication is rejected outside development/test configuration. No external authentication SaaS is introduced in this phase.

## Consequences

- Production authentication can implement the provider protocol without changing review or membership business logic.
- Local tokens are not production credentials and the local signing secret must remain outside source control.
- Application-layer tenant scoping is mandatory. PostgreSQL row-level security remains a future defense-in-depth option, not the primary policy boundary.
- Every new tenant-owned repository must accept organization/actor scope and add negative cross-tenant tests.
