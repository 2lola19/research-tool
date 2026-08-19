# Autonomous Build Recovery

Use this procedure after a shutdown, terminal closure, Codex restart, network loss, context loss,
sandbox interruption, test timeout, Windows spawn `EPERM`, or temporary-directory ACL failure.

## Required recovery order

1. Read `ARCHITECTURE.md`, `AGENTS.md`, `docs/IMPLEMENTATION_STATUS.md`, `docs/ROADMAP.md`, the
   applicable domain documents, `docs/autonomous-build/MASTER_PLAN.md`,
   `docs/autonomous-build/EXECUTION_STATE.json`, this file, and relevant ADRs.
2. Run read-only `git status --short --branch` and `git log --oneline -10`. If Git reports dubious
   ownership, use a per-command `-c safe.directory="C:/path/to/repository"` option; never change
   global Git configuration or `.git` permissions.
3. Reconcile Git `HEAD`, execution state, phase checkpoint records, current files, migrations,
   tests, and the current phase report. Git is evidence, not permission to discard valid
   uncommitted work.
4. Inspect all partial implementation before editing. Preserve valid partial work and resume the
   first incomplete durable step for the recorded phase.
5. Check for truncated files, NUL-filled/corrupted files, half-written migrations/tests, broken
   imports, interrupted generated output, temporary files, and stale lock files.
6. Remove only clearly disposable runtime artifacts created by validation. Never use broad clean,
   reset, restore, ACL, permission, repository-recreation, or history-rewriting operations.
7. Update `EXECUTION_STATE.json` at the recovery boundary, then continue the phase loop.

## State interpretation

`current_step` is the last durable phase boundary. Expected values include `PLANNING`,
`IMPLEMENTING`, `MIGRATION_COMPLETE`, `BACKEND_VALIDATION`, `FRONTEND_VALIDATION`,
`SCIENTIFIC_REVIEW`, `SECURITY_REVIEW`, `PROVENANCE_REVIEW`, `FIXING_FINDINGS`,
`DOCUMENTING`, `READY_FOR_CHECKPOINT`, `CHECKPOINTED`, and `PHASE_COMPLETE`.

The state schema must retain `current_phase`, `current_step`, `last_completed_phase`,
`last_local_commit`, `expected_phase_commit_message`, `commit_pending`, `checkpoint_status`,
validation status, blockers, `next_action`, and `updated_at`. `checkpoint_status` describes the
current phase and uses `NOT_READY`, `READY_FOR_CHECKPOINT`, `CHECKPOINT_PENDING`, or
`CHECKPOINTED`. A completed phase's SHA belongs in `phase_checkpoints` as well as the phase report.

`validation` must distinguish `PASS`, `FAIL`, `ENVIRONMENT_BLOCKED`, and `DEFERRED`; a blocked
environment gate is never reported as a pass. `files_in_progress`, `last_completed_action`, and
`next_action` identify the safest resume point.

## Git checkpoint recovery

The autonomous program may create validated local commits after the phase gates pass. Before every
commit it must confirm implementation completion and scientific/security/provenance review, verify
that every required gate is `PASS` or honestly `ENVIRONMENT_BLOCKED`, inspect `git status`, the
unstaged diff, and `git diff --check`, audit secrets/credentials, exclude unrelated or generated
files, stage only the intended phase files, inspect staged stat/content, run
`git diff --cached --check`, commit one truthful phase-specific message, verify the commit and
worktree, and record the SHA in state and the phase report.

Completed phase commit SHAs are durable recovery checkpoints. Always reconcile `EXECUTION_STATE.json`
with Git `HEAD` before resuming. If state claims a phase is complete but the recorded local commit
does not exist, set `checkpoint_status: CHECKPOINT_PENDING` and treat that phase as pending; never
silently advance. Preserve valid partial work and never reset to an earlier phase merely to make
state files agree.

The current full-access environment is expected to permit normal local commits. Do not stop merely
because a previous session hit a sandbox `.git/index.lock` restriction. If a lock failure actually
recurs, diagnose with non-destructive inspection, check for a genuinely active Git process, do not
delete a lock blindly, do not change ACLs or `.git` permissions, preserve all work, record
`LOCAL_COMMIT_PENDING`/`commit_pending: true`, and stop at that durable checkpoint for minimum
manual intervention.

Never push to GitHub and never repair this condition by changing `.git` permissions or ACLs.

## Model escalation

Use the currently selected model for normal implementation. Do not switch models autonomously.
Only an unresolved scientific, security, migration, or architectural issue that cannot be resolved
confidently justifies escalation. Preserve work, set `status: MODEL_ESCALATION_RECOMMENDED`, record
the exact issue in state and blockers, and stop at a durable checkpoint.
