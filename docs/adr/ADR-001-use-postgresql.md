# ADR-001: Use PostgreSQL as the Canonical Store

- Status: Accepted
- Date: 2026-08-09

## Context

The platform requires normalized relational scientific records, strong constraints, transactionality, append-only history, tenant scoping, and future vector/search extensions.

## Decision

Use PostgreSQL with SQLAlchemy 2 and Alembic. SQLite is allowed only for fast tests that do not claim PostgreSQL compatibility.

## Consequences

Local development requires PostgreSQL (provided by Docker Compose). Database-specific repository tests must run against PostgreSQL before related features are complete.

