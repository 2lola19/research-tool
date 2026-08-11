# ADR-015: Derive PRISMA and preserve reproducible export artifacts

## Status

Accepted for the deterministic PRISMA and export foundation.

## Context

Manual flow counters drift from the scientific records they claim to summarize. Export files can
also change silently when query ordering, spreadsheet generation, or source data changes. A final
report must distinguish imported records, publication reports (Articles), and underlying Studies,
and it must not imply completeness while screening or family assignment remains unresolved.

## Decision

- Compute PRISMA counters from citation-source, deduplication, screening, retrieval, full-text, and
  Study-family records. Do not persist editable counters.
- Persist immutable PRISMA snapshots containing the algorithm version, counts, readiness blockers,
  and deterministically ordered source references.
- Treat one Article as one report and one Study as one investigation. Citation source rows remain
  records; confirmed duplicate suppression never deletes them.
- Create CSV, XLSX, JSON, and RIS bytes with deterministic ordering and no LLM involvement.
- Store each export artifact transactionally with its exact bytes, manifest, SHA-256 checksum,
  source PRISMA snapshot, creator, format, media type, and size. Previous artifacts are append-only.
- Mark incomplete reviews as draft through explicit readiness blockers; export remains available so
  work-in-progress can be exchanged without being represented as a final PRISMA report.

## Consequences

Artifact storage in PostgreSQL is acceptable for this bounded foundation and prevents partial local
files after failed transactions. Large exports may later move behind `ObjectStorageProvider`, but a
move must retain immutable bytes and checksums. Spreadsheet output uses deterministic standard-library
OOXML generation, so this milestone adds no paid provider or new runtime dependency.
