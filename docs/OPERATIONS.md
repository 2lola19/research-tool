# Operations and Recovery

The application separates scientific data, workflow state, provenance, and audit history. An
operational repair must preserve those boundaries and must not invent or rewrite a scientific
decision.

## Health and observability

- `GET /health/live` checks only that the API process is serving.
- `GET /health/ready` checks PostgreSQL connectivity and, when
  `DATABASE_REQUIRE_MIGRATIONS=true`, that `alembic_version` equals the configured head.
- `GET /health/metrics` returns dependency-free Prometheus text with route labels that redact UUID
  and numeric path identifiers. Keep this endpoint on an internal network or scrape path.
- JSON logs include request ID, trace ID, method, low-cardinality route, status, and duration. The
  `traceparent` header is accepted only for a valid W3C trace ID; no request body, bearer token,
  organization ID, query string, or provider response is logged.

The request limiter is intentionally process-local and applies to password-token issuance. It is a
fail-closed application guard, not a distributed abuse-control system. A multi-replica deployment
must add an edge or shared-store limit before exposing authentication publicly.

## Worker shutdown and recovery

The worker polls through the provider-neutral workflow runner, handles SIGINT/SIGTERM where the
runtime supports signal handlers, and disposes its database engine in `finally`. A shutdown stops
new polling; an in-flight claim remains governed by its lease and the explicit recovery command.
Compose also checks that the worker process is alive; operational health still requires a current
`workflow_workers` heartbeat in PostgreSQL rather than treating a live process as proof of a healthy
database connection.
Use `python -m workers.review_worker --recover-expired` only as an authorized, bounded operational
action. Inspect attempts, events, checkpoints, retry class, and provenance before requeueing.

`AWAITING_HUMAN`, dead-lettered jobs, and scientific writes are never silently replayed. Follow
`docs/autonomous-build/RECOVERY.md` for autonomous-build state and local Git checkpoint recovery.

## Backup and restore runbook

The commands below are templates. Replace placeholders only in an approved environment and never
write credentials into command history or a repository file.

1. Quiesce or coordinate application/worker writes according to the deployment change plan.
2. Create an encrypted, access-controlled custom-format PostgreSQL backup and record its checksum:

   ```powershell
   pg_dump --format=custom --no-owner --file=<protected-path> "$env:DATABASE_URL"
   Get-FileHash <protected-path> -Algorithm SHA256
   ```

3. Back up object storage using the provider's versioned, encrypted mechanism. Verify every
   exported object manifest against the stored size and SHA-256 metadata; do not copy secrets or
   expose opaque storage keys in logs.
4. Restore only into a disposable or explicitly authorized target. Do not drop a production
   database as an autonomous action:

   ```powershell
   createdb <recovery-db>
   pg_restore --clean --if-exists --no-owner --dbname=<recovery-db> <protected-path>
   ```

5. Run `alembic current`, the health endpoints, migration/integrity checks, and the tenant
   isolation suite. Reconcile workflow attempts/checkpoints and compare object manifests before
   reopening traffic.
6. Record backup ID, source/head revision, checksum, restore target, operator, timestamps, test
   results, and any limitation in the protected operations record. Retain the original backup.

Audit events and scientific provenance are append-only application records. This V1 repository
does not implement an automatic deletion job or a legal retention policy. Retention, encryption,
access review, immutable backup storage, and disposal must be set by the operating organization;
no purge is a routine recovery step.

## Incident handling

For suspected cross-tenant access, provenance drift, credential exposure, migration mismatch, or
object corruption: restrict traffic, preserve logs/backups and the current worktree, identify the
affected Review/Organization scope, and stop automated retries that could repeat consequential
writes. Rotate credentials through the secret manager, inspect audit/provenance and workflow
events, and record a bounded incident decision. Never hide a failed check by weakening auth,
blinding, migration constraints, or scientific readiness rules.
