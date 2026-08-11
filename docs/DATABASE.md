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
