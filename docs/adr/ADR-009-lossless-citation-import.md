# ADR-009: Preserve Citation Imports Before Normalization and Deduplication

- Status: Accepted
- Date: 2026-08-10

## Context

Citation exports are imperfect and provider-specific. Destructively normalizing an upload or merging records during import would erase evidence needed to reproduce counts, diagnose parser behavior, and review duplicate decisions.

## Decision

Persist every import batch's exact text, format, name, and SHA-256 hash. Parse RIS, BibTeX, and CSV deterministically into one immutable source record and one Article per citation. Normalize common identifiers into Article fields but retain source metadata unchanged.

The same format/content hash is idempotent within a review. Import never merges records, even when DOI or PMID matches. Article remains a publication/citation entity and is never treated as Study.

## Consequences

- Import counts and raw inputs are reconstructable.
- Parser changes require an explicit version/provenance change rather than silent reinterpretation.
- Duplicate Articles temporarily coexist and are resolved by the reviewable deduplication domain.
- Very large uploads will eventually move through object storage/worker streaming; the local API currently enforces a bounded payload.
