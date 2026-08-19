# Phase 30 Report — Read-Only Evidence-Aware Review Copilot

## Outcome

Phase 30 implements the read-only `REVIEW_COPILOT` task over bounded canonical project metadata.
The explicit task registry covers project status, workflow blockers, and provenance navigation.
The deterministic context assembler includes only bounded Review metadata, PRISMA summary/readiness,
workflow run/job state metadata, derived blockers, and source-reference counts. Workflow payloads,
arbitrary retrieval, provider tools, scientific calculations, manuscript generation, and canonical
workflow/scientific writes are excluded.

Non-abstaining answers must cite exact supplied citation IDs. Deterministic validation rejects
fabricated citations, oversized answers, unexplained abstention, invalid confidence, and unsupported
actions. Query reads recompute the current context hash and label historical results stale when
canonical Review/PRISMA/workflow context changes.

## Implementation surface

- Added task definition, prompt contract, mock abstention fixture, governed generic-route closure,
  bounded context/citation validator, append-only persistence, policy service, and AI execution
  integration.
- Added tenant/Review-scoped policy/query API routes, workflow repository read-list methods, migration
  `20260819_0031`, and importable SQLAlchemy mappings.
- Added frontend policy/query actions, typed copilot API access, read-only activity history, citation
  and stale-context display, and explicit policy configuration.
- Added ADR-029 and updated AI architecture, API, database, domain, provenance, security, testing,
  implementation-status, roadmap, open-source, and autonomous-build decision documentation.

## Scientific, security, and provenance review

- PASS — the copilot is not a Study, Article, evidence value, scientific judgment, report artifact,
  or workflow transition.
- PASS — AI execution is bounded, provider-neutral, no-tools, secret-screened, and framed against
  untrusted query/source data.
- PASS — all policy/query reads and writes are organization/Review scoped; foreign direct IDs fail
  closed; workflow payloads are not in the model context.
- PASS — query snapshots retain context hash, citations, AI run/proposal identity, validation, and
  append-only audit metadata; no canonical scientific write is performed.

## Validation

- PASS — repository `ruff check .`.
- PASS — repository `ruff format --check .`.
- PASS — `mypy backend workers` (217 source files).
- PASS — `python -m compileall -q backend workers tests`.
- PASS — `tests/unit/test_ai_review_copilot.py` (3 tests, `--no-cov`).
- PASS — `tests/integration/test_ai_copilot.py` (4 tests, including stale-context detection).
- PASS — `tests/integration/test_migrations.py` through `20260819_0031` (SQLite upgrade/downgrade).
- PASS — frontend `npm run lint`, `npm run typecheck`, `npm test` (9 tests), and `npm run build`.
- ENVIRONMENT_BLOCKED — full `pytest -q` produced no output for 364 seconds under the Windows
  process environment. Exact pytest processes were verified and terminated; no assertion result is
  claimed.
- PASS — secret/credential and generated-artifact audits found no intended-file violations.

## Checkpoint

Implementation is complete and the required local checkpoint checklist is ready. The Phase 30
implementation commit SHA and final metadata checkpoint SHA will be recorded here after local Git
verification. No GitHub operation is authorized or performed.
