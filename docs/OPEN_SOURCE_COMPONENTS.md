# Open-Source Component Evaluation

Evaluation snapshot: 2026-08-11. Versions are pinned only when integration begins.

| Component | Repository | License | Purpose | Evaluated | Decision | Reason / integration approach | Version |
|---|---|---|---|---|---|---|---|
| GROBID | https://github.com/grobidOrg/grobid | Apache-2.0 | Scholarly PDF parsing | Evaluated | Adapter boundary accepted; live service deferred | PDF-to-TEI service remains isolated; `GrobidTeiParser` normalizes fixture TEI into the canonical document model; Docker execution is blocked | TBD |
| ASReview | https://github.com/asreview/asreview | Apache-2.0 | Active-learning screening | Preliminary | Deferred | Screening Foundation uses the local blinded decision/provenance model; evaluate ASReview only after this recovery checkpoint | TBD |
| dedupe | https://github.com/dedupeio/dedupe | MIT | Fuzzy entity resolution | Preliminary | Candidate | Layer after deterministic DOI/PMID/title rules; never destructively merge source records | TBD |
| Temporal | https://github.com/temporalio/temporal | MIT (server); SDK licenses vary | Durable orchestration | Preliminary | Deferred behind port | Strong fit, but extra service complexity is premature before workflow semantics are implemented | TBD |
| Temporal Python SDK | https://github.com/temporalio/sdk-python | MIT | Worker/client integration | Preliminary | Deferred behind port | Typed durable workflows; evaluate replay/versioning operational cost in Phase 4 | TBD |
| OpenAlex / PyAlex | https://github.com/pyalex-tooling/pyalex | MIT | Scholarly metadata | Pending | Candidate | Implement behind `SearchProvider`; respect API etiquette and preserve raw source provenance | TBD |
| metafor | https://github.com/wviechtb/metafor | GPL-2.0 | Validated meta-analysis | Pending legal/architecture review | Isolate | Prefer a separately deployed R statistical service; review distribution implications before incorporation | TBD |

No candidate code is copied into this repository. Direct integration requires a maintenance, license, security, and fit review at the relevant phase.

Phase 2 adds no authentication dependency or SaaS. Its local-only provider uses Python standard-library scrypt and HMAC behind an application protocol; a production OIDC implementation remains deferred.

The PRISMA/export foundation adds no external component. CSV, JSON, RIS, SHA-256, and deterministic
OOXML/XLSX generation use Python standard-library modules; no paid reporting provider or spreadsheet
SDK is introduced.

The Search Execution phase adds no external dependency. Its provider-neutral `SearchProvider`
protocol and fixture/manual/file-import acquisition methods preserve honest provenance without
calling PubMed, Europe PMC, OpenAlex, Crossref, or any paid API. Raw artifacts reuse the existing
local object-storage adapter.
