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
| metafor | https://github.com/wviechtb/metafor | GPL-2.0 | Validated meta-analysis | Architecture evaluated; legal/operational review pending | Isolate | Future separately deployed provider accepting canonical payloads and returning structured results; no raw R objects or duplicated domain state | TBD |

No candidate code is copied into this repository. Direct integration requires a maintenance, license, security, and fit review at the relevant phase.

Phase 2 adds no authentication dependency or SaaS. Its local-only provider uses Python standard-library scrypt and HMAC behind an application protocol; a production OIDC implementation remains deferred.

The PRISMA/export foundation adds no external component. CSV, JSON, RIS, SHA-256, and deterministic
OOXML/XLSX generation use Python standard-library modules; no paid reporting provider or spreadsheet
SDK is introduced.

The Search Execution phase adds no external dependency. Its provider-neutral `SearchProvider`
protocol and fixture/manual/file-import acquisition methods preserve honest provenance without
calling PubMed, Europe PMC, OpenAlex, Crossref, or any paid API. Raw artifacts reuse the existing
local object-storage adapter.

The Risk of Bias foundation adds no external dependency and embeds no copyrighted published
instrument. Its declarative demonstration definition is intentionally incomplete and exists only to
validate the generic engine. Adoption of RoB 2, ROBINS-I, QUADAS-2, QUIPS, JBI, or another instrument
requires methodology, licensing, maintenance, and validation review at the time its complete
definition is introduced.

The Outcome Harmonization foundation adds no statistical dependency. Foundational RR, OR, RD, and
MD derivations use deterministic `Decimal` arithmetic and stop before pooling. A Phase 20 statistical
engine must complete the documented legal, maintenance, and numerical-validation review before
integrating a component such as `metafor`.

Phase 20 adds no external dependency. Its bounded native inverse-variance engine uses Python
standard-library numerical functions, explicit algorithm versioning, and repository-owned golden
fixtures. It is a reproducible foundation rather than a claim of parity with all `metafor` methods.
Future metafor integration remains behind the provider contract and requires license, packaging,
independent numerical validation, and operational review.

Phase 21 adds no external dependency and embeds no complete published GRADE instrument. Its
GRADE-compatible foundation is a generic human-judgment demonstration with explicit downgrade and
upgrade structures; adopting and maintaining complete official guidance requires separate
methodology, licensing, and validation work. No AI or statistical package makes certainty decisions.
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

Phase 24 adds no external component. Title/abstract suggestion validation, Wilson confidence
intervals, calibration bins, threshold simulations, disagreement classification, and evaluation metrics
use repository-owned deterministic Python code. The only provider is the existing offline deterministic
mock. No paid AI SDK, scholarly API, full-text classifier, statistical package, training framework, or
copyrighted screening instrument is introduced.

Phase 25 adds no third-party dependency. Full-text selection, Unicode/whitespace normalization,
evidence validation, metrics, and mock fixtures are deterministic repository code. `DocumentParser`
remains the provider boundary; the fixture parser is sufficient. Live GROBID, OCR/computer vision,
embeddings, external retrieval, and paid AI providers remain deferred.
## Phase 26 dependency impact

Governed structured extraction adds no new third-party runtime dependency. Typed validation, hashing,
field-aware chunk selection, evaluation, and mock fixtures use the existing Python/FastAPI/Pydantic/
SQLAlchemy stack. No OCR, computer-vision, model-training, paid-provider, or network-retrieval package
is introduced.

## Phase 27 dependency impact

Governed Risk-of-Bias assistance adds no third-party runtime dependency. Instrument normalization and
judgment rules remain repository-owned deterministic code; evidence selection/validation, hashing,
metrics, and mock safety fixtures use the existing Python/FastAPI/Pydantic/SQLAlchemy stack. No
complete published RoB 2 instrument, model-training package, retrieval/embedding service, OCR package,
paid AI SDK, or external provider is introduced. Complete instrument adoption remains a separate
methodology, licensing, maintenance, and validation decision.

Phase 28 adds no third-party runtime dependency. Outcome assistance uses the existing
Python/FastAPI/Pydantic/SQLAlchemy AI substrate, deterministic source/chunk validation, canonical
outcome rules, and offline mock fixtures. No conversion library, statistical engine, embedding or
retrieval service, paid model SDK, or production provider credentials were introduced.

Phase 29 adds no third-party runtime dependency. Certainty assistance uses the existing
Python/FastAPI/Pydantic/SQLAlchemy substrate, immutable certainty rules, deterministic evidence
validation, and offline mock fixtures. No complete published GRADE instrument, statistical engine,
retrieval/embedding service, paid AI SDK, external provider, or credential was introduced.

## Phase 30 dependency impact

The read-only Review copilot adds no third-party runtime dependency. Context assembly, citation
validation, hashing, policy/query persistence, and deterministic mock output use the existing
Python/FastAPI/Pydantic/SQLAlchemy stack and Next.js frontend. No embedding/retrieval service,
workflow SDK, paid AI SDK, external provider, manuscript generator, or credential was introduced.

## Phase 31 dependency impact

Durable workflow execution adds no third-party runtime dependency. Leases, bounded worker capacity,
payload validation/redaction, local handler dispatch, and deterministic runner behavior use the
existing Python/FastAPI/Pydantic/SQLAlchemy stack. No Temporal SDK, queue broker, provider SDK,
credential, scientific calculation package, or external worker runtime was introduced.
