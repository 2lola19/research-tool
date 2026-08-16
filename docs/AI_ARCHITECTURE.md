# AI Architecture

Domain code calls task-oriented services such as screening, extraction, and adjudication. Those services depend on the `AIProvider` protocol and a versioned prompt registry. Vendor SDKs are infrastructure adapters only.

The default `MockAIProvider` returns deterministic structured output and requires no network or credentials. Real providers will be selected by configuration and every scientific AI run will record provider, model/version, prompt/version, parameters, schema, timestamps, status, and usage.

Prompts live in a versioned registry, not arbitrary route handlers. Schemas permit `NOT_REPORTED`, `UNCLEAR`, `NOT_APPLICABLE`, and `NEEDS_REVIEW`. Deterministic calculations are prohibited from using AI.



## Phase 23 execution law

AI is a bounded capability, never the workflow or scientific source of truth. A typed task definition selects an immutable prompt version and model configuration. The execution service snapshots minimal scientific input, frames source text as untrusted data, hashes prompt and input, enforces model allowlists and bounded retry/timeout/token policies, and invokes a provider protocol with no tools. Provider responses are preserved as attempts with usage and optional cost metadata. Deterministic syntactic, schema, domain, size, and evidence validation must pass before an immutable proposal is created.

Proposal generation is not scientific acceptance. Human decisions are append-only and idempotent. Future consequential acceptance adapters must invoke the existing domain service and attach the proposal, run, prompt, model, reviewer, and evidence chain. The Phase 23 demonstration accepts only a search-query draft and proves that no SearchStrategyVersion changes.

The deterministic MockAIProvider supports known outputs, malformed outputs, timeouts, rate limits, permanent failures, retry exhaustion, usage fixtures, and abstention. Real-provider adapters are intentionally absent. AI reproducibility means preserving requested and returned model metadata, configuration, prompt, input, output, attempts, validation, and human review; it is not mathematical or bit-for-bit reproducibility.

## Phase 24 governed screening assistance

Phase 24 adds one governed scientific AI task: title/abstract screening suggestions. A versioned
review policy selects `OFF`, `BLINDED_AI`, or `ASSISTED` behavior and a bounded batch size. Every
proposal snapshots the approved protocol version and content hash, criterion hashes, citation hash,
task-definition version, assignment, run, prompt, and model. The proposal is always separate from the
canonical immutable screening decision.

`BLINDED_AI` withholds the suggestion until the assigned reviewer records a human decision;
`ASSISTED` permits a pre-decision view and records the access event. Post-decision reveals are
assignment-scoped and append-only. Human disagreement categories, interaction state, audit events,
and provenance preserve how the proposal was handled without allowing AI output to write workflow or
scientific state.

Evaluation datasets are curated reference records separate from Study, Article, and screening
decision entities. Deterministic local metrics report coverage, confusion counts, sensitivity and
specificity, Wilson intervals, calibration bins, threshold simulations, abstention/maybe rates, and
high-risk false exclusions. Evaluation results and case-level error classifications are immutable.
The Phase 24 implementation uses only the deterministic mock provider; full-text screening, paid or
live providers, autonomous exclusion, automatic acceptance, and model training remain deferred.
