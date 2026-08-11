# ADR-014: Study-level provenance-first extraction and verification

## Status

Accepted for Phases 12–15.

## Context

One investigation may produce several Articles and Documents. Extraction therefore cannot use Article identity as Study identity, and a schema or extracted value must not change meaning silently after work begins. Dual extraction must preserve disagreements for human review rather than overwrite one run with another.

## Decision

- `Study` is a stable Review-scoped identity; `StudyArticleLink` is a non-destructive, provenance-bearing relationship to Articles.
- Extraction is pinned to immutable schema versions. Field definitions are typed and ordered, while scientific missingness is explicit.
- Manual values use typed database columns and must identify a linked Article or Document evidence location. The existing Provenance Ledger and Audit Ledger remain the only provenance systems.
- Verification canonicalizes deterministic types. Numeric, categorical, boolean, date, and exact normalized text comparisons may match; semantic text equivalence is not inferred. Evidence disagreement is a conflict.
- Conflicts retain both original value/evidence snapshots. Authorized human adjudication updates only conflict and verification state and appends provenance/audit records.
- Provider-backed or AI extraction will enter the same run/value/verification path later; no provider is integrated by this ADR.

## Consequences

The model supports multiple publication sources and resumable manual work without destructive merges. Schema, value, and conflict tables are larger than a single JSON blob but keep scientific types, tenant constraints, and history queryable. Mature extraction automation, templates, and statistical analysis remain deferred.
