# Roadmap

1. **Foundation (source complete; live stack environment-blocked):** repository, API, database/migrations, frontend, local containers, provider contracts, quality gates.
2. **Identity and multi-tenancy (complete):** local authentication, organizations, memberships/RBAC, actor context, tenant tests.
3. **Review Projects (complete):** tenant-owned project metadata, review members, ownership transfer, archive/restore, dashboard shell.
4. **Workflow State Machine (complete):** persisted workflow runs, explicit transitions, checkpoints, and transition invariants.
5. **Provenance Ledger (complete):** append-only audit/provenance/AI-run registries.
6. **Protocol Engine (complete):** immutable structured protocol versions and approval checkpoints.
7. **Search Strategy Domain (complete):** canonical search concepts and deterministic provider translators/fixtures.
8. **Citation Import (complete):** RIS/BibTeX/CSV source records with import provenance.
9. **Deduplication (complete):** deterministic identifiers followed by reviewable, non-destructive fuzzy candidates.
10. **Screening Foundation (complete):** reviewer queues, blinded immutable decisions, deterministic conflicts, adjudication, and full-text progression.
11. **Documents and full-text foundation (verified):** storage/validation, canonical parser adapter, evidence locations, warnings, and manual full-text eligibility.
12. **Study families (verified):** stable Study identity and non-destructive multi-Article relationships.
13. **Versioned extraction schemas (verified):** typed, immutable schema versions with explicit missingness metadata.
14. **Manual extraction (verified):** Study-level typed values with Article/Document evidence and provenance.
15. **Extraction verification (verified):** deterministic comparison, explicit conflicts, and human adjudication history.
16. **Deterministic PRISMA and reproducible export foundation (implemented):** database-derived flow counts, immutable snapshots, readiness blockers, portable CSV/XLSX/JSON/RIS artifacts, manifests, and checksums.
17. **Search execution and identification-source provenance (implemented):** structured source classes, immutable repeated executions, exact query/provider/method/status history, import discovery links, raw artifacts, deterministic PRISMA grouping, and search documentation exports/UI.
18. **Risk of Bias foundation (verified):** versioned declarative instruments, Study-design compatibility, multi-Article evidence, independent blind assessments, deterministic disagreement, human adjudication, and reproducible exports.
19. **Outcome/effect-estimate harmonization (verified):** versioned outcomes, explicit extraction mappings, Review-specific timepoints/units/scales, structured reported/derived effects, immutable candidate sets, and deterministic readiness without pooling.
20. **Deterministic meta-analysis foundation (implemented):** versioned explicit specifications,
    revalidated Study-independent sets, fixed-effect and DerSimonian-Laird random-effects synthesis,
    heterogeneity/prediction diagnostics, leave-one-out sensitivity, and reproducible SVG artifacts.
21. **GRADE/certainty foundation (verified):** versioned human-first frameworks and thresholds,
    outcome/evidence-body scoped assessments, explicit downgrade/upgrade judgments, deterministic
    candidates, independent blind review and adjudication, immutable revisions, RoB/analysis
    evidence hashes and staleness, Evidence Profiles, Summary-of-Findings rows, exports, and UI.
22. **Summary findings and reproducibility reporting (implemented):** deterministic report snapshots, readiness profiles, structured Evidence Profile/SoF consumption, checksummed JSON/HTML/XLSX, validated reproducibility packages, and minimal reporting UI.
23. **AI provider foundation (implemented):** provider-neutral task execution, immutable model/prompt
    versions, bounded runs, structured validation, human acceptance, and deterministic mock execution.
24. **Governed AI screening assistance (implemented):** versioned policy, assignment-scoped title/abstract
    suggestions, server-enforced blinded/assisted reveal, provenance/audit links, deterministic evaluation,
    calibration, threshold simulation, and human error taxonomy.
25. **Remaining V1 completion envelope (in progress):** durable jobs/recovery, production scholarly and
    AI provider adapters, document/object-storage hardening, collaboration/QC UX, production readiness,
    and end-to-end release validation. Advanced estimators, dependency policies, subgroups,
    meta-regression, publication-bias inference, network meta-analysis, and mature reports remain
    deferred beyond V1.

Each milestone must meet the definition of done in the master specification before progression.

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

Phase 24 is the first scientific AI assistance workflow. It is deliberately limited to title/abstract
screening suggestions under a Review policy and approved protocol. Suggestions remain proposals; human
screening decisions remain canonical and immutable. Blinded and assisted modes, assignment-level reveal
audits, deterministic evaluation datasets/metrics, and error classifications are implemented locally.
At the Phase 24 checkpoint, full-text assistance, production providers, autonomous decisions, and
Phase 25 work remained deferred.

## Phase 25 complete: governed AI full-text screening

Phase 25 extends existing AI and screening boundaries to exact Document/parser inputs, bounded
structured chunks, deterministic criterion/evidence checks, structured uncertainty, server-side
BLINDED_AI, human-only canonical acceptance, immutable staleness, bounded batch execution, and formal
full-text safety evaluation. Live providers, OCR, cross-report evidence, active learning, and autonomous
exclusion remain deferred.

## Phase 26 complete: governed AI structured extraction assistance

Phase 26 adds schema-pinned typed proposals, exact document/chunk evidence, source-versus-normalized
value semantics, explicit uncertainty/conflicts/limitations, server-side blinding, human-only writes
through manual extraction, immutable staleness, bounded batch execution, and deterministic field-level
safety evaluation. It does not add OCR, live providers, AI verification, or autonomous acceptance.

## Recommended Phase 27

Build governed, evidence-grounded AI Risk of Bias assistance against immutable instrument versions and
human-only domain judgments. Preserve independent assessors, blinding, deterministic validation,
Study/document evidence, formal evaluation, and no autonomous judgment or adjudication.

## Phase 27 complete: governed AI Risk-of-Bias assistance

Phase 27 implements the recommendation above. The governed task pins Review, Study, assessment,
approved immutable instrument version, question choices, explicit Study Family source Documents,
successful parser runs, selected evidence chunks, prompt/model/task versions, and hashes. Exact
deterministic validation rejects invented questions, choices, documents, chunks, source blocks,
pages, sections, or quotes. Domain and overall suggestions are derived only from validated answers
through the existing declarative RoB rules; they are never canonical AI judgments.

`BLINDED_AI` withholds structured output, validation, and suggestions until the assessor submits the
canonical assessment. `ASSISTED` permits an assignment-scoped human view and records disposition;
neither mode lets AI submit answers, satisfy independent dual assessment, adjudicate, or alter
submitted records. Evaluation results are immutable/descriptive, include signalling/domain/overall
agreement, evidence grounding, abstention/coverage, confusion counts, calibration status, and a
dangerous-underestimation queue. The demonstration instrument is not complete RoB 2.

## Phase 28 governed outcome/effect harmonization assistance

The next scientific AI surface is an advisory projection over verified extraction values and
immutable OutcomeDefinitionVersions. It may suggest an evidence-grounded mapping or a reported
effect candidate, but cannot convert values, calculate effects, impute components, pool studies, or
change analysis readiness. Human dispositions call the existing canonical outcome service with an
explicit payload. Evaluation remains descriptive and separate from canonical outcome data.

## Phase 29 complete: governed certainty-of-evidence/GRADE assistance

The certainty assistant is an advisory projection over assessor-owned in-progress assessments,
immutable framework versions, included Studies, and explicitly selected processed evidence. It
provides only grounded summaries, permitted domain suggestions, or abstention. Human dispositions
call the existing certainty service; no AI final certainty, threshold, publication-bias inference,
upgrade/downgrade, calculation, adjudication, or submission is supported. Evaluation is descriptive
and separate from canonical certainty data. This is a structured foundation, not a claim of full
official GRADE support.

## Recommended Phase 30

Build the read-only evidence-aware Review copilot/project intelligence surface described in the
master plan. Preserve allowlisted context, explicit citations, stale-context labels, tenant scope,
and no canonical writes or scientific calculation.

## Phase 30 complete: read-only evidence-aware Review copilot

Phase 30 implements the bounded copilot surface. It provides explicit task keys, versioned Review
policy, deterministic PRISMA/workflow context, exact source citations, immutable query history,
tenant/review authorization, and a read-only frontend workspace. It does not provide arbitrary
retrieval, workflow mutation, scientific calculation, or manuscript generation. The offline mock
abstention and live-provider/deployment limitations remain documented.

## Phase 31 complete: durable workflow jobs and worker execution

Phase 31 turns the workflow lifecycle shell into a claimable local worker contract. Explicit payload
schemas, bounded attempt limits, tenant/review-scoped leases, heartbeats, worker capacity/health,
failure/requeue paths, lease-expiry recovery, deterministic handler registration, redacted claim
responses, and a local `--once` runner are implemented. Scientific work remains behind existing
domain/provenance services; Phase 32 adds richer workflow resumability, retry taxonomy, backoff,
dead-letter handling, and operational reconciliation.

## Phase 32 complete: workflow resumability and operational recovery

Phase 32 adds immutable definition/step contracts, bounded retry taxonomy and backoff, attempt
timeouts, dead-letter/manual recovery, normalized step checkpoints, durable idempotent resume and
recovery operations, lease/timeout reconciliation diagnostics, tenant-scoped recovery APIs, and a
local expired-attempt recovery command. It does not silently replay consequential writes, override
human checkpoints, or require Temporal/cloud infrastructure.
