# ADR-021: Immutable structured reporting and reproducibility packages

## Status

Accepted 2026-08-13.

## Context

Phases 16–21 establish canonical protocol, search, screening, Study, extraction, Risk of Bias,
outcome, analysis, PRISMA, certainty, provenance, and audit records. Publication-oriented output
must make those records exchangeable without becoming a second scientific database. Reports also
need to distinguish scientific content identity from renderer/file identity, detect upstream
staleness, and avoid redistributing restricted documents or provider payloads.

## Decision

- `ReportSpecification` is an immutable, Review-scoped, versioned request containing report type,
  explicitly requested sections/formats, draft policy, and any explicit baseline-risk inputs.
- `ReportSnapshot` is immutable derived content. It stores the specification, canonical source
  references, source hashes, renderer version, and a deterministic scientific-content hash. It never
  replaces or duplicates protocol, screening, extraction, RoB, analysis, certainty, or PRISMA state.
- `ReportArtifact` stores exact JSON, HTML, XLSX, or ZIP bytes with a separate SHA-256 file checksum.
  Renderer metadata and archive timestamps are excluded from the scientific-content hash.
- Readiness is report-type-specific. A reproducibility package can be generated from structured
  provenance while a final Summary of Findings requires current evidence and certainty inputs.
  Explicit draft generation remains labelled and does not alter scientific readiness.
- Reports consume immutable PRISMA snapshots and existing export datasets. Statistical, PRISMA,
  Risk-of-Bias, and certainty calculations are never performed by a report renderer.
- Staleness hashes cover an allowlisted set of canonical scientific tables. Report artifacts,
  provenance written by report generation, and unrelated UI/export metadata are not upstream
  scientific inputs. Historical snapshots remain immutable and are marked stale at read time.
- Reproducibility ZIPs contain deterministic relative paths, a manifest, per-file SHA-256 checksums,
  and a package hash. Validation checks names, checksums, manifest schema, and package hash without
  database mutation. Full-text binaries, raw provider bytes, secrets, environment files, storage
  keys, and runtime files are excluded by default.
- Baseline-risk transformations are permitted only from an explicit persisted source/value/unit
  supplied by methodology. RR/OR transformation uses version `absolute-effect-1`; original relative
  effects remain unchanged. No baseline risk is inferred from pooled controls.
- Existing centralized authorization, audit events, and scientific provenance are required for
  report specification/snapshot generation and artifact retrieval.

## Consequences

Reports are reconstructable and publication-oriented while canonical Review state remains in its
existing domain tables. Structured JSON/HTML/XLSX and reproducibility ZIP output can be compared by
scientific hash even when file bytes differ due to renderer metadata. Redistribution safety is
explicit and conservative; licensed documents and provider payloads require a separately authorized
future policy. Mature prose authoring, PDF/DOCX, living-review automation, and AI generation remain
out of scope.

