# Autonomous Build Recovery

Use this procedure after a shutdown, terminal closure, Codex restart, network loss, context loss,
sandbox interruption, test timeout, Windows spawn `EPERM`, or temporary-directory ACL failure.

## Required recovery order

1. Read `ARCHITECTURE.md`, `AGENTS.md`, `docs/IMPLEMENTATION_STATUS.md`, `docs/ROADMAP.md`, the
   applicable domain documents, `docs/autonomous-build/MASTER_PLAN.md`,
   `docs/autonomous-build/EXECUTION_STATE.json`, this file, and relevant ADRs.
2. Run read-only `git status --short --branch` and `git log --oneline -10` with the repository’s
   configured safe-directory path.
3. Reconcile Git `HEAD`, execution state, current files, migrations, tests, and the current phase
   report. Git is evidence, not permission to discard valid uncommitted work.
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

`validation` must distinguish `PASS`, `FAIL`, `ENVIRONMENT_BLOCKED`, and `DEFERRED`; a blocked
environment gate is never reported as a pass. `files_in_progress`, `last_completed_action`, and
`next_action` identify the safest resume point.

## Git checkpoint recovery

If a completed phase cannot be committed because `.git/index.lock` or another Git sandbox
restriction is not writable, stop mutation attempts. Set `commit_pending: true`, set
`status: LOCAL_COMMIT_PENDING`, record the truthful commit message and exact files, and stop at
that phase. The user can run the exact manual checkpoint command printed in the final handoff;
afterward a fresh session resumes by reconciling `HEAD` with this state file.

Never push to GitHub and never repair this condition by changing `.git` permissions or ACLs.
