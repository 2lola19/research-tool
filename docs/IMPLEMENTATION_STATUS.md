# Implementation Status

Last updated: 2026-08-17

## Status by milestone

| Milestone | Status | Evidence and boundary |
|---|---|---|
| Foundation (Phases 0/1) | VERIFIED | Source-level backend/frontend gates pass; Docker live-stack execution remains environment-blocked. |
| Identity and multi-tenancy (Phase 2) | VERIFIED | SQLite integration tests cover authentication, membership revocation, tenant isolation, direct-object access, and role boundaries. |
| Review Projects (Phase 3) | VERIFIED | Project ownership, membership, archive/restore, transfer, and dashboard tests pass. |
| Workflow State Machine (Phase 4) | VERIFIED | Persisted transitions, idempotency, ordered events, checkpoints, and control boundaries pass. |
| Provenance Ledger (Phase 5) | VERIFIED | Immutable prompt/AI/provenance/audit records, actor references, and scoped reads pass. |
| Protocol Engine (Phase 6) | VERIFIED | Structured immutable versions, decisions, hashes, audit, and provenance pass. |
| Search Strategy Domain (Phase 7) | VERIFIED | Canonical strategies, approved-protocol pinning, deterministic translators, replay, provenance, and audit pass. |
| Citation Import (Phase 8) | VERIFIED | RIS/BibTeX/CSV parsing, lossless batches, source records, idempotency, Article separation, and provenance pass. |
| Deduplication (Phase 9) | VERIFIED | Versioned deterministic scans, reviewable decisions, non-destructive retention, provenance, audit, and screening suppression pass. |
| Screening Foundation (Phase 10) | VERIFIED | Blinded-only rounds, authorized assignments, immutable decisions, deterministic outcomes, adjudication, closure, progression, provenance, and audit pass. |
| Concurrency Hardening (Phase 10.5) | VERIFIED | Five scoped sequential allocators use database uniqueness plus bounded savepoint retry; ordinary, uniqueness, retry, simulated contention, and rollback tests pass. |
| Document/Full-Text Foundation (Phase 11) | VERIFIED | Local-first PDF storage, checksum/provenance, retrieval states, canonical parser boundary, GROBID TEI fixture adapter, evidence locations, warnings, manual criterion screening, and tenant tests pass. Mature extraction remains deferred. |
| Study Families (Phase 12) | VERIFIED | Stable Review-scoped Study identity, non-destructive multi-Article links, role/method metadata, soft unlink history, provenance, audit, duplicate-link rejection, and tenant/review tests pass. |
| Versioned Extraction Schemas (Phase 13) | VERIFIED | Typed ordered field definitions, explicit allowed options, deterministic content hashes, immutable prior versions, review/tenant boundaries, and migration tests pass. |
| Provenance-First Manual Extraction (Phase 14) | VERIFIED | Study/schema-version pinned runs, typed values, explicit missingness, linked Article/Document evidence, resumable saves, audit/provenance, and permission tests pass. |
| Extraction Verification (Phase 15) | VERIFIED | Deterministic canonical comparison, evidence-aware conflicts, immutable original snapshots, authorized adjudication, verification state transitions, audit/provenance, and tenant tests pass. |
| Deterministic PRISMA + Reproducible Export (Phase 16 foundation) | VERIFIED | Database-derived record/report/Study counts, readiness blockers, immutable snapshots, CSV/XLSX/JSON/RIS artifacts, manifests, SHA-256 verification, audit/provenance, tenant boundaries, and minimal Reports/Exports UI pass. |
| Search Execution + Identification-Source Provenance (Phase 17) | VERIFIED | Structured source classes, immutable repeated/corrected executions, exact query/provider/method/status history, citation-import discovery links, raw artifact integrity, deterministic PRISMA grouping, versioned export documentation, and minimal Search UI pass. |
| Risk of Bias Foundation (Phase 18) | VERIFIED | Versioned declarative instruments, Study-design validation, Study Family evidence, independent blind assessments, deterministic conflict detection, immutable corrections/adjudication, export schema v3, and minimal RoB UI pass. |
| Outcome + Effect-Estimate Harmonization (Phase 19) | VERIFIED | Versioned canonical outcomes, explicit extraction mappings, review-specific timepoint/unit/scale configuration, structured reported/derived estimates, deterministic RR/OR/RD/MD calculations, zero-event safeguards, synthesis-candidate readiness, export schema v4, and minimal Outcomes workspace pass. |
| Deterministic Statistical Synthesis (Phase 20) | VERIFIED | Immutable explicit analysis specifications/sets/runs, Study independence and live-readiness rechecks, inverse-variance fixed-effect and DerSimonian-Laird random-effects synthesis, structured heterogeneity/weights/diagnostics, leave-one-out sensitivity, deterministic SVG forest artifacts, export schema v5, and minimal Analysis workspace pass. |
| GRADE / Certainty-of-Evidence Foundation (Phase 21) | VERIFIED | Versioned human-first certainty frameworks and thresholds, outcome/evidence-body assessments, explicit downgrade/upgrade judgments, deterministic candidates, independent blinded review/reveal, immutable revisions, adjudication, RoB/analysis evidence hashes and staleness, Evidence Profiles, Summary-of-Findings rows, export schema v6, and minimal Certainty workspace pass. |

| Summary Findings + Reproducibility Reporting (Phase 22) | IMPLEMENTED | Deterministic report specifications/readiness, immutable report snapshots/artifacts, scientific-content hashes, structured JSON/HTML/XLSX, validated reproducibility ZIPs, and reporting workspace foundation. |
| AI Provider Foundation (Phase 23) | VERIFIED | Provider-neutral task execution, immutable model/prompt versions, bounded runs, structured validation, append-only proposals/acceptance, deterministic mock execution, and provenance. |
| Governed AI Screening Assistance (Phase 24) | IMPLEMENTED | Versioned screening policy, assignment-scoped title/abstract suggestions, server-enforced blinded/assisted reveal, deterministic evaluation metrics, case-level error taxonomy, migration, API, UI, provenance, audit, and tenant tests. |
| Governed AI Full-Text Screening (Phase 25) | IMPLEMENTED | Document/version/parser-pinned bounded suggestions, exact evidence/criterion validation, structured uncertainty, direct-ID blinding, human-only canonical acceptance, staleness, batch isolation, full-text evaluation, migration, API, UI, and tenant tests. |
| Governed AI Structured Extraction (Phase 26) | IMPLEMENTED | ExtractionSchemaVersion-pinned typed field proposals, exact report/document/chunk evidence, source/normalized value separation, explicit missingness/conflicts/limitations, direct-ID blinding, human-only manual-service acceptance/editing, staleness, batch isolation, field-level safety evaluation, migration, API, UI, and tenant tests. |
| Governed AI Risk-of-Bias Assistance (Phase 27) | IMPLEMENTED | Instrument-version-pinned signalling-answer proposals, Study Family/document/parser/chunk provenance, deterministic evidence and declarative-rule validation, blinded/assisted reveal, human disposition through the existing RoB service, abstention/high-risk evaluation, migration, API, UI, and tenant tests. The bundled instrument remains a demonstration framework, not complete RoB 2. |

## Validation evidence

### Phase 26 validation (2026-08-17)

- Backend Ruff check and scoped format check pass; strict mypy passes for 201 source files. Eight
  focused unit tests, the Phase 26 assignment-scoped integration test, and the full migration test
  pass. Completed coverage shards retain the repository threshold at 85% (16,648 statements); AI,
  downstream science, and canonical extraction regression shards pass.
- SQLite upgrades through `20260817_0027` and downgrades fully to base. Composite tenant/review foreign
  keys cover schemas, assignments, Studies, reports/Documents, processing runs, blocks, proposals,
  human reviewers, reference datasets, evaluation cases, and classifications.
- Frontend ESLint and TypeScript pass. The Next.js production bundle compiles successfully before its
  TypeScript worker is blocked by Windows `spawn EPERM`; Vitest is blocked at Vite config startup by
  the same host restriction.
- `ENVIRONMENT_BLOCKED`: the monolithic pytest invocation exceeded its bounded ten-minute run without
  emitting a failure, so deterministic repository-local shards were used. Some filesystem/temp shards
  cannot traverse pytest-created directories due Windows `Access denied`; no ACL changes were made.

- Backend: repository Ruff check/format and strict mypy pass; Phase 24-focused unit and integration tests pass. The full pytest run was attempted with a repository-local temp workaround but exceeded the unelevated fallback command limit without a test failure report.
- Frontend: TypeScript passes. ESLint, Vitest, and the Next.js 16 production build were attempted; the unelevated fallback blocked their subprocess/config work with timeout or `spawn EPERM` errors.
- Alembic is linear through `20260815_0025`. A temporary SQLite database upgrades through Phase 24 and downgrades fully to base in the focused migration test.
- Focused PRISMA tests cover record/report/Study distinctions, confirmed-duplicate counting, title/full-text completeness, retrieval state, Study Family counting, structured exclusion reasons, stable source references, immutable snapshots, role restrictions, and tenant non-enumeration.
- Focused export tests cover deterministic byte rendering, CSV formula neutralization, portable XLSX archive structure, JSON/RIS output, all download formats, manifests, checksums, preservation of prior artifacts, provenance/audit, and tenant authorization.
- Focused Search Execution tests cover structured PRISMA source groups, exact query and strategy/translation retention, repeated searches and corrections, status events, provider/import reconciliation, multi-source discovery, citation-source linkage, raw artifact integrity, stable exports, role restrictions, cross-review linking, and cross-tenant non-enumeration.
- Focused Risk of Bias tests cover declarative ordering/rules, answer-choice validation, Study-design compatibility, assessor blindness, structured disagreement, submitted-record immutability, adjudication, Study Family evidence spanning multiple Articles, unrelated-Study evidence rejection, audit/provenance, export ordering, role restrictions, and tenant/review non-enumeration.
- Focused Outcome Harmonization tests cover immutable versions, explicit mapping, original-value retention, review-scoped time windows, context-safe unit conversion, direction transformations, RR/OR/RD/MD formulae, defined decimal precision, zero-event behavior, verified-source requirements, duplicate-Study detection, adjusted/population compatibility, deterministic export ordering, and tenant/review non-enumeration.
- Focused Statistical Synthesis tests cover independent golden fixed/random calculations, explicit transformations and confidence methods, Study weights, Q/Q p-value/I-squared/tau-squared, prediction diagnostics, leave-one-out sensitivity, Study independence, current READY enforcement, live staleness rechecks, failure-safe edge cases, immutable/checksummed forest artifacts, export schema v5, centralized roles, and tenant/review/direct-ID non-enumeration.

## Environment-blocked validation

- `ENVIRONMENT_BLOCKED`: Docker Compose live execution was not exercised. PostgreSQL health, PostgreSQL-specific migration behavior, container health, inter-service communication, and live GROBID execution remain unverified.
- No Docker recovery, reset, prune, volume/image deletion, distribution unregister, reinstall, or security-policy change was performed.
- SQLite is used only for local adapter/integration validation; PostgreSQL remains the canonical production database.

## Findings and residual risk

- CRITICAL: none found.
- HIGH: none found.
- MEDIUM resolved: PRISMA readiness now blocks unassigned imported records, open/multiple screening rounds, unsettled retrieval, retrieved-but-unscreened reports, conflicting multi-Document eligibility decisions, and included reports without Study assignment.
- MEDIUM resolved: snapshot source references and export queries use stable ordering; deduplication candidate/decision references retain correct IDs; confirmed duplicate source rows are counted once.
- MEDIUM resolved: transactional database artifact storage, immutable ORM guards, download-time checksum verification, sanitized filenames, and spreadsheet formula neutralization prevent partial-file, mutation, integrity, and injection failures in the foundation.
- MEDIUM resolved: completed SearchExecution identity fields and event history are append-only; one explicit correction may supersede a terminal execution, while routine living-review updates remain independent history.
- MEDIUM resolved: PRISMA identification uses distinct execution-linked source records and structured source classes, never source-name inference or deduplicated Article counts; mismatched provider/import totals and cross-group links block final readiness.
- MEDIUM resolved: raw search artifacts use opaque tenant/review keys, immutable checksum metadata, upload-failure cleanup, authorization before key resolution, and download-time size/SHA-256 verification.
- MEDIUM resolved: submitted RoB assessments are service-locked and corrected only by a superseding revision; comparison uses current submitted revisions and adjudication appends a final snapshot without changing either assessor record.
- MEDIUM resolved: RoB evidence is resolved through the existing Document evidence location and active Study Family link, preventing Article/Study confusion and cross-review evidence leakage.
- MEDIUM resolved: month/year durations are preserved but are not converted through a universal average; only days/weeks normalize intrinsically, and calendar-unit harmonization requires an explicit review-specific rule.
- MEDIUM resolved: reported estimates with adequate uncertainty are not rejected solely for missing arm sizes; derived estimates retain structured components, provenance, and measure-appropriate variance scales.
- MEDIUM resolved: synthesis readiness detects incompatible outcomes/timepoints/units/scales, unverified extraction, duplicate Study estimates, adjustment/population mismatches, and zero-event policy needs without performing statistical pooling.
- MEDIUM resolved: AnalysisSet creation now requires a current Phase 19 READY evaluation and then independently rechecks the selected live estimates; execution repeats that check and compares the canonical input hash, preventing stale-ready reuse.
- MEDIUM resolved: completed/failed statistical runs and result children are immutable, every consequential method is explicit, ratio measures use a versioned log transform, no continuity correction is hidden, and unsupported dependent multi-arm/cluster/crossover inputs block safely.
- MEDIUM resolved: all read-maximum-plus-one allocators now use scoped database uniqueness and bounded savepoint retries; PostgreSQL remains the production concurrency validation target.
- LOW: worker dispatch remains a lifecycle shell. Phase 11 keeps processing synchronous behind a parser/service boundary; durable claiming and retries remain deferred.
- Unblinded screening remains rejected until an explicit reveal policy exists.
- GROBID is evaluated and adapter-ready, but its live service and resource profile are not validated on this host.

## Deferred and planned

- Advanced estimators/dependency policies, general subgroup inference, meta-regression, publication-bias inference, network meta-analysis, mature report authoring, paid AI providers, and real external scholarly APIs remain out of scope until separately authorized.
- GROBID live deployment, ASReview, external scholarly APIs, R/metafor, paid AI providers, production identity, and cloud object storage remain deferred.

## Architecture decisions

- PostgreSQL is canonical; SQLite is permitted only for fast adapter and local integration tests.
- Workflow state, scientific data, provenance, audit, and human checkpoints remain physically distinct.
- Documents remain distinct from Articles and Studies and preserve multiple source files per Article.
- Original full-text bytes are immutable storage artifacts; parser output is separate, versioned by processing run, and referenced by evidence locations.
- PRISMA counters are derived, not manually persisted; immutable snapshots retain algorithm version, readiness, and ordered source references.
- Export artifacts are append-only exact bytes with manifests and SHA-256 checksums; CSV/XLSX/JSON/RIS generation is deterministic local code.
- Search design remains separate from append-only SearchExecution history; source classifications are structured, citation discovery links survive deduplication, and PRISMA identification counts derive only from eligible completed execution links.
- Risk of Bias instruments are declarative immutable versions; assessments apply to Studies, reuse Document evidence locations across Study Families, remain assessor-owned until authorized reveal, and preserve original submissions through append-only comparison/adjudication history.
- Outcome definitions are immutable scientific versions; mappings preserve reported values and timing, conversions require structured review-specific rules, effect derivations retain components and formula versions, and candidate readiness snapshots never perform pooling.
- Analysis specifications, sets, terminal runs, weights, sensitivities, and artifacts are immutable scientific records; the provider-neutral synthesis engine consumes only canonical revalidated inputs, and forest rendering is separate from statistical calculation.
- Tenant actor context is resolved from active database membership on every request; storage keys never substitute for authorization.

See [ADR-012](adr/ADR-012-concurrent-sequential-allocation.md), [ADR-013](adr/ADR-013-document-processing-and-grobid-adapter.md), [ADR-014](adr/ADR-014-study-extraction-verification.md), [ADR-015](adr/ADR-015-deterministic-prisma-and-reproducible-exports.md), [ADR-016](adr/ADR-016-search-execution-identification-provenance.md), [ADR-017](adr/ADR-017-versioned-risk-of-bias-assessments.md), [ADR-018](adr/ADR-018-outcome-effect-harmonization-readiness.md), [ADR-019](adr/ADR-019-deterministic-statistical-synthesis.md), [ADR-022](adr/ADR-022-provider-neutral-ai-execution-and-human-acceptance.md), [ADR-023](adr/ADR-023-governed-ai-screening-assistance-and-evaluation.md), [API_REQUIREMENTS.md](API_REQUIREMENTS.md), and [OPEN_SOURCE_COMPONENTS.md](OPEN_SOURCE_COMPONENTS.md).

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

### Phase 23 validation (2026-08-14)

- Backend: Ruff and format PASS; strict mypy PASS (185 source files); pytest 209 PASS; coverage 92.98% (threshold 85%).
- Migration: full SQLite upgrade through `20260814_0024` and downgrade to base PASS.
- Frontend: ESLint PASS; TypeScript PASS; Vitest 9 PASS; Next.js 16.3 production build PASS.
- Repository: git diff --check PASS; focused secret audit PASS.
- Live paid AI providers and PostgreSQL remain intentionally unexecuted/environment-blocked.

## Phase 24 validation (2026-08-16)

- Backend: focused Ruff lint/format, Python compilation, strict mypy, unit screening tests, and the
  assignment-scoped end-to-end screening integration test pass. The integration test covers blinded
  withholding, post-decision reveal, evaluation dataset/result/case-result/error classification,
  provenance/audit, and cross-tenant not-found behavior.
- Migration/schema: the Phase 24 metadata creates nine screening tables, including assignment-level
  proposal foreign keys; the linear `20260815_0025` upgrade/downgrade path is covered by migration
  tests. PostgreSQL-specific execution remains environment-blocked.
- Frontend: TypeScript passes. ESLint, Vitest, and the Next.js production build reached the local
  toolchain but are environment-blocked by the unelevated Windows fallback (`spawn EPERM` during
  config/test/build subprocess work); no code diagnostic was emitted by those failures.

## Phase 25 validation (2026-08-16)

- Full Ruff lint/format and strict mypy pass (196 source files). Eleven deterministic Phase 25 unit
  tests, the assignment-scoped API integration, and the SQLite full upgrade/downgrade pass. Coverage
  includes bounded/scoped chunks, normalization, fabricated
  criteria/chunks/quotes/documents/pages, abstention, prompt injection, false-negative direction,
  wrong-criterion scoring, direct-ID blinding, canonical-state non-mutation, post-decision reveal,
  generic-endpoint closure, policy-change resistance, tenant non-enumeration, unchanged PRISMA
  counts, evaluation, audit, document replacement staleness, and protocol staleness.
- Frontend ESLint and TypeScript pass. The integrated workspace exposes readiness, document/parser pins,
  withholding/reveal, staleness, missing information, evidence, human acceptance, and safety metrics.
- `ENVIRONMENT_BLOCKED`: normal pytest Temp/basetemp creation receives Windows `Access denied` in the
  intentional unelevated sandbox. The exact full command passed 118 tests but produced 108 Temp-fixture
  setup errors; its resulting 64% partial coverage is not a valid full-suite measurement and cannot
  satisfy the 85% gate. Focused tests and migration validation used pre-created local paths and direct
  fixture execution without ACL changes.
  Vitest fails before loading tests at Vite config startup with `spawn EPERM`; the Next.js build compiles
  successfully, then its TypeScript worker hits `spawn EPERM`. PostgreSQL, live GROBID, Docker, and
  paid/live AI providers remain unexecuted.
## Phase 26 governed AI structured extraction assistance

Phase 26 implements schema-pinned typed extraction proposals over explicit Study/report/document
inputs. Deterministic source preparation persists selected and omitted chunk manifests; field-level
validation enforces exact schema IDs, types, options, units, missingness, source/report scope, chunks,
metadata, quotes, and value support. Conflicts and table/supplement/parser limitations are explicit.
OFF/BLINDED_AI/ASSISTED behavior is server-enforced, human accept/edit goes through the existing
manual extraction service, and AI does not count as an extractor or change canonical completion.

Field-level evaluation supports qualified human/curated reference standards, numeric error and
explicit tolerances, categorical confusion, missingness, hallucination and grounding metrics,
calibration bins, hypothetical thresholds, and high-risk queues. Repeated runs are immutable and
schema/document/parser/task/prompt changes report staleness without rerun.

## Phase 27 Risk-of-Bias assistance validation

- Focused unit coverage passes for exact instrument answer choices, fabricated chunk/source-block/quote rejection, valid abstention, declarative domain/overall derivation, descriptive metrics, high-risk underestimation flags, prompt safety, and deterministic mock fixtures.
- The repository-local Phase 27 integration shard passes. It covers approved-instrument/readiness gates, processed Study Family Documents, BLINDED_AI withholding, ASSISTED human disposition, generic-route closure, canonical assessment immutability, post-submission reveal, evaluation abstention metrics, audit links, and tenant/assessor direct-ID non-enumeration.
- Ruff, format, strict mypy, compile, and the full SQLite upgrade/downgrade chain through `20260818_0028` pass. Frontend ESLint and TypeScript pass. The ordinary Windows pytest temp root remains environment-blocked; a narrow repository-local temp root was used for the integration shard.
- No complete published RoB 2 instrument was added. The demonstration instrument continues to be labeled as such, and AI never writes canonical domains, overall judgments, submissions, comparisons, or adjudications.
