# ADR-035: Production Deployment and Operational Readiness Boundary

- Status: Accepted for the V1 controlled-deployment package
- Date: 2026-08-19

## Context

The local topology already has PostgreSQL migrations, liveness/readiness endpoints, JSON logs,
request IDs, non-root containers, durable workflow leases, and a deterministic worker. It did not
fail closed on several unsafe production defaults, expose low-cardinality request diagnostics, or
drain the worker on supported termination signals. Production infrastructure is intentionally not
available to this autonomous build.

## Decision

- Staging and production settings reject local authentication, SQLite, debug logging, wildcard or
  non-HTTPS CORS, and disabled migration-head readiness. The expected Alembic revision is explicit.
- API responses receive baseline security headers. Request middleware validates correlation IDs,
  emits structured completion logs, propagates a bounded trace ID, and records dependency-free
  low-cardinality request counters/durations. Metrics never include tenant or object identifiers.
- Password-token issuance has a bounded process-local limiter with `429` and retry metadata. A
  multi-replica deployment must add an edge/shared-store limiter; the local limiter is not treated
  as distributed security authority.
- The worker polls through the existing orchestration service, installs SIGINT/SIGTERM handlers
  when supported, disposes its database engine on exit, and leaves lease/recovery semantics to the
  existing durable workflow layer.
- Compose and container images retain non-root users, add health checks/grace periods, and use
  `npm ci`. Production image digests, TLS, secrets, OIDC, object storage, malware scanning, and
  backup infrastructure remain deployment gates.

No scientific table, Article/Study model, approved protocol, provenance record, or migration was
changed by this phase. Operational state remains separate from scientific data and provenance.

## Rejected alternatives

- Trusting arbitrary forwarded client headers: this would make rate limits and audit correlation
  spoofable behind an unconfigured proxy.
- Embedding a vendor metrics/tracing SDK or shared rate-limit store: that would add an unreviewed
  deployment dependency without available infrastructure. The protocol boundary remains open.
- Automatic audit purge, database reset, or destructive restore: this could destroy scientific
  reconstruction and is outside autonomous authority.
