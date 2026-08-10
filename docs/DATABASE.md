# Database

PostgreSQL is the canonical store. SQLAlchemy 2 typed models define persistence mappings and Alembic owns every schema change.

Rules:

- Use database constraints for uniqueness, referential integrity, allowed ranges, and immutable identity where practical.
- Use UTC timezone-aware timestamps.
- Prefer UUID identifiers for externally exposed records.
- Preserve imported source records and merge links rather than destructively deleting duplicates.
- Avoid unbounded JSON as a substitute for modeled scientific data. JSON is appropriate for provider payload snapshots and evolving structured metadata with a stable envelope.
- Keep workflow, evidence, provenance, and audit tables distinct.
- Tests may use SQLite only for adapter-fast tests; PostgreSQL integration tests remain required for database-specific behavior.

The Phase 1 migration is intentionally empty: it establishes migration mechanics without adding throwaway schema before a domain is implemented.

Migration `20260810_0002` adds `users`, `organizations`, `memberships`, `local_credentials`, `reviews`, and `review_memberships`. Composite foreign keys prevent review owners, creators, assignees, and assigners from crossing organization boundaries. Normalized email/slug, non-empty names/titles, role values, membership uniqueness, and removal metadata are database constrained.

Membership removal is represented by `removed_at` and `removed_by_user_id`; authorization queries require `removed_at IS NULL`. Review queries always include `organization_id`, even when the review UUID is globally unique, to preserve non-enumeration behavior.
