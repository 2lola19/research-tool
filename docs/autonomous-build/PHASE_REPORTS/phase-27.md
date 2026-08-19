# Phase 27 - Governed AI Risk-of-Bias Assistance

## Objective

Add bounded, evidence-grounded Risk-of-Bias signalling-answer assistance while preserving the
existing human assessment, deterministic domain rules, adjudication, submission, audit, and
provenance boundaries.

## Implementation

- Added a versioned `risk-of-bias-suggestion` AI task with strict input/output validation and
  deterministic mock scenarios for success, abstention, malformed, fabricated, stale, and retry
  cases.
- Added a RoB-specific domain validator and evaluator. It pins instrument/version, question
  choices, evidence chunks, document/parser metadata, hashes, abstention, and output grounding.
- Added immutable tenant/review-scoped policy, proposal-link, source, evidence, access, human
  answer-review, evaluation, and high-risk error persistence.
- Added a service and API for policy/readiness, assignment-scoped proposal generation, controlled
  reveal, human answer disposition, evaluation datasets/results, and error classification.
- Reused the existing `RiskOfBiasService` for accepted human answers; no canonical RoB record is
  written by the AI execution path.
- Added the Risk-of-Bias workspace controls and typed frontend API/actions for policy, proposals,
  evidence, disposition, and evaluation summaries.

## Architecture

The feature is an advisory projection over the existing Phase 18 RoB substrate and Phase 23-26 AI
execution/provenance ledger. The AI task can return only allowed signalling-answer envelopes,
grounded evidence, rationale, confidence, and abstention. Deterministic existing instrument rules
derive any non-canonical domain/overall suggestion from validated answers.

## Scientific safeguards

- Exact Review, Study, Study Family, instrument version, domain/question, permitted choices,
  Article/Document, parser/processing, chunk, task, prompt, model, run, and input hashes are
  pinned.
- Evidence must resolve to the active Study Family and exact document/chunk/page/section/source
  block; unsupported quotes, wrong documents, fabricated chunks, stale inputs, and unsupported
  answers are rejected.
- Human reviewers remain authoritative. AI is not an assessor, independent reviewer, adjudicator,
  final domain/overall judge, or submission mechanism.
- Blinded mode withholds proposal content and records access/disclosure events.
- Evaluation reports signalling/domain/overall agreement, evidence grounding, abstention, coverage,
  confusion, descriptive calibration, domain-specific error classes, and dangerous
  underestimation/high-risk queues without inventing a threshold.

## Security and tenant model

All persistent records carry organization/review ownership and composite tenant/review integrity
where relationships cross objects. Read and mutation paths enforce review membership, role,
assessor ownership, and assignment scope. Direct IDs do not bypass these checks. Generic AI routes
cannot create, list, or directly read the governed RoB task outside the dedicated service. Blinded
content is not exposed by the assignment or direct proposal routes.

## Migration

Migration `20260818_0028_ai_rob_assistance.py` adds the linear Phase 27 tables, constraints, indexes,
immutable relationships, and source-manifest block counts. The complete SQLite upgrade to `0028`
and downgrade to base passed manually and through the migration test assertions.

## API and frontend

The dedicated `/api/v1/ai/risk-of-bias` routes cover policy, readiness, batch and assignment
proposal generation, proposal reads, human answer review, evaluation datasets/results, high-risk
queues, and error classification. The existing Risk-of-Bias page now exposes explicit disclosure
mode, readiness, evidence-grounded proposal review, human disposition, and safety metrics. The
server remains the authorization/scientific authority.

## Tests and validation

- Phase 27 unit shard: 5 passed with `pytest --no-cov`.
- Phase 27 integration shard: 3 passed with `pytest --no-cov` using a repository-local temporary
  root; the default Windows temporary root is Access Denied before setup.
- `ruff check backend workers tests`: passed.
- `ruff format --check .`: passed.
- `mypy backend workers`: passed with no issues in 205 files.
- `python -m compileall -q backend workers`: passed.
- SQLite migration upgrade/downgrade: passed.
- Frontend lint and typecheck: passed.
- Frontend Vitest and Next.js build: environment-blocked by Windows `spawn EPERM` after startup/
  compilation; no application workaround was introduced.
- Broad Ruff scan: environment-blocked by the pre-existing inaccessible `.phase24-test-tmp`.
- `git diff --check`: passed. No full-suite PASS is claimed because the interrupted broad run did
  not produce a durable exit result.

## Review findings and fixes

- Fixed a missing `block_count` source-manifest field in the persistence model and migration.
- Fixed UUID conversion at source-manifest persistence boundaries.
- Fixed the integration fixture to use an explicit supported randomized study design.
- Fixed generic AI route handling so governed RoB tasks cannot be created or leaked through generic
  task list/direct-read routes.
- No unresolved critical/high scientific or security finding remains for this phase.

## Limitations and environment blockers

This remains a demonstration-framework integration rather than a claim of complete RoB 2 or
ROBINS-I support. Live PostgreSQL, Docker, GROBID, external scholarly providers, paid AI providers,
and production credentials were not used. Frontend process-spawn and default pytest temp ACL
limitations require host-side validation before controlled deployment.

## Changed files

- Backend AI task, mock, service, domain, persistence, router, and API route modules.
- Migration `20260818_0028_ai_rob_assistance.py` and migration integration assertions.
- Phase 27 unit and integration tests.
- Risk-of-Bias frontend API, actions, and page.
- ADR-026 and the domain/database/API/provenance/security/AI/testing/roadmap/status/open-source
  documentation updates.
- Autonomous-build state, validation, decision, blocker, and phase-report records.

## Checkpoint and next phase

This report is checkpointed at local commit `995c5af` after the explicit diff/secret/staging
review. The next implementation phase is Phase 28, governed AI outcome/effect-estimate
harmonization assistance.
