# Phase 29 Report - Governed AI Certainty-of-Evidence/GRADE Assistance

## Outcome

Phase 29 implementation is complete. The new `CERTAINTY_SUGGESTION` task is a bounded,
evidence-grounded advisory projection over the existing immutable certainty framework and
`CertaintyService`. It can draft an evidence summary, cite exact supplied source chunks, suggest
framework-permitted domain considerations, or abstain. It cannot calculate or save final certainty,
thresholds, upgrades/downgrades, publication-bias decisions, comparisons, adjudications, or
Summary-of-Findings state.

## Implemented surface

- Added deterministic certainty input preparation, source/chunk manifests, identity/framework/
  choice/magnitude/evidence validation, abstention, and descriptive evaluation metrics.
- Added an immutable tenant/Review-scoped policy, proposal-link, access, human-review,
  evaluation-dataset/result, and error-classification persistence surface.
- Added readiness and proposal orchestration over assessor-owned in-progress assessments, included
  Study identities, Article-linked processed Documents, parser snapshots, and the canonical
  certainty evidence profile.
- Added dedicated API routes and closed the generic `/api/v1/ai/runs` route for
  `CERTAINTY_SUGGESTION`.
- Added explicit human disposition routes and a certainty workspace panel. Accepted/edited domain
  payloads call `CertaintyService.save_domain`; AI output remains non-canonical.
- Added migration `20260819_0030`, deterministic mock fixtures, focused unit/integration tests,
  ADR-028, and relevant documentation updates.

## Validation

- `ruff check .`: PASS.
- `ruff format --check .`: PASS (332 files formatted).
- `mypy backend workers`: PASS (213 source files).
- `python -m compileall -q backend workers tests`: PASS.
- `tests/unit/test_ai_certainty_assistance.py`: PASS (5 tests).
- `tests/integration/test_ai_certainty.py`: PASS (3 tests).
- `tests/integration/test_migrations.py`: PASS (SQLite upgrade/downgrade through `0030`).
- Frontend `npm run lint`: PASS; `npm run typecheck`: PASS; `npm test`: PASS (9 tests);
  `npm run build`: PASS.
- Full `pytest -q`: ENVIRONMENT_BLOCKED after 304 seconds without output; the wrapper left only
  the exact launched pytest parent/workers, which were verified and terminated. This is recorded as
  an environment limitation, not a scientific test pass or failure.
- Secret/credential audit: PASS; no credential patterns found in intended Phase 29 files.
- Scientific/security/provenance review: PASS. Canonical certainty writes remain human and service-
  governed, source and tenant boundaries are pinned, stale/invalid proposals cannot be accepted,
  and no AI statistical or final-certainty path was introduced.

## Checkpoint

The validated local Phase 29 implementation checkpoint exists:

- Commit: `df0a74fd2231e76d61f248b0e1fad398e7ee1566`
- Message: `feat: add governed AI certainty-of-evidence/GRADE assistance`
- Parent: `f47561973e697ac30a87c41a865d146b18e11246`
- Worktree after verification: clean
- GitHub operation: none

This SHA is the durable Phase 29 recovery checkpoint. A separate local metadata commit records
the resulting SHA in the execution state and this report; the phase checkpoint remains the commit
above.
