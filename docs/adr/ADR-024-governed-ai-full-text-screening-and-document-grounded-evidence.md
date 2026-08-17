# ADR-024: Governed AI full-text screening and document-grounded evidence

## Status

Accepted for Phase 25.

## Context

Full-text eligibility is a consequential human scientific checkpoint. Unlike title/abstract
triage, a suggestion depends on the exact acquired document and parser representation. A replaced
PDF, new parser run, changed protocol, or changed selected text must not silently reinterpret an
old model response. False exclusions remain the primary safety risk. Missing supplements, parser
omissions, inaccessible tables, and ambiguous criteria must remain uncertainty rather than become
exclusion.

The platform already owns canonical full-text assignments and decisions in `ScreeningService`,
canonical structured document blocks behind `DocumentParser`, and immutable provider-neutral AI
runs/proposals. Phase 25 must connect those systems without creating a parallel screening engine.

## Decision

`FULL_TEXT_SCREENING_SUGGESTION` is a versioned critical-risk task on the Phase 23 AI substrate. A
proposal link pins Organization, Review, full-text assignment, reviewer mode, approved
ProtocolVersion and exclusion-criteria hashes, Article/citation, immutable acquired Document (the
source artifact version), successful DocumentProcessingRun, parser/version, parsed block-manifest
hash, ordered selected chunk IDs, omitted-chunk hash manifest, selection method/version, prompt,
model, task version, run, and input hash.

The application prepares bounded structured chunks deterministically. Providers receive no tools,
retrieval, network, filesystem, shell, or database access. Paper content is framed as untrusted
scientific data and cannot alter task instructions. Full document text is not copied into the
full-text link; bounded selected input remains in the AI run snapshot and evidence retains only
necessary quotations.

Output permits `INCLUDE`, `EXCLUDE`, `MAYBE`, and `ABSTAIN`. `INCLUDE` means retain at this stage,
not Study Family finalization, extraction authorization, universal synthesis eligibility, or an
outcome decision. `EXCLUDE` requires a pinned criterion plus exact normalized-substring evidence
from the pinned document/version/chunk; document, version, page, section, chunk, quote, size, and
tenant scope are checked deterministically. Reference-list-only evidence cannot by itself support
exclusion. Missing information has structured reasons and is never exclusion.

`BLINDED_AI` is enforced in the service for assignment and direct-proposal reads and for evaluation:
before the assigned reviewer submits a canonical decision, structured proposal content is withheld
and the case cannot enter evaluation. Reveal/access events are append-only. `ASSISTED` records a
pre-decision view. Choosing to use a binary suggestion remains a human action and calls the existing
`ScreeningService`; the proposal itself never writes `ScreeningDecision`, outcomes, progression,
Study, StudyFamily, or PRISMA state.

Staleness is derived without mutating history from current protocol/citation/document/parser/chunk
and task identities. Old proposals remain inspectable but cannot be accepted. The default policy is
single-report primary-full-text evidence. Document roles explicitly include primary, supplement,
appendix, and other supporting material; cross-report Study Family evidence is not enabled in Phase
25 and would require a human-confirmed relationship plus an explicit future policy.

Evaluation uses explicit adjudicated, consensus, final-human, or curated reference standards; an
unadjudicated reviewer is not universal truth. Non-curated labels require a same-Review,
same-Article canonical full-text outcome source and, for adjudicated labels, an actual adjudication;
the reference decision must match that source. Retention is the positive class and a false negative
is AI `EXCLUDE` with reference `RETAIN`. Deterministic results add criterion correctness, evidence
grounding, section analysis, calibration, simulation-only thresholds, and a high-risk false-exclusion
queue. A zero-observed-FN threshold is labeled only for the evaluated dataset and is not deployment
policy.

## Consequences

- AI cannot auto-exclude, complete a stage, progress an Article, change PRISMA, or accept itself.
- Replacement/reprocessing produces stale immutable history rather than silent refresh or caching.
- Parser adapters remain provider-neutral; live GROBID is not required.
- Batches isolate runs and failures and create no combined prompt or stage side effect.
- Live/paid providers, OCR/computer vision, multi-report evidence, automatic exclusion, active
  learning, and model training remain deferred.
