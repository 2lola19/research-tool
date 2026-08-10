# Future API Requirements

| Service | Purpose | Required stage | Providers | Credentials | Free/open alternative | Current mock | Status |
|---|---|---|---|---|---|---|---|
| AI inference | Screening, extraction, adjudication assistance | Screening onward | OpenAI, Anthropic, Gemini | Provider API key | Local models where validated | `MockAIProvider` | Interface created |
| Scholarly metadata | Discovery and enrichment | Search/import | OpenAlex, PubMed, Europe PMC, Crossref | Usually none; polite email/key may apply | Fixture provider | Fixture planned | Deferred to Phase 7 |
| Document parsing | Scholarly PDF to structured TEI | Document management | GROBID | None for self-hosted | Local GROBID container | Adapter planned | Deferred to Phase 11 |
| Object storage | Durable document storage | Document management | S3-compatible providers | Access key/secret/role | Local filesystem | Local adapter contract | Foundation created |
| Notifications | Human checkpoints and job failures | Workflow | Email providers | Provider credentials | Console/mock notifications | Mock planned | Deferred to Phase 4 |
| Durable orchestration | Retries, timers, checkpoints | Workflow | Temporal self-hosted/cloud | None locally; cloud credentials later | Local PostgreSQL-backed adapter | Contract created | Evaluate in Phase 4 |
| Statistical service | Deterministic meta-analysis | Analysis | R service with metafor | None | Local R container | Interface planned | Deferred to Phase 20 |
| Production identity | User authentication and enterprise federation | Production hardening | Standards-based OIDC provider | OIDC client credentials/metadata | Local scrypt + signed-token provider | `AuthenticationProvider` + local implementation | Provider selection deferred; local provider complete |
