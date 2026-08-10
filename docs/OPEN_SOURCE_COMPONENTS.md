# Open-Source Component Evaluation

Evaluation snapshot: 2026-08-10. Versions are pinned only when integration begins.

| Component | Repository | License | Purpose | Evaluated | Decision | Reason / integration approach | Version |
|---|---|---|---|---|---|---|---|
| GROBID | https://github.com/grobidOrg/grobid | Apache-2.0 | Scholarly PDF parsing | Preliminary | Candidate accepted for adapter evaluation | Run as isolated service; normalize TEI without making GROBID output canonical | TBD |
| ASReview | https://github.com/asreview/asreview | Apache-2.0 | Active-learning screening | Preliminary | Patterns/library evaluation accepted | Assess algorithms and APIs in Phase 10; retain richer local decision/provenance model | TBD |
| dedupe | https://github.com/dedupeio/dedupe | MIT | Fuzzy entity resolution | Preliminary | Candidate | Layer after deterministic DOI/PMID/title rules; never destructively merge source records | TBD |
| Temporal | https://github.com/temporalio/temporal | MIT (server); SDK licenses vary | Durable orchestration | Preliminary | Deferred behind port | Strong fit, but extra service complexity is premature before workflow semantics are implemented | TBD |
| Temporal Python SDK | https://github.com/temporalio/sdk-python | MIT | Worker/client integration | Preliminary | Deferred behind port | Typed durable workflows; evaluate replay/versioning operational cost in Phase 4 | TBD |
| OpenAlex / PyAlex | https://github.com/pyalex-tooling/pyalex | MIT | Scholarly metadata | Pending | Candidate | Implement behind `SearchProvider`; respect API etiquette and preserve raw source provenance | TBD |
| metafor | https://github.com/wviechtb/metafor | GPL-2.0 | Validated meta-analysis | Pending legal/architecture review | Isolate | Prefer a separately deployed R statistical service; review distribution implications before incorporation | TBD |

No candidate code is copied into this repository. Direct integration requires a maintenance, license, security, and fit review at the relevant phase.

Phase 2 adds no authentication dependency or SaaS. Its local-only provider uses Python standard-library scrypt and HMAC behind an application protocol; a production OIDC implementation remains deferred.
