# Identity Validation

Status: PASS_WITH_LIMITATIONS

## Local deterministic evidence

The repository has local development authentication and no OIDC adapter. The
focused config, authentication, API security, tenant-isolation, and health
tests passed. They verify that production settings reject local authentication,
SQLite, insecure CORS, and unsafe deployment defaults; malformed local
authentication and authorization paths fail closed, with role and tenant
boundaries covered by the 54-test PostgreSQL tenant-isolation module.

No OIDC issuer, JWKS endpoint, provider account, callback, or test identity was
created. Issuer/audience validation, expiry, key rotation, provider-side
revocation/logout, browser sessions, and real provider role mapping therefore
remain unvalidated.

## Exact operator checklist

Provide an authorized disposable issuer and audience, JWKS/key-rotation policy,
callback URLs for the private staging origin, tenant memberships, role
mappings, expired and malformed token cases, logout/revocation behavior, and
test users for each required role. Configure only secret variable names
defined by the approved adapter, such as OIDC_ISSUER_URL, OIDC_AUDIENCE,
OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, and OIDC_JWKS_URL. Never paste their values
into documentation or commit them.

After configuration, rerun wrong issuer/audience, expired token, rotated key,
missing claim, malformed token, tenant membership, role, browser/session,
logout, and fail-closed startup checks.
