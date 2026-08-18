# ADR-025: Governed AI structured extraction and document-grounded value provenance

- Status: Accepted
- Date: 2026-08-17

## Context

Structured extraction is consequential scientific work. The platform already has immutable
`ExtractionSchemaVersion` contracts, human extraction runs, typed manual values, verification,
adjudication, Study Families, and parsed document evidence. AI assistance must fit those systems
without becoming an extractor, verifier, or parallel canonical store.

## Decision

`STRUCTURED_EXTRACTION_SUGGESTION` is a critical-risk, mandatory-human-review task on the existing
provider-neutral AI substrate. Each run pins the assigned human `ExtractionRun`, exact schema ID and
hashes, Study and explicitly allowed Article/Document set, document processing and parser identity,
parsed-content hashes, bounded ordered chunks and omissions, task/prompt/model/provider snapshots,
and rendered input hash. Document text is framed as inert, untrusted scientific content.

The immutable proposal contains exactly one envelope for every requested schema field. Field IDs,
types, options, constraints, and units come only from the pinned schema. Scalar types already safe in
the manual extraction domain are supported; unsafe structured/effect-estimate fields block readiness.
Every non-missing value requires reconstructable evidence against a pinned document, chunk, page and
section metadata where present, a short exact-normalized quote, and deterministic hashes. Invalid
fields remain inspectable, but cannot be accepted; aggregate validity records completeness and field
results.

Reported/source text is distinct from normalized typed value and unit. The model may identify source
inputs but performs no conversions, pooling, imputation, or other hidden derivations. Conflicts,
missing supplements, unreadable tables/figures, parser limitations, ambiguity, non-reporting, and
abstention are explicit states. Figure digitization and OCR are out of scope.

OFF, BLINDED_AI, and ASSISTED policies reuse the screening mode vocabulary. In BLINDED_AI, values,
missingness, confidence, evidence, and validation are withheld on every extraction endpoint until the
assigned human submits canonical extraction. Reveal is audited and comparison-only. In ASSISTED mode,
a human may accept, edit, reject, or leave a field unresolved. Accept/edit calls the existing manual
extraction service; canonical provenance names the human actor and links the immutable AI proposal.
AI never counts toward dual extraction, verification, or adjudication.

Schema, document/parser/content/chunk, task, and prompt changes make a proposal stale without mutation
or automatic rerun. Repeated runs coexist. Batch work is bounded and isolated per assignment.

Evaluation is field-level and deterministic. Reference standards are curated gold or matched/
adjudicated human extraction; an unverified single extractor is rejected as ground truth. Exact,
normalized, explicit-tolerance, missingness, abstention, invalid proposal, and evidence-invalid results
remain separate. Hallucination and fabricated/invalid evidence are high-risk queues. Confidence bins
are descriptive; threshold results are labelled hypothetical only and can never activate auto-accept.

## Consequences

- AI proposals cannot alter extraction completion, PRISMA, verification, harmonization, synthesis,
  certainty, reporting, or scientific exports until a human writes through the canonical service.
- Cross-report evidence requires an existing canonical Study relationship and an explicit input set;
  sources are never silently merged.
- Existing schema versions do not have a separate approval-decision entity. Their immutable created
  version is the authoritative contract; adding an approval lifecycle is a future schema-domain change.
- Only the deterministic mock provider is exercised. Live providers, OCR/computer vision, training,
  autonomous verification, and autonomous acceptance are deferred.
