# Future API Requirements

## Outcome harmonization and synthesis preparation

Authenticated Review-scoped endpoints under `/api/v1/outcomes` create/list logical outcomes and
immutable versions, timepoint windows, units, and measurement scales; append explicit extraction
mappings; append reported or deterministically derived effect estimates; construct immutable
synthesis candidate sets; and append readiness evaluations. Mapping requests require a Study,
extraction value, outcome version, method, and rationale, while preserving optional structured
timing/unit/scale transformations. Derived estimates accept only supported structured components;
RR/OR/RD/MD calculations never accept an arbitrary continuity correction. Reads return deterministic
ordering. Mutations require centralized outcome/harmonization/synthesis permissions and use the
existing provenance/audit ledgers. No endpoint performs pooled analysis.


## Certainty-of-evidence foundation

Authenticated Review-scoped /api/v1/certainty endpoints create logical frameworks and immutable
content-hashed versions, optional outcome-pinned decision-threshold versions, independent
outcome/evidence-body assessments, explicit domain and final judgments, immutable submission and
correction chains, deterministic comparison/reveal, human adjudication, Evidence Profiles, and
Summary-of-Findings row snapshots. Quantitative assessments must pin a completed current Phase 20
run and its exact specification; narrative assessments name Review-scoped Studies. Workspace reads
preserve blindness until an explicit comparison record. No endpoint recalculates meta-analysis,
duplicates RoB, invents thresholds, infers publication bias, or generates a certainty decision by AI.

## Deterministic statistical synthesis

Authenticated Review-scoped `/api/v1/analysis` endpoints create logical specifications and immutable
versions, materialize explicitly selected AnalysisSets from Phase 19 candidates, execute immutable
runs, list workspace history/staleness, generate SVG forest artifacts, and authorize artifact
downloads. Execution accepts only a persisted AnalysisSet; it rechecks live scientific readiness and
never accepts transient estimates or method flags. Responses contain structured result,
heterogeneity, weights, leave-one-out sensitivity, diagnostics, provider/algorithm versions, and
input/result hashes. The download proxy keeps bearer credentials server-side.

| Service | Purpose | Required stage | Providers | Credentials | Free/open alternative | Current mock | Status |
|---|---|---|---|---|---|---|---|
| AI inference | Screening, extraction, adjudication assistance | Screening onward | OpenAI, Anthropic, Gemini | Provider API key | Local models where validated | `MockAIProvider` | Mock interface only; real providers deferred |
| Scholarly metadata | Discovery and enrichment | Search/import | OpenAlex, PubMed, Europe PMC, Crossref | Usually none; polite email/key may apply | Deterministic fixture translator/provider | Provider adapters and fixture implemented | Live execution explicit opt-in/deployment gate |
| Document parsing | Scholarly PDF to structured TEI | Document management | GROBID | None for self-hosted | Fixture parser + TEI adapter | `DocumentParser` + `GrobidTeiParser` | Adapter foundation implemented; live service deferred |
| Object storage | Durable document storage | Document management | S3-compatible providers | Access key/secret/role | Local filesystem | `LocalFileStorageProvider` | Local-first foundation implemented; S3 adapter deferred |
| Notifications | Human checkpoints and job failures | Workflow | Email providers | Provider credentials | Console/mock notifications | Mock planned | Deferred to Phase 4 |
| Durable orchestration | Retries, timers, checkpoints | Workflow | Temporal self-hosted/cloud | None locally; cloud credentials later | Local PostgreSQL-backed adapter | Contract created | Evaluate in Phase 4 |
| Statistical service | Deterministic meta-analysis | Analysis | Isolated R service with metafor | None | Versioned native deterministic engine | `StatisticalSynthesisEngine` | Native fixed/DL foundation implemented; metafor service deferred |
| Production identity | User authentication and enterprise federation | Production hardening | Standards-based OIDC provider | OIDC client credentials/metadata | Local scrypt + signed-token provider | `AuthenticationProvider` + local implementation | Provider selection deferred; local provider complete |

## Implemented scientific endpoints

- `/search-executions/sources` records structured Review-scoped identification sources;
  `/search-executions` creates immutable executions and appends explicit status events.
- `/search-executions/{id}/imports` links lossless citation-import source records without collapsing
  multiple discovery paths. Raw artifacts are stored and downloaded through checksum-verifying,
  tenant-scoped endpoints.
- Review search-documentation reads return deterministic execution order, exact query, filters,
  source/provider identity, strategy/translation linkage, status history, result count, and import
  count. No live scholarly provider or credential is required.

- `/studies` creates and lists Review-scoped Studies; article links carry roles, methods, source evidence, and soft unlink state.
- `/extraction/schemas` and `/extraction/schema-versions` create immutable typed schema definitions.
- `/extraction/runs` creates and resumes Study-level manual extraction runs; `/values` validates typed values, explicit missingness, and source evidence before saving.
- `/extraction/verifications/compare` performs deterministic dual-run comparison; `/extraction/conflicts/{id}/resolve` performs authorized human adjudication without overwriting original values.
- `/prisma/reviews/{review_id}/summary` derives live record/report/study flow counts and explicit
  final-readiness blockers; `/snapshots` preserves immutable algorithm-versioned summaries.
- `/exports/reviews/{review_id}` creates and lists authorized CSV, XLSX, JSON, and RIS artifacts;
  export metadata exposes manifests and SHA-256 checksums, while tenant-scoped download verifies the
  stored checksum before returning immutable bytes.
- `/risk-of-bias/instruments` and `/instrument-versions` create review-scoped declarative methods;
  immutable decisions approve or reject a version before use. The demonstration endpoint installs a
  clearly labelled framework-validation RCT definition and does not claim complete RoB 2 support.
- `/risk-of-bias/assessments` creates Study- and version-pinned independent records. Answer, domain,
  and overall endpoints validate instrument choices and optional existing evidence locations;
  submission locks the record and correction requires an explicit superseding revision.
- `/risk-of-bias/comparisons` deterministically reveals and compares two submitted independent
  assessments. Authorized adjudication appends a final verified snapshot and rationale without
  overwriting either original assessment.

All endpoints resolve organization context from active membership and enforce Review access server-side. AI extraction/RoB proposals and live external scholarly APIs remain deferred. Export generation, search-execution recording, and RoB comparison are deterministic local application code and require no external API or credential.

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

The `/ai/screening` routes expose Review-scoped versioned policies, assignment-scoped title/abstract
suggestion generation and reveal, curated evaluation datasets, deterministic evaluation results,
case-result reads, and append-only error classifications. `BLINDED_AI` keeps model output hidden until
the assigned reviewer has recorded the canonical screening decision; `ASSISTED` records a pre-decision
access event. Every suggestion requires an approved protocol and preserves assignment, citation,
criterion, prompt, model, task, run, and content-hash references.

Evaluation datasets use explicit reference standards and decisions. Evaluation is deterministic and
never changes screening decisions; it reports coverage, false-negative-sensitive metrics, calibration,
threshold simulations, and high-risk disagreements. All routes resolve active organization membership
and Review access server-side, return not-found semantics for foreign direct identifiers, and preserve
human decisions as the canonical workflow state. Only the offline deterministic mock provider is
enabled; full-text screening and production providers remain deferred.

## Phase 25 governed AI full-text screening

`/api/v1/ai/screening/full-text` exposes assignment/document readiness, bounded batch generation,
assignment and direct-proposal reads with server-side blinding, human acceptance through the canonical
screening service, document-version evaluation datasets, deterministic results, case results, and
error classifications. Requests name an explicit Review, assignment, processed Document and role.
Batch entries fail independently and never complete a stage.

Responses distinguish unavailable page/section metadata, expose stale reasons, structured missing
information, selected chunk IDs, and selection method. Direct IDs are scoped by Organization, Review,
assignment, and reviewer. Evaluation refuses unrevealed BLINDED_AI proposals and labels metrics
`FULL_TEXT`. No route auto-excludes, changes PRISMA, merges reports, or treats an AI proposal as a
canonical decision.
## Phase 26 AI extraction API

All routes are organization- and review-scoped under `/api/v1/ai/extraction/reviews/{review_id}` and
reuse centralized AI permissions. The API supports versioned policies, readiness, bounded independent
batch generation, proposal list/assignment/direct-ID inspection, field review, reference-dataset
creation, evaluation, and high-risk result queues. No route accepts an arbitrary prompt or provider
call. Direct-ID responses enforce the same BLINDED_AI withholding as assignment responses; generic AI
endpoints exclude structured extraction content. Accept/edit requests invoke the normal manual
extraction service and attribute the canonical value to the authenticated human.

## Phase 27 AI Risk-of-Bias API

Authenticated Review-scoped routes under `/api/v1/ai/risk-of-bias/reviews/{review_id}` provide
versioned policy creation, assessment/source readiness, bounded proposal generation, assignment and
proposal reads, question-level human dispositions, evaluation dataset creation/evaluation, case
results, high-risk queues, and append-only error classifications. Requests require the assessor-owned
RoB assessment, an approved immutable instrument version, and one through eight explicit processed
Study Family Documents. Source manifests retain Article, Document/version, processing/parser, parsed
content, and block metadata; proposals retain selected/omitted chunk hashes and task/model/prompt
provenance through the existing AI run.

`BLINDED_AI` responses omit structured answers, validation, domain, and overall suggestions before
canonical submission; `ASSISTED` responses are visible only to the assigned assessor and record
access/disposition. Generic `/ai/runs`, run lists, and direct proposal reads reject or omit
`ROB_SUGGESTION`. Human dispositions invoke the existing Risk-of-Bias answer service and never
create a domain/overall judgment or submit an assessment. Evaluation routes cannot evaluate an
unrevealed blinded proposal and expose only deterministic descriptive metrics.

## Phase 28 AI outcome harmonization API

The `/api/v1/ai/outcomes/reviews/{review_id}` routes provide policy creation, readiness checks,
bounded proposal generation, proposal reads, human dispositions, evaluation dataset/result
management, and append-only error classification. Requests explicitly identify a verified
extraction value, immutable outcome version, and one through eight processed Documents linked to
the Study's Article. Responses preserve source manifests, selected/omitted chunks, validation
errors, staleness, and task/model/prompt provenance through the existing AI run.

The generic AI routes reject `OUTCOME_MAPPING_SUGGESTION`. Proposals cannot write mappings or
effect estimates. `ACCEPTED` and `EDITED` require a human canonical action and payload; the
service invokes `OutcomeService`, which performs the final compatibility, evidence, tenant, and
immutability checks. The API never performs unit conversion, effect calculation, imputation,
pooling, or analysis-state mutation. Direct proposal/evaluation/error identifiers are scoped by
the path Review and active organization membership.

## Phase 29 AI certainty-of-evidence API

The `/api/v1/ai/certainty/reviews/{review_id}` routes provide versioned policy creation, readiness
checks, bounded proposal generation, proposal reads, human dispositions, evaluation dataset/result
management, and append-only error classification. A request names an assessor-owned in-progress
certainty assessment and one through eight explicit processed Documents; the service verifies the
assessment's included Study identities and the Article-to-Study relationship before invoking the
AI task.

The generic AI routes reject `CERTAINTY_SUGGESTION`. Responses retain assessment/outcome/framework
identity, source and selected-chunk manifests, validation errors, staleness, and AI run/task/model/
prompt provenance. The task may draft evidence and framework-permitted domain suggestions only.
`ACCEPTED` and `EDITED` require an explicit human payload and `SAVE_DOMAIN_JUDGMENTS`; the route
invokes `CertaintyService`, which rechecks framework choices, evidence, tenant scope, and
immutability. No AI route writes candidate/final certainty, thresholds, publication-bias
decisions, upgrades/downgrades, comparisons, adjudications, or Summary-of-Findings records.

## Phase 30 read-only Review copilot API

Authenticated Review-scoped routes under `/api/v1/ai/copilot` expose the explicit read-only task
registry, versioned policy limits, policy reads, query creation, immutable query history, and
direct query reads. Query creation requires `REVIEW_AI_PROPOSALS`, active organization membership,
Review access, a configured policy, a bounded task key/query, and the deterministic context
assembler. Policy creation requires `MANAGE_AI`.

The context is limited to Review metadata, deterministic PRISMA summary/readiness, workflow
run/job state metadata, derived blockers, and source-reference counts. Job payloads are never
returned to the provider or UI. Responses retain context hashes, available source citations,
selected citation claims, AI run/proposal identity, validation status, and abstention. The generic
`/ai/runs` endpoint rejects `REVIEW_COPILOT`; no copilot route changes scientific or workflow state,
performs arbitrary search/retrieval, or generates manuscript content.

## Phase 31 durable workflow execution API

The existing `/api/v1/workflow` submission route accepts `payload_schema`, `payload_version`, and
bounded `max_attempts` metadata. Authenticated controller routes under
`/api/v1/workflow/execution` register and heartbeat workers, inspect worker health, claim a job for
one Review, heartbeat/complete/fail an attempt with its lease token, list Review attempts, and
explicitly requeue a failed job. Claim, attempt, and requeue operations require active organization
membership, Review access, and the existing workflow-control boundary; foreign Review/job/attempt
identifiers fail closed.

Claim responses include only the handler's allowlisted redacted payload and a short-lived lease
capability. Attempt history never returns the lease token. Worker CLI execution uses the same
provider-neutral service and does not bypass API authorization for human workflow control.

## Phase 32 recovery API

Workflow job submission may include an immutable definition hash, step key/order, and structured
retry policy with bounded attempts, backoff, retryable failure classes, and timeout. Responses expose
operational retry/dead-letter metadata without returning raw lease capabilities.

Authenticated Review-controller routes under `/api/v1/workflow/execution` provide idempotent pause
resume, bounded manual requeue/dead-letter recovery, normalized step-checkpoint reads, and
read-only reconciliation diagnostics. Recovery requests carry an idempotency key and explicit reason;
exhausted jobs require an explicit additional attempt budget. Foreign organization/Review/job
identifiers fail closed. No recovery route accepts or writes scientific data, evidence, Article,
Study, analysis, or human checkpoint decisions.

## Phase 33 scholarly provider execution API

Authenticated search-controller routes expose configured provider capability metadata at
`/api/v1/search-executions/providers`, append-only request history at
`/api/v1/search-executions/{execution_id}/provider-attempts`, and an explicit execution command at
`/api/v1/search-executions/{execution_id}/provider-runs`. A provider run requires the Review,
provider key, exact query already retained by the planned `SearchExecution`, and bounded optional
page/page-size values. Live provider execution is disabled unless the deployment explicitly
enables it.

OpenAlex, PubMed E-utilities, Europe PMC, and the deterministic fixture implement the same
provider protocol. Responses normalize into `ParsedCitation` records through the existing
citation-import service; the route never accepts provider-specific canonical search semantics or
destructive Article merges. Results retain provider totals, `COMPLETED` versus `PARTIAL` status,
raw response artifact identity, import linkage, provider/version provenance, and safe attempt
history. Provider credentials, when needed, are read only from environment-backed secret
settings and are never returned.

## Phase 34 production AI provider and governance API

The existing `/api/v1/ai/registry` response exposes safe provider capability, routing-policy, model,
prompt, and task metadata without secrets. `GET /api/v1/ai/reviews/{review_id}/usage` returns the
Review-scoped normalized attempt/run totals, known estimated cost, unknown-cost count, and the
configured token/cost/circuit policy. The route repeats active Review authorization and never
returns prompt secrets, provider credentials, raw error bodies, or lease capabilities.

AI runs may use OpenAI, Anthropic, or Gemini only when deployment configuration explicitly enables
the provider and supplies an environment-backed secret. Model identifiers must be allowlisted and
the selected task/provider/model are pinned in the run. A provider, budget, circuit, timeout, or
pricing policy failure is reported explicitly; no endpoint silently falls back to another model.

## Phase 35 document processing and storage API

Document upload continues to return only tenant-scoped `Document` metadata; the server generates
the opaque object key and verifies PDF signature, media type, size, and checksum before the row is
committed. `GET /api/v1/documents/{document_id}/content` authorizes the document first, then
returns checksum-verified bytes; restricted classes require screening permission and missing or
corrupt objects fail closed without exposing storage paths.

`GET /api/v1/documents/{document_id}/processing-runs` returns tenant/review-scoped append-only
parser history, including safe failure class/message, parser version, verified content metadata,
manifest hash, bounded manifest entries, and block/text counts. `POST /api/v1/documents/{document_id}/process`
may create a bounded retry run for a failed document; it cannot silently reprocess a successful
document or exceed the configured attempt limit.

`GET /api/v1/documents/reviews/{review_id}/storage-reconciliation` is a manager-only, read-only
diagnostic. It returns counts, missing document IDs, orphan count, and a status marker, never raw
storage keys, bytes, credentials, or deletion controls. External retrieval records accept only
validated HTTPS URLs and do not trigger automatic fetching in this phase.

## Phase 36 collaboration, assignment, quality-control and operational UX API

`GET /api/v1/screening/reviews/{review_id}/rounds` returns the tenant- and Review-scoped ordered
screening-round index for an authorized Review member. It does not return assignments, peer
decisions, unrevealed AI suggestions, or storage identifiers. Existing queue and outcome routes
remain the authority for reviewer-specific queue visibility and manager-only quality-control
visibility; foreign Review identifiers retain not-found semantics.

The server-rendered Review operations workspace reads Review metadata, round status, optional
membership visibility, PRISMA readiness, workflow attempts/checkpoints/reconciliation, and
scientific provenance through existing authenticated routes. Optional role-restricted sections are
represented as restricted or unavailable rather than guessed. Assignment and conflict-adjudication
forms call the existing screening service through authenticated server actions; the browser cannot
grant itself a role, reveal blinded data, finalize a scientific decision, or recover a workflow job.

The workspace provides explicit loading, error, stale-reconciliation, mutation-error, and live-read
timestamps, plus safe links to existing AI, reporting, and authenticated download surfaces. It does
not calculate scientific values or export raw workflow payloads.

## Phase 37 operational endpoints and transport requirements

`GET /health/live` is process liveness. `GET /health/ready` is dependency readiness and, when
configured, migration-head readiness; it returns `503` without exposing connection strings or
schema details. `GET /health/metrics` is a low-cardinality operational scrape response and must be
network-restricted by deployment policy. Metrics route labels redact UUID and numeric identifiers.

Every response receives the generated or validated `X-Request-ID` and a bounded `X-Trace-ID`.
Structured completion logs contain only method, route template, status, and duration. The token
issuance endpoint returns `429` with `Retry-After` and rate-limit headers after its configured
process-local bound; a production edge/shared-store limiter remains required for multiple replicas.
