# Infrastructure

The root `compose.yaml` is the supported local topology. Production deployment manifests are
intentionally deferred; see `docs/DEPLOYMENT.md` and `docs/OPERATIONS.md` for the controlled-
deployment boundary. Container images use non-root runtime users, application-level health checks,
grace periods, and no-new-privileges in Compose. Compose defaults are local development values and
must never be promoted as production credentials.
