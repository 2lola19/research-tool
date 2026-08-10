# ADR-004: Start as a Modular Monolith

- Status: Accepted
- Date: 2026-08-09

## Context

The product has many scientific domains but initially runs on one local machine. Premature service decomposition would multiply deployment and transaction complexity.

## Decision

Keep API/domain modules in one Python deployable while enforcing engine, repository, provider, workflow, and provenance boundaries. Isolate document parsing and statistical computation as external-service adapters where their runtimes justify separation.

## Consequences

Modules share a deployment but not arbitrary internals. Boundaries can be extracted when measured scale, reliability, or licensing needs warrant it.

