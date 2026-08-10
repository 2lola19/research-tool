# ADR-012: Database-coordinated sequential allocation

## Status

Accepted

## Context

Protocol versions, search strategy versions, prompt versions, screening-round
sequences, and workflow event sequences are scoped human-facing numbers. A
plain `MAX(value) + 1` followed by an insert can produce duplicate values when
multiple workers allocate within the same scope.

## Decision

Keep the scoped sequential numbers and their database uniqueness constraints.
Allocation reads the current maximum and inserts the candidate inside a
transaction savepoint. A uniqueness conflict rolls back only that savepoint,
re-reads the maximum, and retries a bounded number of times. The database
constraint is the coordination mechanism across processes and future workers;
no application-wide mutex is used.

## Consequences

- Successful allocations remain deterministic and human-readable within each
  organization/review or job scope.
- Failed attempts do not leave duplicate rows or invalidate the caller's outer
  transaction.
- Exhausted retries surface the database integrity error for the caller to
  handle; callers must not commit a partially completed domain operation.
- PostgreSQL is the production concurrency target. SQLite tests cover the
  transaction/savepoint behavior and simulated contention, but do not replace
  PostgreSQL validation.
