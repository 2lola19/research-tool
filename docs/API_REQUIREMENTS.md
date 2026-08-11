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

| Service | Purpose | Required stage | Providers | Credentials | Free/open alternative | Current mock | Status |
|---|---|---|---|---|---|---|---|
| AI inference | Screening, extraction, adjudication assistance | Screening onward | OpenAI, Anthropic, Gemini | Provider API key | Local models where validated | `MockAIProvider` | Mock interface only; real providers deferred |
| Scholarly metadata | Discovery and enrichment | Search/import | OpenAlex, PubMed, Europe PMC, Crossref | Usually none; polite email/key may apply | Deterministic fixture translator/provider | Offline translator implemented | Live execution deferred; no credentials required yet |
| Document parsing | Scholarly PDF to structured TEI | Document management | GROBID | None for self-hosted | Fixture parser + TEI adapter | `DocumentParser` + `GrobidTeiParser` | Adapter foundation implemented; live service deferred |
| Object storage | Durable document storage | Document management | S3-compatible providers | Access key/secret/role | Local filesystem | `LocalFileStorageProvider` | Local-first foundation implemented; S3 adapter deferred |
| Notifications | Human checkpoints and job failures | Workflow | Email providers | Provider credentials | Console/mock notifications | Mock planned | Deferred to Phase 4 |
| Durable orchestration | Retries, timers, checkpoints | Workflow | Temporal self-hosted/cloud | None locally; cloud credentials later | Local PostgreSQL-backed adapter | Contract created | Evaluate in Phase 4 |
| Statistical service | Deterministic meta-analysis | Analysis | R service with metafor | None | Local R container | Interface planned | Deferred to Phase 20 |
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
