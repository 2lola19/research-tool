# ADR-023: Governed AI Screening Assistance and Evaluation

## Status

Accepted for Phase 24.

## Context

Title/abstract screening is a consequential scientific workflow. An AI suggestion can reduce
reviewer effort, but an early false exclusion can remove an eligible study. The existing screening
domain already owns blinded assignments, immutable human decisions, deterministic outcomes, and
progression. The Phase 23 AI substrate owns provider-neutral execution, immutable prompts/models/runs,
structured validation, proposals, and human acceptance. Screening assistance must connect those
systems without making AI output a canonical decision or allowing source text to control execution.

Evaluation also needs a stable reference standard. A curated evaluation case is not an Article, Study,
or screening decision, and a metric result must preserve the exact protocol, model, prompt, task, and
proposal dimensions used to produce it.

## Decision

Phase 24 introduces a Review-scoped, immutable screening policy with three modes:

- `OFF` disables suggestion generation.
- `BLINDED_AI` creates and stores a proposal but withholds its structured output until the assigned
  reviewer has recorded the canonical screening decision.
- `ASSISTED` permits an assigned reviewer to view the proposal before deciding and records the access.

Suggestions are limited to title/abstract screening and require an approved immutable protocol
version. Each proposal link is assignment-scoped and snapshots the protocol hash, criterion hashes,
citation hash, task definition version, AI run, and AI proposal. Human decisions remain in the existing
screening tables. A separate append-only decision link records interaction and disagreement categories.
Access/reveal records are append-only and distinguish assisted pre-decision views from post-decision
reveals.

Evaluation datasets contain explicit human-curated reference decisions and standards. Deterministic
local code computes confusion metrics, coverage, Wilson intervals, calibration bins, threshold
simulations, abstention/maybe rates, and high-risk false exclusions. Evaluation results, case results,
and error classifications are immutable; dataset and result provenance/audit links preserve the
reconstruction chain.

## Consequences

The API and UI can provide useful screening assistance while keeping human workflow authority and
tenant/review boundaries in the existing services. Assignment-level linkage prevents two reviewers
assigned to the same Article from seeing or being credited with one another's proposal. Evaluation
results are comparable only when their immutable protocol/model/prompt/task dimensions match.

The Phase 24 implementation uses the deterministic mock provider only. Full-text assistance, live or
paid providers, autonomous exclusion, automatic acceptance, model training, and Phase 25 work remain
deferred.

## Alternatives rejected

- Writing AI suggestions directly into `ScreeningDecision` would violate human checkpoint and
  append-only workflow invariants.
- Linking proposals only to Articles would be ambiguous when multiple reviewers share an Article.
- Treating evaluation cases as screening decisions would collapse scientific workflow state and
  reference data.
- Using an LLM to calculate metrics or thresholds would make deterministic scientific evaluation
  non-reproducible.
