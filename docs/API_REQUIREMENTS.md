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
| Scholarly metadata | Discovery and enrichment | Search/import | OpenAlex, PubMed, Europe PMC, Crossref | Usually none; polite email/key may apply | Deterministic fixture translator/provider | Offline translator implemented | Live execution deferred; no credentials required yet |
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