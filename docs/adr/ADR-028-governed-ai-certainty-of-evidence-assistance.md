# ADR-028: Governed AI Certainty-of-Evidence Assistance

## Status

Accepted for V1 implementation.

## Context

The certainty foundation stores immutable framework versions and canonical human domain/final
judgments. A reviewer may benefit from a bounded evidence summary and a checklist of framework-
permitted domain considerations, but certainty judgments are consequential scientific decisions.
AI must not become a second certainty engine or infer publication bias, thresholds, upgrades,
downgrades, or final certainty.

## Decision

Implement `CERTAINTY_SUGGESTION` as a governed advisory projection over the existing
`CertaintyService`:

- Deterministically pin the assessor-owned in-progress assessment, immutable outcome/framework
  versions, evidence profile, included Studies, explicit processed Documents, parser/block snapshots,
  bounded chunks, and content hashes before provider execution.
- Allow only an evidence summary, exact grounded evidence, framework-permitted domain suggestions,
  confidence, or abstention. Reject identity changes, unsupported domains/choices/magnitudes,
  fabricated quotes, stale sources, final/candidate certainty, thresholds, publication-bias
  inference, and statistical calculations.
- Store proposal links, access events, human dispositions, evaluation datasets/results, and error
  classifications append-only with composite organization/Review integrity.
- Require an explicit human `ACCEPTED` or `EDITED` payload before calling
  `CertaintyService.save_domain`; the existing service remains canonical for domain writes, final
  certainty, submission, comparison, adjudication, and Summary-of-Findings records.
- Keep evaluation descriptive and separate from scientific records. The bundled framework remains a
  structured foundation and is not represented as complete official GRADE support.

## Consequences

The assistant can reduce evidence-navigation effort while preserving human scientific authority,
source traceability, staleness checks, and auditability. It cannot automate certainty decisions,
and evaluation cannot establish clinical thresholds or replace framework validation. No new runtime
dependency or live provider is required.
