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

## Phase 25 governed full-text assistance

Phase 25 adds the critical-risk `FULL_TEXT_SCREENING_SUGGESTION` task on the same provider-neutral
execution service. Each run pins an approved protocol, exclusion criteria, full-text assignment,
Article, immutable acquired Document artifact, successful processing run, parser/version, parsed and
selected-text hashes, ordered scoped chunk IDs, deterministic selection method, prompt, model, task,
and input snapshot. Input is bounded structured data; providers have no tools or retrieval authority.

Exact normalized-substring validation checks evidence quote, document/version/chunk, parser page and
section metadata, size, criterion identity, and Review scope. EXCLUDE without pinned criteria and
substantive evidence is invalid. MAYBE/ABSTAIN require structured missing information. BLINDED_AI
withholding applies to assignment reads, direct proposal IDs, and evaluation. Only the existing human
`ScreeningService` creates canonical decisions. Staleness never mutates or silently refreshes history.

Full-text evaluation remains labeled separately from title/abstract evaluation. Retention is positive;
AI EXCLUDE/reference RETAIN is the false-negative safety event. Metrics include criterion correctness,
evidence validation, section analysis, calibration, simulations, and high-risk disagreements. The
offline deterministic mock remains the only provider.
## Phase 26: governed structured extraction assistance

`STRUCTURED_EXTRACTION_SUGGESTION` reuses the Phase 23 run, attempt, model, prompt, provider, usage,
and immutable proposal substrate. An extraction-specific link pins the human assignment,
`ExtractionSchemaVersion`, Study, explicit report/document set, processing/parser identities, parsed
hashes, selected and omitted chunk manifests, and validation results. Field-aware source selection is
deterministic and versioned; document content is untrusted data and the provider receives no tools.

Every requested schema field has one proposal envelope. Non-missing fields require exact grounded
evidence, and deterministic validation separately checks the schema envelope, field uniqueness and
completeness, value types/options/units, missingness consistency, document/chunk/page/section/quote,
and value support. Source text and normalized value are preserved separately. No model calculation or
unit conversion is accepted.

OFF, BLINDED_AI, and ASSISTED are server policies. BLINDED_AI serializers withhold field output and
validation until human submission and record reveal access. Only ASSISTED valid/current fields can be
accepted or edited, always through `ManualExtractionService`. Generic run/proposal endpoints exclude
the task. Evaluations use deterministic field metrics, explicit reference standards, calibration bins,
hypothetical-only thresholds, and high-risk hallucination/evidence queues.

## Phase 27: governed Risk-of-Bias assistance

`ROB_SUGGESTION` is a critical-risk task on the existing provider-neutral execution substrate. The
input snapshot pins the Review, assessor-owned RoB assessment, Study, approved immutable instrument
version and content hash, normalized question definitions and allowed choices, explicit Study Family
Articles/Documents, processing/parser identity, selected/omitted chunks, and deterministic input
hashes. Source content is untrusted quoted data; providers receive no tools or retrieval authority.

The validator requires exactly one envelope per pinned signalling question. A proposed answer must
use an instrument-allowed choice and a quote whose document/version/chunk/source-block/page/section
identity matches the immutable input. `ABSTAIN` is valid and conservative. Only after validation do
the existing declarative instrument rules derive provisional domain/overall suggestions; the model
does not supply or calculate those judgments. The existing `RiskOfBiasService` remains the only
canonical answer/domain/overall/submission path.

Review policies support `OFF`, `BLINDED_AI`, and `ASSISTED`. Blinded serializers withhold structured
answers, validation, domain, and overall fields until the assessor submits; generic AI run/list/direct
proposal endpoints exclude the task. Assisted views and human dispositions are append-only and
assignment-scoped. Staleness compares instrument, assessment, source/parser, parsed-block, and
selected-text hashes. Evaluation is deterministic and descriptive only: signalling/domain/overall
agreement, grounding, abstention, coverage, confusion counts, calibration status, and dangerous
underestimation/high-risk queues. The bundled instrument remains a demonstration framework and is
not a claim of complete RoB 2 support.
