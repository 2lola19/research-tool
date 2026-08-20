# Staging Activation Recovery

After interruption, read `STAGING_PLAN.md`, `STAGING_STATE.json`, `EXTERNAL_GATES.md`,
`VALIDATION_LOG.md`, `BLOCKERS.md`, and this file. Then run safe-directory Git status/log/HEAD,
inspect only the named disposable Docker project, query the project database head/readiness, and
reconcile scanner/parser/storage/identity/edge resources before continuing.

Resume from `current_gate` and preserve valid evidence. Do not repeat a completed gate unless new
evidence or a genuine defect requires it. Prove ownership before using or changing a container,
volume, database, bucket, scanner, proxy, or temporary file. Do not reset Docker/WSL, alter ACLs,
reset/clean Git, push GitHub, expose public traffic, use customer data, or record secrets.

If a gate needs an account, credential, operator-owned service, DNS, certificate, or institutional
configuration, record `EXTERNAL_CREDENTIAL_REQUIRED` or `EXTERNAL_OPERATOR_ACTION_REQUIRED` with an
exact checklist in `EXTERNAL_GATES.md` and continue independent gates. A timeout is not a pass;
inspect only the related process tree and record `ENVIRONMENT_BLOCKED` when bounded execution cannot
produce evidence.

When the final report and state are complete, create one truthful local documentation checkpoint,
verify the worktree, and stop. Do not start a product phase or production deployment.

## Last recorded checkpoint

On 2026-08-20 the named readiness project was healthy after the image-security
refresh, with PostgreSQL at Alembic head 20260819_0036. The disposable
staging_activation_20260820 database used for live migration and tenant
checks was dropped. The Trivy cache volume is named
research-tool-staging-activation_trivy_cache and is program-scoped; do not
remove it without a fresh ownership check.

The application/worker/frontend image fix is local commit
95446647d25af3708b7b579fcd4769018d6b990d. The activation documentation
records the final READY_WITH_EXTERNAL_GATES classification and the exact
remaining operator actions. On resumption, reconcile the current Git HEAD and
status first, then rerun only the blocked gates after their external
dependencies are supplied.
