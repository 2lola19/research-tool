# Research Tool Controlled Deployment Readiness Plan

Status: COMPLETE_WITH_EXTERNAL_GATES_PENDING_LOCAL_CHECKPOINT

This is the deployment-readiness program for the completed V1 release candidate. It is not a new
development phase, does not create Phase 39, and does not add product features. The V1 baseline is
the local checkpoint `a4156e32c969efcbf4363f02413b58dabf6d4dd1` (`a4156e3`).

## Objective and final classifications

Convert the repository-controlled V1 classification `READY_WITH_DOCUMENTED_LIMITATIONS` into an
evidence-backed controlled-staging decision. Every gate is recorded as `PASS`, `FAIL`,
`ENVIRONMENT_BLOCKED`, `EXTERNAL_CREDENTIAL_REQUIRED`, `EXTERNAL_DEPLOYMENT_GATE`, `DEFERRED`, or
`NOT_APPLICABLE`; a blocked gate is never silently treated as a pass.

The final classification must be exactly one of:

- `READY_FOR_CONTROLLED_STAGING` — the supported candidate has evidence sufficient for controlled
  staging with non-sensitive or explicitly authorized test data. This is not production launch,
  public traffic, clinical use, or autonomous publication.
- `READY_WITH_EXTERNAL_GATES` — repository and safely executable checks do not expose a release
  blocker, but one or more real-environment, credential, institutional, or infrastructure gates
  remain to be completed by an authorized operator.
- `NOT_READY` — a release-blocking defect, data-integrity failure, unsafe configuration, unresolved
  critical/high security finding, failed migration/restore, tenant leak, scientific safeguard
  bypass, unrecoverable state, or supported-target startup failure remains.

Do not claim production readiness merely because a local rehearsal passes.

## Durable stages

The machine-readable state is `DEPLOYMENT_STATE.json`; this plan and the companion logs are the
human-readable control plane. Resume stages in order, preserving valid partial evidence:

1. `BASELINE`
2. `ENVIRONMENT_INVENTORY`
3. `CONTAINER_VALIDATION`
4. `POSTGRESQL_VALIDATION`
5. `BACKUP_RESTORE`
6. `OBJECT_STORAGE`
7. `PARSER_VALIDATION`
8. `SECURITY_CONFIGURATION`
9. `DEPENDENCY_SCANNING`
10. `OBSERVABILITY`
11. `WORKER_RECOVERY`
12. `TENANT_REHEARSAL`
13. `ROLLBACK_REHEARSAL`
14. `FINAL_REGRESSION`
15. `GO_NO_GO`
16. `COMPLETE`

Scientific integrity, provenance continuity, frontend readiness, OIDC, TLS/proxy, rate limiting,
malware scanning, and external credential gates may be validated or documented within the relevant
stage, but must also be visible in the final report.

## Operating boundary

Only the repository and explicitly project-scoped disposable validation resources are in scope.
Never use production/customer data, publish traffic, change public DNS, buy cloud resources, activate
paid providers, expose credentials, modify unrelated projects, or perform Docker/WSL/ACL/security
software repair. If Docker is unhealthy, inspect it non-destructively, record
`ENVIRONMENT_BLOCKED_DOCKER`, and continue independent checks.

Local Git checkpoints are authorized only after a meaningful control-plane milestone or genuine
deployment fix has passed its required validation and scientific, security, tenant, and provenance
reviews. GitHub remains out of scope. Before every local commit:

1. confirm implementation/milestone completion and required reviews;
2. ensure gates are `PASS` or truthfully blocked/deferred;
3. run `git status`, inspect the unstaged diff, and run `git diff --check`;
4. audit secrets/credentials and exclude unrelated files, caches, runtime output, host files, and
   database dumps;
5. stage only intended deployment-readiness files;
6. inspect `git diff --cached --stat` and `git diff --cached`;
7. run `git diff --cached --check`;
8. commit one truthful, phase-specific deployment message;
9. verify the commit, resulting worktree, and recorded SHA in this state file and the relevant log.

Prohibited operations include `git push`, force-push, releases, repository-setting changes,
remote changes, `git reset --hard`, `git clean`, broad restore, history rewriting, branch/tag
deletion, global Git configuration changes, `.git` ACL/permission changes, `git init`, repository
recreation, and operations on another repository. If `.git/index.lock` actually fails, diagnose
without deletion or ACL surgery, check for an active Git process, preserve work, record
`LOCAL_COMMIT_PENDING`, and stop only at the durable checkpoint for manual intervention.

## Cost-aware model policy

Use the currently selected model for normal implementation and validation. Do not stop merely
because another model may be stronger and do not switch models autonomously. Escalate only for a
genuinely unresolved scientific, security, migration, or architectural issue that cannot be
resolved confidently. If required, preserve work, set `status` to
`MODEL_ESCALATION_RECOMMENDED`, explain the exact issue in state/blockers, and stop at a durable
checkpoint.

## Gate method

Use bounded, reproducible checks. Record commands, timestamps, tool versions, target scope, result,
and evidence paths in `VALIDATION_LOG.md`. Inspect exact process trees before stopping no-output
commands. Do not call a timeout a pass. Do not weaken tests or coverage thresholds.

### Environment and containers

Inventory versions and names without printing secret values. Run `docker compose config --quiet`,
inspect build contexts and Dockerfiles, then build and start only a project-named disposable stack
if the Docker daemon is healthy. Validate migrations, non-root execution, health/readiness,
dependencies, startup, logs, and no secrets in image layers. Never use broad prune/reset or delete
unrelated resources.

### PostgreSQL, concurrency, and recovery

Use only a disposable PostgreSQL target. Validate connectivity, the complete Alembic chain/current
head, constraints/indexes/tenant composite keys, transactions, uniqueness, immutability and
append-only behavior, bounded concurrent allocators/leases/writes, and application readiness. Create
a custom-format backup, record checksum/size, restore into a different disposable database, and
verify migrations, representative scientific/provenance/audit records, tenant separation, and
health. Do not overwrite or reset the source database.

### Storage, parser, and security boundaries

Exercise an already available S3-compatible service only if it is explicitly disposable and
supported; do not provision paid cloud infrastructure. Verify opaque keys, metadata, length,
checksums, retrieval, missing/tampered objects, authorization, duplicate/retry behavior, and
read-only reconciliation. Test a safely available malware scanner or record the external gate.
Exercise GROBID with a bounded representative PDF if available; otherwise record
`ENVIRONMENT_BLOCKED_GROBID`. Review OIDC fail-closed behavior, secret names/rotation boundaries,
TLS/reverse-proxy assumptions, forwarded headers, secure cookies, CORS/host handling, and the
process-local rate limiter versus a required shared/edge control.

### Operations and scientific safeguards

Validate structured redacted logs, request/trace/workflow/review correlation, health/readiness,
metrics, worker health, and internal-only diagnostics. Rehearse worker claim interruption/recovery,
workflow stale-lease/resume/idempotency, live PostgreSQL tenant isolation, a deterministic
end-to-end scientific fixture, audit/provenance continuity, application rollback without destructive
database reset, frontend production artifacts, and bounded broader regression. AI remains advisory;
human checkpoints, canonical scientific services, deterministic calculations, Article/Study
separation, immutable protocols, and append-only provenance/audit must remain authoritative.

## Required artifacts

- `DEPLOYMENT_STATE.json`: machine-readable resume state and gate classifications.
- `ENVIRONMENT_INVENTORY.md`: versions, service/configuration names, availability, and no-secret
  configuration inventory.
- `VALIDATION_LOG.md`: chronological command/evidence log.
- `BLOCKERS.md`: active blockers, external gates, and exact operator actions.
- `SECURITY_REVIEW.md`: threat/configuration/secret/scanner findings and disposition.
- `OPERATIONS_REHEARSAL.md`: database, backup, storage, worker, workflow, tenant, rollback, and
  observability rehearsal evidence.
- `DEPLOYMENT_REPORT.md`: final evidence-backed recommendation and remaining risks.
- `RECOVERY.md`: restart/reconcile procedure for a fresh Codex session.

## Stop conditions

Stop at a durable checkpoint for any critical scientific/security/migration/data-loss/scope or
destructive-operation concern. `NOT_READY` is mandatory for a critical vulnerability, exploitable
tenant leak, data corruption, failed migration or backup restore, canonical scientific bypass,
autonomous consequential AI mutation, retry duplication of canonical records, exposed secrets,
fail-open authentication, unsafe cross-tenant storage, unrecoverable operational state, or failure
to start in a supported target environment. External credentials or missing infrastructure are
classified explicitly and do not justify fabricated evidence.

When `GO_NO_GO` is complete, stop. Do not start another development phase, deploy publicly, or push
to GitHub.
