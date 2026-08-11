# Future API Requirements

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

All endpoints resolve organization context from active membership and enforce Review access server-side. AI extraction providers and live external scholarly APIs remain deferred. Export generation and search-execution recording are deterministic local application code and require no external API or credential.
