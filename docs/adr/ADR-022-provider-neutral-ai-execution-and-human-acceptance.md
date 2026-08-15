# ADR-022: Provider-neutral AI execution and human acceptance boundary

## Status

Accepted for Phase 23.

## Decision

All AI-assisted work uses a task-oriented `AIExecutionService` and an `AIProvider` protocol.
Provider SDKs and credentials remain adapter concerns. Phase 23 ships only a deterministic,
offline mock provider.

Model configurations and prompt templates are immutable, versioned records. Each logical AI run
pins the task definition/version, output-schema version, prompt version, model configuration,
execution policy, parameters, input snapshot/hash, rendered-prompt hash, attempts, usage, response
hash, validation, and final state. Retry is bounded and limited to transient provider failures.

A valid provider response creates an immutable proposal in `PENDING_REVIEW`; it is not scientific
acceptance. A human acceptance/rejection is a separate append-only decision. Consequential future
acceptance adapters must call the existing scientific domain service and retain the proposal/run
chain. The Phase 23 search-query demonstration accepts only a draft and never replaces a canonical
`SearchStrategyVersion`.

Source content is framed as untrusted data and cannot redefine instructions, request secrets, or
obtain tools. Providers receive bounded structured input and no shell, filesystem, browser, or
network tools. Prompt snapshots retain minimal necessary content and references rather than
duplicating full documents.

AI reproducibility means preserving provider, requested and returned model metadata, model
configuration, prompt, inputs, output, validation, attempts, and human decision. It does not claim
bit-for-bit regeneration. Publication-oriented packages include accepted AI provenance only;
rejected proposals remain in the audit domain.

## Consequences

- AI cannot directly mutate canonical scientific tables.
- Historical runs cannot silently adopt current prompt/model versions.
- Unknown pricing remains unknown; model confidence remains explicitly uncalibrated metadata.
- Real providers, embeddings, autonomous agents, and production scientific-task workflows remain
  deferred.
