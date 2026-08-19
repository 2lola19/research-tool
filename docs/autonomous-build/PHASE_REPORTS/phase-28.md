# Phase 28 report - Governed AI outcome/effect-estimate harmonization assistance

## Objective

Provide bounded, evidence-grounded assistance for mapping verified extraction values and identifying
reported effect estimates while preserving the existing canonical outcome/effect-estimate service.

## Implementation

- Added the governed `OUTCOME_MAPPING_SUGGESTION` task, prompt definition, input/output contracts,
  deterministic mock fixtures, generic-route closure, and structured validation.
- Added deterministic outcome input preparation reusing the extraction chunk selector, exact source
  manifests, allowed-reference manifests, identity/value/evidence/effect safeguards, staleness
  checks, descriptive evaluation metrics, and high-risk error categories.
- Added append-only policy, proposal-link, access, human-review, evaluation-dataset/result, and
  error-classification persistence with tenant/review composite constraints and mutation guards.
- Added Review-scoped API routes for readiness, bounded generation, proposal reads, explicit human
  disposition, evaluation, and error classification.
- Added a typed Next.js client, Server Actions, and a governed panel in the existing outcomes page.
  The panel exposes proposal evidence and requires explicit human canonical JSON for accepted/edited
  writes.

## Architecture and scientific safeguards

AI is an advisory projection over `OutcomeService`. Requests pin the Review, Study, verified
extraction value and snapshot, immutable OutcomeDefinitionVersion/content hash, compatible effect
measures, version-permitted units/windows/scales, Article-linked processed Documents, parser runs,
selected/omitted chunks, and task/model/prompt/input hashes. Output is mapping, reported effect, or
abstention. Exact chunk/source-block identity and a bounded quote are required for non-abstaining
output. Deterministic validation rejects changed extracted values, fabricated evidence, unsupported
references/conversion, calculations, incompatible measures, unsafe numbers, incomplete intervals,
and missing variance scale.

AI does not normalize values, derive effects, impute components, pool estimates, change analysis
readiness, or become a harmonizer. `ACCEPTED` requires a valid candidate whose kind matches the
explicit canonical action. Invalid or changed proposals require `EDITED` plus an explicit human
payload. Canonical writes call `OutcomeService`; AI cannot create a mapping or effect estimate
directly.

## Security, tenant isolation, and authorization

Every route resolves active organization membership and Review access. Proposal, evaluation, error,
and review direct IDs are path-scoped by Review. Composite foreign keys repeat Organization/Review
scope across AI, Study, extraction, outcome, membership, and evaluation records. Documents must be
processed, belong to the Review, and be linked to the Study's Article. Generic AI routes reject the
outcome task. The browser has no authority to bypass server-side checks.

## Provenance and immutability

Proposal links retain source/parser/chunk manifests, selected-text and extraction/outcome hashes,
validation results, task version, and the existing AI run/proposal/attempt chain. Access and human
dispositions are append-only. Accepted/edited canonical records receive `AI_PROPOSAL` source
provenance plus the normal canonical outcome trace. ORM event guards reject updates/deletes of the
Phase 28 scientific history.

## Migration

Migration `20260818_0029_ai_outcome_assistance` follows `20260818_0028` and adds seven outcome-AI
tables, constraints, composite foreign keys, and scoped indexes. A manual SQLite run upgraded to
`0029`, verified the Phase 28 tables, downgraded to the base revision, and verified cleanup.

## API and frontend

The dedicated `/api/v1/ai/outcomes/reviews/{review_id}` API exposes policy, readiness, proposal,
human-review, evaluation, and error routes. The existing `/reviews/{reviewId}/outcomes` page now
offers policy/proposal/disposition forms and renders pinned evidence/validation state. Canonical
mapping and effect forms remain unchanged and still use the canonical outcome routes.

## Tests and validation

- `tests/unit/test_ai_outcome_harmonization.py`: 7 focused tests pass.
- Targeted Ruff, format, strict mypy, backend import/compile checks: pass.
- Targeted changed-file ESLint and `npm run typecheck`: pass.
- Manual SQLite migration upgrade/downgrade through `0029`: pass.
- `tests/integration/test_ai_outcomes.py`: environment-blocked by pytest's Windows repository-local
  temp-root cleanup (`WinError 5`); no durable assertion failure was available, so it is not called
  a pass.
- Broad `npm run lint`: environment-blocked by timeout without output; direct changed-file ESLint
  passes. Prior Vitest/Next build spawn limitations remain documented from Phase 27.
- `git diff --check`, secret review, tenant/review review, provenance review, and scientific-boundary
  review are required at the checkpoint and have no known critical/high finding.

## Review findings and fixes

- Version allowlists initially exposed every review configuration item; fixed by filtering the
  provider manifest to the immutable outcome version's declared unit, scale, and time-window IDs.
- Canonical acceptance initially did not distinguish invalid proposals or candidate/action mismatch;
  fixed by requiring `EDITED` for invalid output and matching candidate kind for `ACCEPTED`.
- Reported effect payload parsing now rejects non-numeric components and malformed source mapping
  UUIDs before invoking the canonical service.
- Proposal, readiness, evaluation, and error reads now enforce AI-review/harmonization
  permissions so an assigned viewer cannot inspect AI evidence through a Review-scoped route.

## Remaining limitations and environment blockers

The feature uses only the deterministic mock provider; no paid model or production credential is
enabled. Live PostgreSQL, durable worker execution, external document storage, and provider
validation remain later phases. The repository's Windows temp ACL and Node process behavior limits
the integration/lint gate in this environment. The feature does not calculate effects or claim
complete scientific harmonization coverage.

## Changed files

Backend AI/service/routes/models/migration, focused unit/integration tests, frontend outcomes client,
actions, and page, ADR-027, relevant domain/API/database/security/AI/provenance/testing/status/
roadmap/open-source documentation, and autonomous-build control-plane logs/state.

## Commit and next phase

The initial restricted-sandbox staging attempt failed with `.git/index.lock` `Permission denied`.
After the execution environment moved to full local access, the validated checkpoint was reconciled
and verified:

- Commit: `f47561973e697ac30a87c41a865d146b18e11246`
- Message: `feat: add governed AI outcome harmonization assistance`
- Worktree after verification: clean
- GitHub operation: none

Next phase: Phase 29, governed AI certainty-of-evidence/GRADE assistance over the existing certainty
service and deterministic rule engine.
