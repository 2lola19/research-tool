# ADR-016: Search execution and identification-source provenance

## Status

Accepted 2026-08-11.

## Context

An immutable `SearchStrategyVersion` describes intended search design, but it cannot prove what a
provider actually received or which imported records it returned. PRISMA identification counts
must distinguish databases/registers from other methods without inferring meaning from source
names. Repeated and updated searches must retain every discovery path.

## Decision

- `IdentificationSource` is a Review-scoped, structured identity with an explicit classification,
  provider, and optional platform. Names never determine classification.
- `SearchExecution` is an append-only scientific record of the source, optional strategy and
  translation, exact query, structured restrictions, acquisition method, execution timestamp, and
  software version. Repeated searches create new records.
- Status changes are append-only `SearchExecutionEvent` rows. Terminal executions cannot be
  changed. A correction creates a new execution with `supersedes_execution_id`; routine search
  updates do not supersede earlier searches.
- `SearchExecutionCitationLink` retains every execution-to-imported-source-record discovery path.
  Article deduplication never removes these links.
- Optional raw response artifacts use the existing object-storage port and retain filename, media
  type, byte size, SHA-256, creator, and tenant-scoped opaque storage key.
- Provider-reported result count is a reproducibility cross-check, not a deduplicated count.

## PRISMA counting rule

Only active, completed executions contribute. “Active” excludes an execution explicitly corrected
by a newer execution; ordinary repeated/update executions all remain active. Counts are the number
of distinct linked `CitationSourceRecord` IDs in each structured PRISMA group:

- `BIBLIOGRAPHIC_DATABASE`, `TRIAL_REGISTER`, and `OTHER_REGISTER` contribute to databases and
  registers.
- all other classifications contribute to other methods.

A source record linked more than once within one group counts once. Separate source records for the
same publication remain separate at identification, so deduplication occurs only downstream. A
record linked across both groups is excluded from both counters and creates a readiness blocker.
Completed provider totals must match linked source-record counts for final readiness. This prevents
API/file-import double counting and detects incomplete ingestion.

## Consequences

Search documentation is reproducible and living-review compatible without implementing live
provider APIs. Correcting a terminal execution requires an explicit historical successor. The
export schema advances to `review-export-2`; JSON and XLSX include deterministic execution records
and status histories. PostgreSQL-specific validation remains environment-blocked; SQLite validates
the complete reversible migration chain.
