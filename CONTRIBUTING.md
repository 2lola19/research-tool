# Contributing

Use small, coherent changes that preserve the architecture and scientific invariants.

1. Read `AGENTS.md`, `ARCHITECTURE.md`, and relevant ADRs.
2. Create or update a migration for persistent-model changes.
3. Add tests before declaring behavior complete.
4. Run `scripts/check.ps1`.
5. Update documentation and implementation ledgers.
6. Commit without secrets or local runtime data.

Commit messages should describe an outcome, for example `feat(protocol): add immutable protocol versions` or `test(tenancy): enforce organization-scoped review access`.

