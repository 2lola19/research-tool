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
## AI-assisted extraction provenance

For an assisted canonical field, provenance retains the human actor and canonical extraction value,
the ACCEPTED or EDITED field-review event, immutable AI field/proposal, AI run and attempts, model,
prompt and task versions, exact schema/field hashes, Study and source Article/Document identities,
processing/parser and parsed-content hashes, chunk manifests, and exact bounded evidence quote/hash.
UNSEEN, VIEWED/REVEALED, ACCEPTED, EDITED, REJECTED, UNRESOLVED, and model abstention remain
distinguishable. Human edits never mutate the original proposal. Unaccepted proposals remain audit and
evaluation records only and are excluded from normal scientific exports.

## AI-assisted Risk-of-Bias provenance

For every governed RoB proposal, the provenance chain retains the human-owned assessment and Study,
immutable instrument version/content hash, exact question/choice definitions, Article/Document/version,
successful processing run, parser/version, parsed block hash, selected/omitted chunk manifest, input
hash, task/prompt/model versions, attempt history, response/validation hashes, and evidence quote/hash.
The `AIRobProposalLink` is never a canonical assessment record.

`BLINDED_AI` access is withheld until the assessor submits; `ASSISTED` access and every question-level
human disposition are append-only. ACCEPTED/EDITED dispositions point through the existing RoB answer
service and record the human actor, rationale, canonical answer, proposal, AI run, and instrument
identities. REJECTED/UNRESOLVED and abstention remain distinct. Domain and overall suggestions are
derived by the existing declarative instrument rules only. Evaluation datasets/results and
high-risk/error classifications carry separate human/system provenance and never enter scientific
exports as canonical RoB state.

## AI-assisted outcome harmonization provenance

Each outcome proposal retains the human-owned Study and verified extraction snapshot, immutable
OutcomeDefinitionVersion/content hash, allowed mapping references, Article/Document identities,
successful parser/version and parsed-content hashes, selected/omitted chunk manifest, input hash,
task/prompt/model versions, attempt history, response/validation hashes, and exact evidence quote.
The proposal is never a canonical mapping or effect estimate.

`ACCEPTED`, `EDITED`, `REJECTED`, and `UNRESOLVED` dispositions remain append-only. Accepted or
edited canonical records are created only by the existing `OutcomeService` from an explicit human
payload and receive human provenance with `AI_PROPOSAL` source identity. The canonical record
retains its normal extraction/mapping/effect trace; the AI proposal, evaluation, and error records
remain separate and are not used as analysis inputs merely because they were validated.

## AI-assisted certainty-of-evidence provenance

Each certainty proposal retains the assessor-owned assessment, included Study identities, outcome
and immutable framework version/content hashes, evidence-profile and assessment snapshots,
Article/Document/version identities, successful processing/parser and parsed-block hashes,
selected/omitted chunk manifests, input hash, task/prompt/model versions, attempt history,
response/validation hashes, and exact bounded evidence quotes. The proposal link is never a
canonical certainty record.

`ACCEPTED`, `EDITED`, `REJECTED`, and `UNRESOLVED` dispositions remain append-only. Accepted or
edited domain judgments are created only by the existing `CertaintyService` from an explicit human
payload and receive human `AI_PROPOSAL` provenance plus the normal audit event. AI abstention,
staleness, validation errors, evaluation results, and high-risk/error classifications remain
distinct and cannot enter scientific exports as canonical certainty state.

## AI-assisted Review copilot provenance

Each copilot query preserves the requesting Review/member scope, explicit task key, bounded query,
deterministic context snapshot and hash, available citation locators, AI run/proposal identifiers,
prompt/model/task history through the existing AI substrate, response/validation snapshot, and
abstention or failure status. An append-only audit event records query creation and the cited
context hash.

Copilot answers are navigation assistance, not scientific evidence or canonical workflow state.
Workflow payloads are excluded; source citations point to allowlisted Review/PRISMA/workflow record
locators. No copilot response is exported as a scientific result, and no copilot route creates a
canonical write or substitutes for domain-service provenance.

## Workflow execution provenance boundary

Phase 31 separates operational execution history from scientific provenance. Job attempts preserve
the task payload schema, worker/lease lifecycle, attempt result or failure, and ordered operational
events needed to reconstruct execution. These records do not assert why a scientific claim is true.

When a future scientific handler performs a consequential write, it must call the existing domain
service and append its normal human/system/AI provenance and audit records in that service's
transaction. Worker claim, heartbeat, completion, failure, requeue, and expiry events never serve
as substitutes for evidence source identity, method version, actor, verification, or human approval.

## Workflow recovery provenance boundary

Definition hashes, retry classes, attempt deadlines, step checkpoints, reconciliation findings, and
manual recovery reasons explain operational execution. They are not evidence, scientific values, or
human decisions. A manual recovery operation records its authorized actor and reason but cannot
stand in for a scientific provenance event.

If a workflow step invokes a consequential domain service, that service remains responsible for the
atomic scientific write, source/method/actor provenance, append-only audit event, idempotency key,
and explicit human acceptance where required. Automatic retry is never permission to repeat an
unreviewed scientific write; handlers must be designed to detect or reject duplicate side effects.

## Scholarly provider acquisition provenance

Phase 33 keeps canonical search intent, SearchExecution history, raw acquisition, normalized
CitationSourceRecords, and provider-attempt operations distinct. A provider run records the exact
query and filters already held by SearchExecution, provider/version, bounded page and attempt
history, safe request fingerprints, HTTP/failure classification, response sizes/hashes, and the
checksum-verified raw response artifact. The provider execution method/version and initiating actor
are appended to the provenance ledger; normalized citation records use the existing citation
import provenance path and retain provider metadata in their raw source snapshot.

Request fingerprints intentionally omit credential parameters. Attempt rows are tenant/Review
scoped and append-only, and a partial result is represented as `PARTIAL` with the provider total
and imported discovery links intact. Provider retries never overwrite an earlier attempt, change
the canonical query, merge Articles, or bypass Study, screening, human-review, or analysis
boundaries.

## Production AI provider provenance

Each Phase 34 AI run retains the selected provider key, immutable model version, task/prompt
versions, routing-policy version, bounded timeout/retry/token policy, budget/circuit policy, input
and rendered-prompt hashes, and the normal AI provenance/audit chain. Each provider attempt retains
the normalized usage snapshot, request identifier when supplied, response hash, exact structured
response snapshot, duration, estimated cost when pricing and usage are both known, or an explicit
unknown-cost state. Failure attempts retain only safe classification/message metadata.

Provider credentials, authorization headers, arbitrary endpoint URLs, raw error bodies, and secret
configuration are excluded from provenance. Usage and circuit reads repeat organization/Review
scope; they describe operational execution and spend governance, not scientific evidence. No model
response bypasses validation, human acceptance, or the existing canonical scientific service.

## Phase 35 document processing provenance

The source-document chain begins with the tenant/review/article identity, opaque object key,
original filename/media type, byte size, and SHA-256. Upload and verified retrieval retain the
same checksum boundary; a corrupted or missing object produces a classified failed processing
run and does not overwrite the original artifact or prior run history.

Each processing run records parser name/version, requester, start/finish times, verified content
hash/size, bounded canonical block count and text-byte total, and a deterministic versioned chunk
manifest/hash. Manifest entries identify block type/order/page/section and text hashes so later
evidence can be reconstructed and compared without treating the manifest as a canonical Article,
Study, or scientific decision. Consequential block persistence and screening continue to use the
existing provenance and append-only audit services.

Read-only storage reconciliation is operational diagnostics only. It reports tenant/review-scoped
missing and orphan counts without deleting objects or inventing provenance. Storage credentials,
malware-scan claims, external URL response bodies, and unbounded parser output are not persisted.
