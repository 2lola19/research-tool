# Deployment Readiness Operations Rehearsal

Status: COMPLETE_WITH_EXTERNAL_GATES

Only the explicit Compose project `research-tool-readiness` and its named disposable databases
were used. The unrelated `school-erp-staging` project was inspected and never modified. No
production/customer data, public traffic, paid provider, DNS, certificate, ACL, WSL, or Docker
factory-reset operation was used.

## PostgreSQL, migration, schema, and concurrency

- `docker compose -p research-tool-readiness run --rm --no-deps migrate`: PASS; full disposable
  chain reached `20260819_0036`.
- Host `.venv` `alembic heads/current/check`: PASS; current and head are `20260819_0036`, and
  `alembic check` reports no new operations.
- Live schema inspection found workflow tenant composite FKs, retry/payload checks, and expected
  workflow/index constraints.
- Four concurrent `SqlAlchemyWorkflowExecutionRepository.claim_next_job` calls against eight
  queued PostgreSQL jobs claimed four distinct jobs and left four queued:
  `POSTGRES_CONCURRENCY_PASS workers=4 claimed=4 unique=4 remaining_queued=4`.
- The PostgreSQL workflow integration selector passed claim/heartbeat/complete, failure/requeue,
  terminal recovery, idempotent resume, and scoped reconciliation.
- No production schema or unrelated database was touched.

## Backup and disposable restore

The worker was paused only during each consistent source backup and restarted afterward. Backups
were created in the named PostgreSQL container with `pg_dump -Fc`; they were not copied to or
committed in the repository.

| Source fixture | Backup SHA-256 | Size | Restore database | Verification |
|---|---|---:|---|---|
| Workflow/tenant fixture | `553abbd737582001a73a36298142e84668815ed8a6b403f0ad14d087ef30ef34` | 632116 | `research_tool_readiness_restore_20260819` | head 0036; 4 reviews; 1 job; 4 job events |
| Provenance fixture | `99ce38b53120b52b698790e68272c07de1ff2625504a9b53055890398cdd477d` | 632106 | `research_tool_readiness_restore_20260819_v3` | head 0036; 4 reviews; 3 audit events; 1 scientific-provenance record; 2 organizations; 9 memberships |

Both restores were into different explicitly named disposable databases and did not overwrite the
source. The restore query that initially referenced a nonexistent table was corrected and rerun;
the restore itself was successful. Restore databases and the known container-local backup remain
owned by this validation project for evidence; no dump is a repository artifact.

## Object storage, parser, and malware boundaries

- Local storage, checksum verification, missing/tampered behavior, and the vendor-neutral fake S3
  adapter tests passed.
- No disposable S3-compatible service was present in Compose or safely available on the host;
  production-style upload/retrieval/reconciliation remains `EXTERNAL_DEPLOYMENT_GATE`.
- Fixture parser and GROBID TEI normalization/limit/failure tests passed. No live GROBID service
  was available, so representative PDF/timeout/version evidence is `ENVIRONMENT_BLOCKED_GROBID`.
- No malware scanner binary or repository scanner adapter was present. No real malware was used;
  scanner integration is an external gate.

## Worker and workflow interruption

- The project worker was stopped and restarted around the live PostgreSQL tenant/workflow checks;
  it returned healthy each time. No unrelated process was stopped.
- A live PostgreSQL recovery probe seeded one deterministic `workflow.noop`, claimed it with a
  five-second lease, closed the claiming session without completion, waited for expiry, requeued
  once, reclaimed once, and completed. Result:
  `POSTGRES_LEASE_RECOVERY_PASS attempts=2 expired_then_completed=1 duplicate_canonical_records=0`.
- The durable workflow integration selector passed lease heartbeat, retry history, terminal failure,
  idempotent manual recovery, resume idempotency, and reconciliation scoping.
- A mid-handler process kill was not claimed: the deterministic noop completes too quickly for a
  safe reproducible kill window. Lease-expiry recovery is the durable crash-equivalent evidence.

## Tenant and scientific rehearsal

- The live PostgreSQL tenant suite passed 54 tests. It covers cross-organization non-enumeration and
  non-read/write for Review, Protocol, Article, Document, Study, extraction, Risk of Bias, analysis,
  AI proposal/run, export, audit, and provenance paths, plus same-organization review scoping.
- Focused live PostgreSQL provenance and audit tests passed. The deterministic V1 lifecycle,
  canonical-state protections, human gates, Article/Study separation, and mock-AI safeguards remain
  supported by the inherited V1 evidence and focused current tests.
- No canonical AI write, tenant leak, duplicate canonical retry record, or append-only violation was
  observed.

## Rollback and observability

- The final backend image was rebuilt from the final source, retagged for migration/worker use, and
  the backend/worker were force-recreated within the named project. Migration compatibility and
  health passed without database downgrade/reset.
- This is an application restart/recreate rehearsal, not a production rollback or destructive
  migration downgrade. Production rollback still requires an operator-approved forward-compatible
  migration plan and preserved backup.
- Final live checks: backend `/health/live`, `/health/ready`, `/health/metrics`, and frontend
  `/api/health` all returned HTTP 200. Metrics content type was Prometheus text.
- Recent backend/worker logs contained zero matches for the audited private-key, password, API-key,
  bearer-token, secret, signed-capability, or access-key patterns.

## Rehearsal evidence table

| Rehearsal | Target | Result | Evidence |
|---|---|---|---|
| PostgreSQL/migrations/concurrency | Disposable PostgreSQL | PASS | Head 0036; Alembic check; bounded claim probe |
| Backup/restore | Two explicitly named disposable DBs | PASS | Checksums/sizes/counts above |
| Object storage/checksum | Local/fake adapter only | PASS_LOCAL / EXTERNAL S3 GATE | Focused storage tests |
| Malware/parser | No scanner; fixture parser | EXTERNAL / ENVIRONMENT_BLOCKED_GROBID | Security review and blockers |
| Worker crash/recovery | Project worker + PG lease probe | PASS_BOUNDED | Stop/start and expiry/reclaim evidence |
| Workflow resume | Disposable PostgreSQL workflow data | PASS | Workflow integration selector |
| Tenant isolation | Live PostgreSQL | PASS | 54-test suite |
| Scientific lifecycle | Deterministic fixture/current focused tests | PASS_WITH_LIMITATIONS | V1 evidence plus focused PG provenance |
| Rollback | Disposable application image/config | PASS_APPLICATION_ONLY | Recreate/health/migration compatibility |
| Observability | Named stack | PASS | Health, metrics, redacted logs |

## External operator actions

Before any broader staging or production-like acceptance, an authorized operator must supply and
validate OIDC, secret management, S3-compatible storage, malware scanning, GROBID, TLS/proxy,
shared rate limiting, and approved Python/image scanners. Exact actions are maintained in
`BLOCKERS.md`; credentials and provider payloads must not be recorded here.
