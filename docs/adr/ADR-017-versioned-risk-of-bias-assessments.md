# ADR-017: Versioned Risk of Bias instruments and independent Study assessments

Status: Accepted
Date: 2026-08-11

## Context

Risk of Bias is a consequential scientific appraisal. A single opaque label or LLM response cannot
preserve the instrument, signalling answers, evidence, independent assessor judgments, disagreement,
or adjudication history needed for reproducibility. Assessments apply to a Study, while supporting
evidence may come from several Articles and Documents in its Study Family.

## Decision

- Keep review-scoped logical instruments separate from immutable instrument versions. Versions store
  ordered declarative definitions, answer and judgment choices, compatible Study designs, optional
  guidance, deterministic rule definitions, and a canonical SHA-256 content hash.
- Record an append-only approval or rejection decision for each version. Only approved versions may
  be used, and every assessment remains pinned to the exact version.
- Store assessments at Study level with assessor, round, revision, structured answers, domain
  judgments, overall judgment, and optional existing `DocumentEvidenceLocation` references.
- Validate every evidence location through Document -> Article -> active Study Family membership.
  Do not bind an assessment to one PDF and do not create a parallel evidence subsystem.
- Keep assessor work blind by returning only the actor's assessments until a user with centralized
  adjudication permission performs comparison/reveal. Comparison is deterministic over signalling
  answers, final domain judgments, and final overall judgment.
- Preserve submitted assessments unchanged. Corrections create one explicit superseding revision.
  Comparison records preserve exact differences; adjudication appends a verified snapshot and never
  overwrites either assessor's submission.
- Implement only two generic, declarative rule forms in this foundation: answer-severity domain
  suggestions and maximum-severity overall suggestions. Store suggested and final judgments
  separately and require an override reason when they differ.
- Use the existing authorization, provenance ledger, audit events, and deterministic export engine.
  AI proposals are deferred and may later enter only through the same validation boundary.

## Initial scope

The bundled demonstration randomized-study definition proves ordering, missingness choices,
suggestion rules, independent review, and adjudication. It is explicitly not a complete
implementation of RoB 2 or any other published instrument. Additional instruments require a
separately validated declarative definition and version.

## Consequences

- Study design becomes canonical Study metadata and is required before assessment creation.
- Instrument history, original assessments, disagreements, evidence links, and adjudication remain
  independently auditable.
- RoB remains separate from PRISMA counting.
- JSON/XLSX exports advance to `review-export-3`; CSV and RIS article semantics remain unchanged.
- Live PostgreSQL constraint validation remains required when the environment blocker is removed.
