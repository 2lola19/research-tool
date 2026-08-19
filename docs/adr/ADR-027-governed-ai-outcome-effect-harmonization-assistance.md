# ADR-027: Governed AI outcome and effect-estimate harmonization assistance

- Status: Accepted
- Date: 2026-08-18
- Scope: Phase 28

## Context

Outcome mapping and effect-estimate records are canonical scientific inputs to later analysis.
The repository already owns deterministic validation and write behavior in `OutcomeService`. A
separate AI outcome system would duplicate conversion, compatibility, and provenance rules and
could silently change the meaning of an extracted value.

## Decision

Add one provider-neutral `OUTCOME_MAPPING_SUGGESTION` task over the existing AI execution ledger.
Each request pins the Review, Study, verified extraction value snapshot, immutable outcome version
and hash, allowed canonical units/windows/scales/measures, processed Article-linked Documents,
parser runs, selected chunks, prompt/model/task versions, and input hashes.

The structured output may be a mapping candidate, a reported effect candidate, or an abstention.
Evidence must identify an exact pinned document/chunk/source block and contain a bounded quote.
Deterministic validation rejects identity mismatches, fabricated evidence, unsupported references,
value changes, conversions, calculations, incompatible measures, unsafe numeric values, and
incomplete reported-effect metadata. Evaluation metrics are descriptive only.

AI output is never canonical. A human disposition is append-only. `EDITED` dispositions require
an explicit human payload; `ACCEPTED` is allowed only for a valid candidate whose kind matches the
explicit canonical action. Canonical writes call the existing `OutcomeService` with human/manual
or reported-origin semantics. The resulting mapping or effect estimate receives human provenance
linking back to the AI proposal, while the proposal and all attempts remain immutable.

## Security and tenant boundaries

All persistent records repeat Organization and Review scope where needed and use composite foreign
keys. Proposal, evaluation, review, and error routes require a path-scoped Review ID; direct IDs
are never resolved without tenant/review authorization. Generic AI routes reject this task so its
structured content cannot bypass the dedicated safeguards. Source Documents must belong to the
Review and be linked to the Study's Article. AI cannot access or mutate canonical records through
the frontend or provider.

## Consequences

The feature provides offline deterministic fixtures, typed API routes, evaluation datasets, and a
review panel while remaining useful without paid providers. Humans must supply the canonical
payload when accepting or editing a proposal. No automatic conversion, effect calculation,
pooling, or analysis readiness change is introduced. PostgreSQL/live-provider and worker
execution validation remain later production-phase gates.

## Rejected alternatives

- Creating a second AI-owned mapping/effect table as scientific truth: rejected because it would
  duplicate the canonical outcome substrate.
- Allowing the model to convert units or calculate effects: rejected because those operations are
  deterministic scientific logic and require explicit review policy.
- Automatically accepting a validated proposal: rejected because AI is not a human harmonizer and
  must not bypass the existing canonical service or provenance ledger.
