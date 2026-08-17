# Provenance

Provenance is a first-class scientific graph. An evidence-bearing assertion will link to a source document/article and the most precise available location (page, section, paragraph, table, figure, coordinates, and source text). It also records the responsible human or AI actor, model/provider, prompt and model versions, algorithm/task version, timestamp, confidence, verification state, and downstream uses.

Audit history answers who changed an application record and when. Scientific provenance answers why a scientific claim exists and what evidence supports it. They are related but not interchangeable.

Corrections create append-only change events carrying previous value, new value, reason, and actor. Normal application operations must not erase history.

## Persisted ledger foundation

Migration `20260810_0005` implements four separate append-only record families:

- `prompt_versions` stores immutable, monotonically numbered prompt templates and output schemas per organization.
- `ai_runs` captures the exact prompt version, provider/model/version labels, parameters, input and output snapshots, status, usage, review, and responsible human initiator. It records runs from mock/fixture providers today; it does not invoke a paid provider.
- `scientific_provenance` links a subject to an optional source and precise structured locator, method/version, human or AI actor, confidence, and verification state.
- `audit_events` records application changes with actor, before/after snapshots, reason, and optional review scope.

ORM mutation guards reject updates and deletes for all four families. Application services expose append and tenant-scoped read operations only. Corrections therefore append a new record or audit event; they never rewrite the historical row.

Actor constraints are explicit. Human provenance points to an active same-organization membership. AI provenance points to an AI run in the same organization and review. System provenance is reserved for internal services. Generic subject/source identifiers make the ledger usable across later scientific domains without collapsing those domains into the provenance schema.

## Extraction provenance

Study-family links record their method, actor, reason, confidence, and source evidence. Manual extraction values use the same scientific provenance ledger as documents and screening: each value records its Article or Document source, field locator, selected evidence text, manual method version, and extractor actor. Verification does not replace either run. It records canonical agreement or an explicit conflict, and adjudication appends a human-verified provenance record linked to the conflict while retaining both original evidence snapshots.

## Outcome and effect-estimate provenance

Outcome versions retain a canonical content hash and optional protocol-version source. Every outcome
mapping points to its original extraction value and records the mapping method, actor, rationale,
reported timing/unit, normalization rule versions, and any explicit direction transformation.
Effect estimates point through normalized tenant-scoped links to their source mappings and optionally
to an existing Document evidence location in the same Study Family. Derived estimates record
`effect-foundation-1`, structured input components, Decimal output, variance scale, and zero-event
state. Candidate selections and `analysis-readiness-1` snapshots are append-only downstream uses;
they never replace or mutate the source extraction, mapping, or estimate.
## Statistical synthesis trace

`ANALYSIS_SPECIFICATION_VERSIONED`, `ANALYSIS_SET_CREATED`, `META_ANALYSIS_STARTED`,
`META_ANALYSIS_COMPLETED`, `META_ANALYSIS_FAILED`, `SENSITIVITY_ANALYSIS_COMPLETED`, and
`ANALYSIS_ARTIFACT_GENERATED` use the existing append-only scientific provenance and audit ledgers.
The trace is: result/run -> specification version -> AnalysisSet -> selected effect estimate ->
outcome mapping -> verified extraction -> evidence location -> Document -> Article -> Study.
Canonical input/result hashes, provider/algorithm versions, renderer version, actor, timestamps, and
artifact checksum make numerical and figure outputs independently reconstructable. Deterministic
reads and staleness checks do not append noisy audit events.

## Phase 22 reporting and reproducibility foundation

Phase 22 adds a deterministic reporting layer over canonical Review state. Versioned `ReportSpecification`
records request explicit report types/sections/formats; immutable `ReportSnapshot` records source references,
source hashes, renderer version, and scientific-content hash; `ReportArtifact` stores exact JSON, HTML, XLSX,
and reproducibility-ZIP bytes with independent file checksums. Reporting readiness is report-type-specific and
supports explicitly labelled drafts. Report generation never recalculates PRISMA, Risk of Bias, certainty, or
meta-analysis results.

The reproducibility package validator checks deterministic relative paths, manifest schema, per-file SHA-256
checksums, package hash, and source identity without database mutation. Structured scientific records are
included; full-text binaries, raw provider bytes, secrets, environment files, storage keys, and runtime files
are excluded by default. Scientific staleness hashes cover canonical upstream scientific tables only; generated
provenance, exports, UI metadata, and report artifacts do not make an otherwise unchanged report stale.

A dedicated reporting workspace supports readiness, report type, package preview, generation, current/stale
status, checksum metadata, and authenticated downloads. Phase 22 is not a mature manuscript authoring system;
AI writing, living-review automation, PDF/DOCX, restricted document redistribution, and provider execution remain
deferred.

## Phase 23 AI provider foundation

Phase 23 adds a provider-neutral, task-oriented AI execution substrate with immutable model and prompt versions, bounded run/attempt lifecycles, input/prompt/response hashes, structured validation, append-only proposals and human decisions, usage/cost metadata, policy ceilings, tenant scoping, and accepted-AI provenance in reporting packages. The only executable workflow is an offline deterministic search-query draft proposal; it never mutates SearchStrategyVersion or another canonical scientific domain. Real providers, credentials, production scientific AI tasks, autonomous tools, and auto-accept remain deferred. AI provenance supports reconstruction of what was requested, returned, validated, and accepted but does not claim bit-for-bit model reproducibility.

## Phase 24 governed AI screening assistance

Screening proposal creation appends a provenance/audit event that identifies the assignment, Article,
AI run, approved protocol version, assistance mode, and content-hash snapshots. The AI execution ledger
retains the prompt/model/task/input/output/validation chain; the screening link adds scientific context
without collapsing AI output into a canonical decision.

Reveal access is separately append-only: assisted pre-decision views and post-decision reveals record
the reviewer, assignment, proposal, and decision where applicable. Canonical screening decisions remain
in the screening domain; a decision link records interaction and disagreement only. Human-curated
evaluation datasets receive human provenance, deterministic evaluations receive system provenance with
metric and dataset hashes, and case error classifications receive human audit events. No Phase 24
operation auto-accepts, auto-excludes, or overwrites a scientific record.

## Phase 25 full-text AI provenance

The trace is ScreeningDecision -> human actor -> optional full-text proposal link -> AI proposal ->
run/attempt/validation -> model/prompt/task -> approved protocol/criteria -> Article/citation ->
Document/version/checksum -> processing run/parser -> parsed/chunk hashes -> selected chunks/evidence.
Append-only access and interaction records distinguish unseen, assisted-viewed, post-decision revealed,
accepted, overridden, disagreed, and abstained behavior without mutating AI or human records.

Staleness never rewrites old records. Scientific publication exports do not use unaccepted proposals;
accepted human-decision provenance may enter audit/reproducibility packages, while evaluation remains
separate from effect estimates.
