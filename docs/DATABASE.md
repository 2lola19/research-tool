# Database

PostgreSQL is the canonical store. SQLAlchemy 2 typed models define persistence mappings and Alembic owns every schema change.

Rules:

- Use database constraints for uniqueness, referential integrity, allowed ranges, and immutable identity where practical.
- Use UTC timezone-aware timestamps.
- Prefer UUID identifiers for externally exposed records.
- Preserve imported source records and merge links rather than destructively deleting duplicates.
- Avoid unbounded JSON as a substitute for modeled scientific data. JSON is appropriate for provider payload snapshots and evolving structured metadata with a stable envelope.
- Keep workflow, evidence, provenance, and audit tables distinct.
- Tests may use SQLite only for adapter-fast tests; PostgreSQL integration tests remain required for database-specific behavior.

The Phase 1 migration is intentionally empty: it establishes migration mechanics without adding throwaway schema before a domain is implemented.

Migration `20260810_0002` adds `users`, `organizations`, `memberships`, `local_credentials`, `reviews`, and `review_memberships`. Composite foreign keys prevent review owners, creators, assignees, and assigners from crossing organization boundaries. Normalized email/slug, non-empty names/titles, role values, membership uniqueness, and removal metadata are database constrained.

Membership removal is represented by `removed_at` and `removed_by_user_id`; authorization queries require `removed_at IS NULL`. Review queries always include `organization_id`, even when the review UUID is globally unique, to preserve non-enumeration behavior.

Migration `20260810_0003` adds organization-unique review project slugs, descriptions, and paired archive actor/time metadata. Existing reviews receive deterministic ID-derived slugs during upgrade. The archiving actor uses the same organization-membership composite boundary as owners, creators, and review assignees.

Migration `20260810_0004` adds `workflow_runs`, `workflow_jobs`, `job_events`, and `human_checkpoints`. Composite keys propagate both organization and review ownership into jobs and checkpoints. Idempotency is unique per tenant/review run and per workflow run. Job events have a unique monotonic sequence per job; checkpoint resolution actor/time metadata is paired by constraint.

Migration `20260810_0005` adds immutable `prompt_versions`, captured `ai_runs`, `scientific_provenance`, and `audit_events`. Composite foreign keys prevent prompt, AI-run, provenance actor, and review references from crossing tenants or reviews. Check constraints enforce actor/reference combinations, source-pair completeness, confidence bounds, statuses, and positive prompt versions. ORM lifecycle guards reject update and delete mutations; repositories expose append and scoped-list operations only.

Migration `20260810_0006` adds immutable `protocol_versions` and one append-only `protocol_decision` per version. Versions are monotonically numbered within an organization/review, contain validated structured content, and retain a canonical SHA-256 content hash. Composite tenant/review and membership keys constrain creators and decision actors.

Migration `20260810_0007` adds immutable `search_strategy_versions` and `search_translations`. Each canonical strategy is tenant/review scoped and references an approved protocol version in the same boundary. Each provider/translator-version output is unique and append-only, so syntax changes never overwrite historical queries.

Migration `20260810_0008` adds `citation_import_batches`, `citation_source_records`, and `articles`. Batches retain exact source text and a content hash. Source rows preserve parsed raw metadata and link one-to-one to newly created Article records. DOI and PMID are normalized but deliberately not unique: import never performs hidden deduplication.

Migration `20260810_0009` adds immutable `deduplication_runs`, `duplicate_candidates`, and `deduplication_decisions`. Runs are idempotent for an algorithm version and Article input hash. Candidate pairs are tenant/review constrained to two distinct Articles, with bounded scores and explicit reason codes. A single append-only decision confirms or rejects a candidate without changing either Article; a confirmation explicitly identifies the retained Article so downstream systems suppress only the other member of the pair.

Migration `20260810_0010` adds `screening_rounds`, `screening_assignments`, immutable `screening_decisions`, derived `screening_outcomes`, immutable `screening_adjudications`, and idempotent `screening_progressions`. Composite keys carry organization and review scope through every Article, round, assignment, reviewer, and outcome reference. Decision rows repeat and constrain their complete assignment boundary, while check constraints enforce final decision/reason and round closure metadata invariants.

Migration `20260810_0011` adds tenant-scoped `documents`, processing runs, canonical document blocks, evidence locations, document warnings, and protocol-pinned full-text criterion judgments. Documents preserve source metadata, opaque storage keys, original filename, media type, size, SHA-256, retrieval state, and uploader. Multiple files per Article are supported; exact uploaded-file duplicates are rejected by a scoped checksum constraint. Full-text judgments retain criterion decisions, reasons, optional evidence locations, reviewer, protocol version, and timestamps. Original bytes remain in object storage and parser output is stored separately.

Migration `20260811_0012` adds stable `studies` and non-destructive `study_article_links`. Link rows retain role, method, confidence, source evidence, actor, and soft-unlink metadata. Composite tenant/review foreign keys prevent Articles from another Review or Organization from entering a family.

Migration `20260811_0013` adds `extraction_schemas` and immutable `extraction_schema_versions`. Version payloads are canonicalized and hashed; version numbers are unique per schema and prior versions are never updated.

Migration `20260811_0014` adds `extraction_runs` and typed `extraction_values`. Values use typed columns plus explicit missingness and require a same-tenant Article or Document evidence source. Composite keys bind runs and values to their Review and Organization.

Migration `20260811_0015` adds `extraction_conflicts` and `extraction_verifications`. Both original value snapshots and evidence snapshots remain available for adjudication; resolution updates verification state and retains adjudicator, reason, and timestamp.

Migration `20260811_0016` adds immutable `prisma_snapshots`. Each snapshot stores deterministic
counts, readiness blockers, source references, algorithm version, creator, and tenant/review scope.
Counters are derived from canonical scientific records and are never manually persisted as mutable
workflow state.

Migration `20260811_0017` adds immutable `export_artifacts`. Each row is bound to a same-tenant
PRISMA snapshot and stores exact artifact bytes, format, schema version, filename, media type,
manifest, byte size, SHA-256 checksum, creator, and timestamp. Transactional blob storage prevents
half-written repository-local export files in this foundation.

Migration `20260811_0018` adds `identification_sources`, immutable `search_executions`, append-only
`search_execution_events`, `search_execution_citation_links`, and immutable
`search_execution_artifacts`. Composite foreign keys bind sources, strategies, translations,
superseded executions, citation source records, artifacts, and actors to one Organization and
Review. Structured check constraints enforce source classifications, acquisition methods, states,
non-negative result counts, and completed-result-count presence. Scoped unique constraints retain
one link per execution/source record and one raw artifact per execution/checksum. Supporting
composite unique keys on citation source records and search translations enable tenant-safe foreign
keys. The migration upgrades linearly from `20260811_0017` and reverses completely on SQLite.

Migration `20260811_0019` adds canonical `study_design` metadata plus `rob_instruments`, immutable
`rob_instrument_versions`, append-only version decisions, assessor-owned `rob_assessments`,
structured signalling answers and domain judgments, deterministic `rob_comparisons`, and append-only
`rob_adjudications`. Composite foreign keys repeat Organization and Review scope across Studies,
instrument versions, assessor membership, correction history, comparisons, and existing Document
evidence locations. Unique constraints preserve version numbers, assessor/round/revision identity,
single explicit corrections, one comparison per canonical pair, and one adjudication per conflict.
Allowed states, positive rounds/revisions, and 64-character definition hashes are constrained. The
migration upgrades linearly from `20260811_0018` and fully downgrades on SQLite.

Migration `20260811_0020` adds logical and immutable versioned outcome definitions, Review-specific
timepoint windows, unit definitions, measurement scales, append-only extraction mappings, structured
effect estimates, synthesis candidate sets, and immutable analysis-readiness snapshots. Composite
tenant/review foreign keys cover Studies, extraction values, protocol versions, evidence locations,
mapping corrections, and configuration. Normalized `effect_estimate_sources` and
`synthesis_candidate_estimates` tables enforce every scientific source/selection link rather than
trusting serialized identifiers. Check constraints cover allowed states, ranges, rule ordinals,
time anchors, direction transforms, effect measures, variance scales, analysis populations, and
readiness states. ORM guards reject updates/deletes across the scientific history. The migration
upgrades linearly from `20260811_0019` and fully downgrades on SQLite.
## Statistical synthesis tables

`analysis_specifications` and immutable `analysis_specification_versions` store the logical method
and every explicit policy version. `analysis_sets` and normalized `analysis_set_estimates` retain the
revalidated Phase 19 candidate selection and deterministic input hash. `meta_analysis_runs` stores
terminal execution metadata and structured output; `meta_analysis_study_weights` and
`meta_analysis_sensitivity_results` retain deterministic child results. `analysis_artifacts` stores
immutable SVG bytes and SHA-256 metadata.

All tables repeat Organization and Review scope. Composite foreign keys prevent cross-tenant or
cross-Review specifications, candidates, estimates, runs, actors, and artifacts. Scoped indexes
serve Review histories and run children; uniqueness constraints protect specification version
numbers, one estimate link per set, one weight per Study/run, one leave-one-out child per omitted
Study/run, and artifact identity. ORM guards reject scientific version/set/result/artifact updates
and reject mutation after a run reaches `COMPLETED` or `FAILED`. Migration `20260812_0021` is linear
after `20260811_0020` and supports full reverse removal.

## Certainty-of-evidence tables

Migration 20260812_0022 adds logical certainty frameworks and immutable content-hashed versions,
outcome-pinned decision-threshold versions, outcome/timepoint/evidence-body certainty assessments,
structured domain judgments, deterministic comparison/reveal history, human adjudication metadata,
and immutable Summary-of-Findings row snapshots. Composite foreign keys repeat Organization and
Review scope across outcomes, timepoints, analysis specifications/runs, framework/threshold
versions, assessors, correction chains, evidence locations, comparisons, and snapshots. Submitted
assessments and adjudicated comparisons are protected from mutation; corrections create successors.
The migration is linear after 20260812_0021 and supports full reverse removal.
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

Migration `20260815_0025` adds immutable, tenant- and Review-scoped policy versions, assignment-linked
screening proposal snapshots, reveal/access events, canonical-decision links, evaluation datasets and
cases, deterministic evaluation results and case results, and append-only error classifications. The
proposal link repeats protocol, criterion, citation, task, assignment, run, and AI proposal identity;
composite foreign keys prevent cross-organization and cross-Review links. Check constraints cover
modes, reference decisions and standards, task versions, metric policy, suggestions, confidence, hashes,
and error categories. ORM guards reject updates and deletes across the Phase 24 scientific history.

Evaluation datasets retain human-curated reference decisions separately from canonical screening
decisions and never replace Article, Study, or screening entities. Case-level results retain the exact
proposal and metric dimensions used for deterministic evaluation. The migration is linear after
`20260814_0024` and supports reverse removal of all Phase 24 tables.
