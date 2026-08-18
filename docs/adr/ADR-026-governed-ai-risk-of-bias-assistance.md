# ADR-026: Governed AI Risk-of-Bias assistance

- Status: Accepted
- Date: 2026-08-18

## Context

Risk-of-Bias assessment is a consequential scientific checkpoint. The repository already owns
immutable declarative instruments, instrument versions and decisions, assessor-owned assessments,
Study Family evidence, deterministic domain/overall rules, independent comparison, adjudication, and
human provenance. AI assistance must reuse that foundation rather than create a second assessor or
parallel Risk-of-Bias engine.

## Decision

`ROB_SUGGESTION` is a critical-risk, mandatory-human-review task on the Phase 23 provider-neutral AI
substrate. Each run and immutable proposal link pins the Organization/Review, assessor-owned
assessment, Study, approved immutable instrument version/content hash, exact signalling questions and
permitted choices, explicit Study Family Articles/Documents, successful processing/parser identities,
bounded selected/omitted chunks, task/prompt/model versions, input snapshot, and hashes. Source text
is untrusted data and providers receive no tools, retrieval, filesystem, network, or workflow authority.

The deterministic validator requires exactly one answer envelope per pinned question. A proposed answer
uses only an instrument-permitted choice and requires exact verifiable evidence with matching
Document/version/chunk/source-block/page/section identity. `ABSTAIN` is valid and conservative. Only
validated signalling answers are passed to the existing declarative instrument rules for provisional
domain and overall suggestions. The model never supplies or calculates those judgments.

`OFF`, `BLINDED_AI`, and `ASSISTED` are versioned Review policies. Blinded reads withhold answer,
rationale, confidence, evidence, validation, domain, and overall content until the assessor submits
the canonical assessment. Assisted reads are assignment-scoped and access is audited. Human question
dispositions are append-only; ACCEPTED/EDITED writes call the existing `RiskOfBiasService` and retain
proposal-linked human provenance. AI cannot satisfy independent dual assessment, adjudicate, submit,
or mutate canonical RoB records. Generic AI endpoints reject or omit this task.

Evaluation datasets are separate curated/adjudicated reference records. Deterministic results report
signalling/domain/overall agreement, evidence grounding, abstention, coverage, confusion counts,
descriptive calibration status, and dangerous underestimation/high-risk queues. Threshold output is
hypothetical only. The bundled instrument remains a demonstration framework and is not complete RoB 2.
Staleness is derived from instrument, assessment, source/parser, parsed-block, and selected-text
changes; history is never silently refreshed.

## Consequences

- Canonical Risk-of-Bias state remains human-authored and uses the existing domain service.
- Article, Study, Document, parser, evidence, AI proposal, evaluation, provenance, and audit records
  remain distinct and tenant/review scoped.
- The deterministic mock provider is sufficient for local safety and integration tests; paid/live
  providers, complete published instruments, OCR, retrieval, and autonomous assessment remain deferred.
- Migration `20260818_0028` adds only the governance/provenance/evaluation bridge and does not alter
  historical Risk-of-Bias tables.
