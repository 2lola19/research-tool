# ADR-008: Keep Search Intent Canonical and Translation Deterministic

- Status: Accepted
- Date: 2026-08-10

## Context

Database-specific query syntax differs and evolves. Treating a PubMed or vendor query as the canonical strategy would couple scientific intent to one provider and make translation changes difficult to reconstruct.

## Decision

Store search intent as immutable, structured concept groups and terms with explicit field semantics. Bind every strategy version to an approved protocol version. Produce provider queries through pure, versioned translators and persist the exact output.

The first translators are PubMed and an offline fixture format. Translation performs no network call. Replaying the same strategy/provider/translator version returns the existing translation.

## Consequences

- Provider syntax is a derived artifact, not canonical scientific state.
- Translation behavior is unit-testable without credentials or provider availability.
- A translator change requires a new translator version and preserves older output.
- Live search execution and raw result capture remain separate Citation Import concerns.
