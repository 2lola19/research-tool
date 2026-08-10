# ADR-002: Defer Temporal Behind an Orchestration Port

- Status: Accepted
- Date: 2026-08-09

## Context

Durable workflows, retries, checkpoints, and long-running work strongly fit Temporal. Requiring Temporal during the foundation milestone adds operational complexity before concrete workflow commands and compatibility rules exist.

## Decision

Define a vendor-neutral orchestrator contract now. Implement a small persisted local adapter in Phase 4, evaluate Temporal against its required semantics, and keep engines free of orchestration SDK imports.

## Consequences

The worker process is initially a lifecycle shell. Workflow identifiers, task versions, and idempotency keys are present from the first contract. Adopting Temporal later does not change application or engine interfaces.

