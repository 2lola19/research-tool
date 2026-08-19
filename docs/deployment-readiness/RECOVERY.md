# Deployment Readiness Recovery

Use this procedure after laptop shutdown, terminal/Codex restart, Docker process failure, database
container failure, network interruption, timeout, or context loss. This program is deployment
readiness only; V1 development is complete and no Phase 39 may be created.

## Required recovery order

1. Read `DEPLOYMENT_PLAN.md`, `DEPLOYMENT_STATE.json`, this file, `VALIDATION_LOG.md`,
   `BLOCKERS.md`, `ENVIRONMENT_INVENTORY.md`, `SECURITY_REVIEW.md`,
   `OPERATIONS_REHEARSAL.md`, and `DEPLOYMENT_REPORT.md`.
2. Read `AGENTS.md`, `ARCHITECTURE.md`, the relevant deployment/security/database/provenance/testing
   documents and ADRs when a code/configuration correction is under consideration.
3. Run safe-directory read-only `git status --short --branch`, `git log --oneline -10`, and inspect
   `HEAD`. Reconcile `DEPLOYMENT_STATE.json` baseline and last checkpoint with Git before resuming.
4. Inspect Docker project state and database/container state non-destructively. Prove ownership before
   treating any container, volume, database, backup, or temporary file as disposable.
5. Preserve valid partial work and evidence. Never reset to an earlier stage merely to make state
   files agree. Never discard unexpected user work.
6. Inspect interrupted processes, truncated files, stale locks, generated runtime output, and backup
   checksums. Stop only relevant validation processes after exact process-tree inspection.
7. Update `DEPLOYMENT_STATE.json` with the recovery boundary and continue the first incomplete durable
   stage. Do not repeat a completed stage unless new evidence or a real defect requires correction.

## State interpretation

`current_stage` is the active deployment stage; `last_completed_stage` is the last durable stage with
recorded evidence. `checkpoint_status` is one of `NOT_READY`, `READY_FOR_CHECKPOINT`,
`CHECKPOINT_PENDING`, or `CHECKPOINTED`. `environment_gates` must distinguish `PASS`, `FAIL`,
`ENVIRONMENT_BLOCKED`, `EXTERNAL_CREDENTIAL_REQUIRED`, `EXTERNAL_DEPLOYMENT_GATE`, `DEFERRED`, and
`NOT_STARTED`.

If state says a milestone is complete but its recorded local commit does not exist, set
`checkpoint_status` to `CHECKPOINT_PENDING`; do not silently advance or rewrite history. Completed
deployment commit SHAs are durable recovery checkpoints. Reconcile state with `git show` and
`git status` before continuing.

## Local Git checkpoint policy

Validated local commits are authorized for meaningful deployment control-plane milestones and genuine
deployment fixes. Before every commit confirm the scope is complete, scientific/security/tenant/
provenance review is complete, required gates are pass or truthfully blocked, inspect status and
unstaged/staged diffs, run both diff checks, audit secrets/artifacts/dumps/caches, stage only intended
files, verify the commit and worktree, and record its SHA in state and the relevant report/log.

Never push, force-push, publish releases, alter remotes/settings/global Git configuration, reset,
clean, broad restore, rebase/rewrite history, delete branches/tags, modify `.git` ACLs/permissions,
recreate the repository, or operate on another repository.

The current full-access environment expects normal local commits. A historical `.git/index.lock`
restriction is not a reason to stop. If an actual lock error recurs, inspect non-destructively,
check whether another Git process is active, do not delete the lock or change ACLs, preserve all
work, set `commit_pending: true`, `checkpoint_status: CHECKPOINT_PENDING`, record `LOCAL_COMMIT_PENDING`,
and stop at that durable checkpoint for minimum manual intervention.

## Docker/database safety

Use only an explicit project-named disposable Compose stack and databases proven to belong to it.
Never factory-reset Docker, prune globally, delete VHDs, repair WSL, remove unrelated resources,
drop production/customer databases, overwrite a source database during restore, or use destructive
resets to make a check pass. If Docker is unhealthy, record `ENVIRONMENT_BLOCKED_DOCKER` and continue
independent gates.

## External gates and model policy

Do not fabricate OIDC, cloud storage, malware, GROBID, TLS, shared-rate-limit, paid-provider, or
institutional evidence. Record exact operator actions in `BLOCKERS.md`. Use the currently selected
model normally; do not switch autonomously. Only an unresolved scientific, security, migration, or
architectural issue justifies `MODEL_ESCALATION_RECOMMENDED`; preserve work and stop at a durable
checkpoint if that status is necessary.

## Completion

When `GO_NO_GO` is complete, update state/report/log/blockers, record the final classification and
local SHA(s), verify the worktree, and stop. Do not start another development phase, deploy public
traffic, or push GitHub.

## Current durable boundary

The current evidence-backed recommendation is `READY_WITH_EXTERNAL_GATES`. The control plane is at
`COMPLETE` with `checkpoint_status=CHECKPOINTED`, `commit_pending=false`, and validated local
checkpoint `208de49f8b16e6ef3b90104157876fd01b472831`. A fresh session must reconcile that SHA with
Git HEAD/history before any action; it must not push or start another development phase.

The validated source changes include PostgreSQL portability corrections, ORM/migration metadata
alignment, workflow invariant migration `20260819_0036`, healthcheck corrections, and opt-in live
PostgreSQL validation plumbing. Preserve these changes and all valid deployment evidence. Do not
reset to the V1 baseline merely to make state files agree. After a successful local commit, record
the exact SHA in `DEPLOYMENT_STATE.json`, `DEPLOYMENT_REPORT.md`, and the validation log, then verify
`git show`, `git status`, and the intended clean/safely-scoped worktree. The state-finalization
documentation commit may be newer than the phase checkpoint; preserve both commits and do not reset
merely because HEAD is newer.

The external gates remain explicit: OIDC and secret-manager configuration, approved S3-compatible
storage, malware scanning, live GROBID, TLS/reverse proxy, shared multi-replica rate limiting,
approved Python/image scanners, and diagnosis of the broad integration timeout. Their absence is
not permission to fabricate evidence or to call the result production-ready.
