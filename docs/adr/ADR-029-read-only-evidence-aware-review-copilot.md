# ADR-029: Read-Only Evidence-Aware Review Copilot

## Status

Accepted for V1 implementation.

## Context

Review members need a safe way to understand deterministic project status, workflow blockers, and
where supporting records live. An unconstrained chat/search layer could cross tenant boundaries,
expose workflow payloads, invent citations, change state, or be mistaken for scientific analysis.

## Decision

Implement `REVIEW_COPILOT` as a governed read-only task over an allowlisted, deterministic context
snapshot:

- Permit only the explicit task keys `PROJECT_STATUS`, `WORKFLOW_BLOCKERS`, and
  `PROVENANCE_NAVIGATION`.
- Assemble bounded Review metadata, deterministic PRISMA summary/readiness, workflow run/job state
  metadata, derived blockers, and source-reference counts. Never expose workflow job payloads or
  grant retrieval, filesystem, browser, database, shell, or mutation tools.
- Require exact citation IDs from the supplied snapshot for every non-abstaining answer. Reject
  fabricated citations, unbounded answers, missing abstention reasons, unsupported actions, and
  invalid confidence values deterministically.
- Store versioned policy limits, immutable query snapshots, context hashes, available citations,
  AI run/proposal links, validation results, status, and append-only audit history with composite
  organization/Review foreign keys.
- Require existing AI permissions and Review access. The service performs no canonical scientific
  or workflow write; human users navigate to the existing domain surfaces to make changes.

## Consequences

The copilot can reduce navigation effort while keeping canonical records, tenant boundaries,
provenance context, and human authority explicit. Its answers are bounded advisory text, not
scientific evidence or workflow truth. The deterministic offline mock remains sufficient for V1;
live providers, embeddings, arbitrary search, and manuscript generation remain deferred.
