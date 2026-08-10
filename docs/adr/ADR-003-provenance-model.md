# ADR-003: Separate Scientific Provenance from Audit Logs

- Status: Accepted
- Date: 2026-08-09

## Context

Operational logs and CRUD audit rows cannot reconstruct evidence location, extraction method, model/prompt version, verification, or downstream analytical use.

## Decision

Model scientific provenance as structured records linked to scientific entities and evidence locations. Maintain append-only audit events separately for consequential application changes.

## Consequences

Scientific feature migrations must include provenance relationships in their definition of done. Logging is useful for diagnosis but never satisfies provenance requirements.

The first persisted implementation uses separate `prompt_versions`, `ai_runs`, `scientific_provenance`, and `audit_events` tables. Tenant/review composite constraints bind cross-table attribution, while ORM mutation guards and append-only repository protocols prevent application-level rewriting of ledger history.
