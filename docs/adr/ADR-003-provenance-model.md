# ADR-003: Separate Scientific Provenance from Audit Logs

- Status: Accepted
- Date: 2026-08-09

## Context

Operational logs and CRUD audit rows cannot reconstruct evidence location, extraction method, model/prompt version, verification, or downstream analytical use.

## Decision

Model scientific provenance as structured records linked to scientific entities and evidence locations. Maintain append-only audit events separately for consequential application changes.

## Consequences

Scientific feature migrations must include provenance relationships in their definition of done. Logging is useful for diagnosis but never satisfies provenance requirements.

