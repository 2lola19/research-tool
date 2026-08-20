# Testing

The quality pyramid uses unit tests for deterministic domain logic, API tests for transport/error contracts, repository tests against PostgreSQL, workflow tests for transitions/retries/idempotency, and focused frontend unit/build tests.

Run backend checks:

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
.\.venv\Scripts\mypy.exe backend workers
.\.venv\Scripts\pytest.exe
```

Run frontend checks from `frontend/`:

```powershell
npm run lint
npm run typecheck
npm test
npm run build
```

Phase 2 includes negative tenant-isolation integration tests for cross-organization reads, writes, enumeration, identifier inference, invalid actor context, membership removal, role restrictions, ownership, and review assignment. The Alembic chain is also applied to a disposable SQLite database in the automated suite. PostgreSQL remains canonical and its database-specific execution gate is tracked as `ENVIRONMENT_BLOCKED` until the host Docker engine is available.

Review Projects adds tests for organization-unique metadata, archive/restore, member listing/removal, immediate project-access revocation, ownership transfer, and cross-tenant transfer rejection. Frontend tests assert that server-side review fetches always send both bearer identity and organization context.

Critical suites cover protocol immutability, audit append-only behavior, provenance completeness, workflow transitions, deterministic deduplication, and screening. Screening tests exercise blinded queues, immutable decisions, exclusion rationale, deterministic consensus/conflict outcomes, conflict adjudication, closure completeness, idempotent full-text progression, retained-versus-suppressed duplicate behavior, role restrictions, assignment ownership, and cross-tenant identifier non-enumeration.

Phase 10.5 tests exercise ordinary sequential allocation, scoped uniqueness, savepoint retry after a simulated concurrent winner, simulated concurrent workers, and rollback after exhausted retries. Phase 11 tests cover PDF signature and size validation, safe filenames, checksum duplicate rejection, unchanged object retrieval, tenant-scoped document access, parser fixture normalization and malformed output, processing failure state, warnings, evidence locations, approved-protocol full-text judgments, structured exclusion reasons, and viewer mutation denial. SQLite writer-lock limitations are not treated as PostgreSQL concurrency validation; the contention test uses a deterministic database-behavior simulation.

The PRISMA/export foundation tests database-derived record/report/Study distinctions, readiness
blockers, structured full-text exclusion reasons, immutable tenant-scoped snapshots, deterministic
byte rendering, CSV formula neutralization, valid XLSX archives, all four download formats,
manifests, checksums, prior-artifact preservation, role restrictions, tenant non-enumeration, and the
complete Alembic upgrade/downgrade chain. Deterministic effect calculations remain deferred.

Search Execution tests cover all structured source groups, strategy/translation and exact-query
retention, repeated execution history, terminal immutability, completed/partial/failed readiness,
provider/import reconciliation, file-import linkage, multiple discovery paths, pre-dedup PRISMA
counts, database/register versus other-method separation, stable JSON/XLSX documentation, raw
artifact checksum retrieval, cross-tenant/cross-review non-enumeration, role restrictions, and the
`20260811_0018` upgrade/downgrade chain.

Risk of Bias tests cover instrument normalization, domain/question order, instrument-defined choices,
deterministic suggestions, Study-design compatibility, independent assessor ownership and blindness,
agreement/conflict comparison, submitted-record immutability, current-revision comparison,
authorized adjudication, audit/provenance, and cross-tenant/cross-review non-enumeration. Study Family
tests cite protocol and results Documents in one Study and reject evidence linked only to another
Study. Export tests verify stable JSON/XLSX RoB sections, instrument hashes/versions, sheet ordering,
and `review-export-3`. Migration tests validate the complete `20260811_0019` SQLite upgrade and
downgrade chain; PostgreSQL-specific execution remains environment-blocked.

Outcome harmonization tests use hand-verifiable Decimal examples for RR, OR, RD, MD, sampling
variance/standard error, unit conversion, time normalization, direction reversal, invalid counts and
denominators, rounding, and zero/boundary events. Integration tests cover version history, verified
extraction linkage, explicit time anchors/windows, immutable mappings, derived provenance, candidate
readiness, duplicate-Study protection, cross-review selection rejection, role/tenant isolation,
deterministic `review-export-4` JSON/XLSX sections, and the full `20260811_0020` SQLite
upgrade/downgrade chain. PostgreSQL-specific execution remains environment-blocked.

Statistical synthesis tests isolate the native engine from HTTP/database code and use a documented
golden fixture with independently derived fixed-effect and DerSimonian-Laird results. Assertions use
explicit tolerances for pooled estimates, normal confidence intervals, model weights, Q, Q p-value,
I-squared, tau-squared/tau, log/back-transformation, prediction intervals, and leave-one-out runs.
Edge tests cover one/two Studies, duplicate Study identity, non-positive/near-zero/large variance,
extreme effects and weights, missing variance, invalid confidence/model/transform combinations,
zero/double-zero policies, adjusted/population mismatch, unsupported multi-arm/cluster/crossover
dependencies, and stale inputs. The synthetic integration review flows from verified extraction
through harmonization/readiness into a persisted specification, set, run, export, forest artifact,
audit/provenance, and tenant/direct-ID isolation. Migration tests cover `20260812_0021` upgrade and
full downgrade; PostgreSQL-specific execution remains environment-blocked.

## Phase 22 reporting and reproducibility foundation

Phase 22 adds a deterministic reporting layer over canonical Review state. Versioned `ReportSpecification`
records request explicit report types/sections/formats; immutable `ReportSnapshot` records source references,
source hashes, renderer version, and scientific-content hash; `ReportArtifact` stores exact JSON, HTML, XLSX,
and reproducibility-ZIP bytes with independent file checksums. Reporting readiness is report-type-specific and
supports explicitly labelled drafts. Report generation never recalculates PRISMA, Risk of Bias, certainty, or
meta-analysis results.

The reproducibility package validator checks deterministic relative paths, manifest schema, per-file SHA-256
checksums, package hash, and source identity without database mutation. Structured scientific records are
included; full-text binaries, raw provider bytes, secrets, environment files, storage keys, and runtime files
are excluded by default. Scientific staleness hashes cover canonical upstream scientific tables only; generated
provenance, exports, UI metadata, and report artifacts do not make an otherwise unchanged report stale.

A dedicated reporting workspace supports readiness, report type, package preview, generation, current/stale
status, checksum metadata, and authenticated downloads. Phase 22 is not a mature manuscript authoring system;
AI writing, living-review automation, PDF/DOCX, restricted document redistribution, and provider execution remain
deferred.

## Phase 23 AI provider foundation

Phase 23 adds a provider-neutral, task-oriented AI execution substrate with immutable model and prompt versions, bounded run/attempt lifecycles, input/prompt/response hashes, structured validation, append-only proposals and human decisions, usage/cost metadata, policy ceilings, tenant scoping, and accepted-AI provenance in reporting packages. The only executable workflow is an offline deterministic search-query draft proposal; it never mutates SearchStrategyVersion or another canonical scientific domain. Real providers, credentials, production scientific AI tasks, autonomous tools, and auto-accept remain deferred. AI provenance supports reconstruction of what was requested, returned, validated, and accepted but does not claim bit-for-bit model reproducibility.

## Phase 24 governed AI screening assistance

Unit tests cover explicit disagreement classes, conservative/strict/coverage metric behavior, Wilson
intervals, calibration and threshold output, deterministic mock task contracts, and evidence/criterion
validation. Integration coverage exercises approved-protocol pinning, policy modes, assignment ownership,
blinded withholding, post-decision reveal, access/audit/provenance links, deterministic evaluation,
case-result reads, append-only error classification, and cross-tenant direct-ID non-enumeration.
Migration checks cover the nine Phase 24 tables and full reverse removal. Full-text, live-provider,
PostgreSQL, and Docker execution remain intentionally outside this phase.

### Phase 23 validation (2026-08-14)

- Backend: Ruff and format PASS; strict mypy PASS (185 source files); pytest 209 PASS; coverage 92.98% (threshold 85%).
- Migration: full SQLite upgrade through `20260814_0024` and downgrade to base PASS.
- Frontend: ESLint PASS; TypeScript PASS; Vitest 9 PASS; Next.js 16.3 production build PASS.
- Repository: git diff --check PASS; focused secret audit PASS.
- Live paid AI providers and PostgreSQL remain intentionally unexecuted/environment-blocked.

## Phase 25 AI full-text screening validation

- Golden tests cover bounded/scoped chunks, omitted manifests, Unicode/whitespace normalization,
  exact quotes and limits, page/section checks, foreign document/version/chunk rejection, fabricated
  criteria, structured abstention, prompt injection, mock failures, and human acceptance delegation.
- Metric tests define retained reports as positive and FN as AI EXCLUDE/reference RETAIN; they verify
  sensitivity/FNR, preserve MAYBE/ABSTAIN, score wrong criteria separately, measure evidence/sections,
  and expose high-risk disagreements and simulation-only thresholds.
- API integration covers readiness, document/parser pins, proposal generation without a decision,
  BLINDED_AI assignment/direct-ID withholding, generic AI endpoint closure, pinning of the original
  assistance mode across later policy changes, post-decision reveal, tenant non-enumeration, unchanged
  PRISMA counts, evaluation, audit links, document replacement staleness, and protocol staleness.
- SQLite upgrades through `20260816_0026` and downgrades fully. Normal Windows pytest Temp creation is
  environment-blocked in the unelevated sandbox; pre-created repository-local direct runners are the
  safe workaround and do not change ACLs. The exact full pytest command records 118 passing tests and
  108 Temp-fixture setup errors; its 64% partial coverage is not a valid gate result. Full
  pytest/coverage, Vitest (`spawn EPERM` while loading
  Vite config), and the final Next.js post-compilation worker (`spawn EPERM`) require manual host
  validation; Ruff, formatting, strict mypy, ESLint, and TypeScript pass in the sandbox.
## Phase 26 extraction safety coverage

Focused unit and integration coverage exercises exact typed/schema validation, missingness, evidence
quotes and numeric support, fabricated chunks/documents/pages/values, unsupported fields, conflicts,
supplement/table limitations, prompt injection, immutable repeated proposals, schema/document
staleness, bounded failure-isolated batches, direct-ID blinding and reveal, tenant/review boundaries,
human accept/edit provenance through manual extraction, dual-extractor separation, unchanged PRISMA,
downstream isolation, deterministic evaluation, hallucination/grounding queues, calibration, and
hypothetical-only thresholds. Migration testing performs a full SQLite upgrade and downgrade.

## Phase 27 Risk-of-Bias AI coverage

Unit tests cover exact instrument choices, one-answer-per-question completeness, valid abstention,
wrong-answer/source-block/chunk/page/section/quote rejection, declarative domain/overall derivation,
dangerous-underestimation metrics, descriptive calibration status, prompt safety, and deterministic
fixtures. Integration tests cover approved-version/readiness gates, Study Family parser inputs,
BLINDED_AI withholding and generic-route closure, ASSISTED question dispositions, canonical human
assessment immutability, post-submission reveal, evaluation abstention/high-risk records, audit links,
and tenant/assessor direct-ID non-enumeration. The `20260818_0028` migration upgrades and downgrades
fully on SQLite. PostgreSQL and live provider execution remain production-phase gates.

## Phase 28 outcome assistance validation

Focused unit coverage verifies identity pinning, exact evidence grounding, fabricated chunk and
quote rejection, unsupported conversion/calculation rejection, allowed-reference filtering,
reported-effect numeric/variance safeguards, descriptive evaluation metrics, and governed task
registration. Integration coverage verifies generic-route closure, Review-scoped proposal reads,
and foreign-tenant non-enumeration. The `20260818_0029` migration was manually upgraded and
downgraded through the base SQLite schema.

Targeted Ruff, format, strict mypy, frontend lint, and TypeScript pass. The Windows pytest temp-root
cleanup remains environment-blocked for the dedicated integration shard; broad frontend lint also
timed out without output while the changed frontend files pass direct ESLint. Vitest/build and live
PostgreSQL/provider execution remain production-phase gates.

## Phase 29 certainty assistance validation

Focused unit coverage verifies framework identity, allowed domain direction/judgment/magnitude,
exact chunk/page/section/source-block/quote grounding, abstention, forbidden final/threshold
fields, descriptive metrics, and deterministic mock fixtures. Integration coverage verifies
Review-scoped proposal reads, viewer authorization, policy/readiness boundaries, and foreign-ID
non-enumeration. Migration coverage upgrades and downgrades the seven certainty-assistance tables.

Backend Ruff, format, strict mypy, import, focused unit/integration, and migration checks pass.
Frontend ESLint, TypeScript, Vitest, and production build pass for the certainty workspace. Live
PostgreSQL, Docker, parser, external storage, and paid/live provider execution remain deferred.

## Phase 30 read-only copilot coverage

Unit coverage verifies deterministic bounded context hashing, workflow payload redaction, exact
citation validation, fabricated-citation rejection, explicit abstention reasons, and unsupported
action rejection. Integration coverage verifies viewer denial, foreign-Review non-enumeration,
generic AI route closure, policy-before-query enforcement, successful deterministic abstention,
query history, and context hashes. Migration coverage upgrades and downgrades the linear SQLite
chain through `20260819_0031`.

Repository Ruff, formatting, strict mypy, compile/import, and the focused copilot unit/integration
and migration checks pass. Frontend lint/typecheck/test/build remain required phase gates; live
PostgreSQL, Docker, external providers, and arbitrary retrieval remain deferred.

## Phase 31 durable workflow execution coverage

Unit coverage verifies exact handler signatures, bounded payload validation, payload redaction, and
the deterministic local runner. Integration coverage verifies worker registration, capacity-bounded
claiming, lease heartbeat, completion, redacted claim responses, append-only attempt event order,
failure/requeue behavior, Review/tenant boundaries, and attempt-history token withholding. Migration
coverage upgrades and downgrades the SQLite chain through `20260819_0032`. Existing workflow
transition/idempotency and worker lifecycle tests continue to pass. PostgreSQL lock contention,
multi-process crash timing, live provider handlers, and production worker orchestration remain later
environment or Phase 32 gates.

## Phase 32 recovery coverage

Unit coverage verifies retry classification/backoff bounds, immutable definition hashes, and stale
definition rejection. Integration coverage verifies permanent-failure dead-lettering, normalized
step checkpoints, idempotent manual recovery with explicit added budget, idempotent pause resume,
read-only reconciliation drift diagnostics, and tenant boundaries. Migration coverage upgrades and
downgrades the linear SQLite chain through `20260819_0033`.

Required follow-on coverage includes PostgreSQL concurrent claim/recovery timing and live worker
crash/timeout behavior when that infrastructure is available. No environment timeout is recorded as
a test pass.

## Phase 33 scholarly provider coverage

Unit coverage exercises the provider-neutral OpenAlex, PubMed, Europe PMC, and fixture adapters
with deterministic response fixtures: normalization, abstract/author/identifier mapping, bounded
pagination, rate-limit retry/backoff, timeout/error taxonomy, raw-response limits, HTTPS host
allowlists, redirect rejection, secret-safe fingerprints, and polite user-agent validation. No test
calls a live scholarly API.

Integration coverage verifies explicit opt-in, fixture execution through the existing
SearchExecution/citation/raw-artifact/provenance services, append-only provider-attempt reads, and
Review/tenant authorization. Migration coverage upgrades and downgrades the linear SQLite chain
through `20260819_0034`. Live provider credentials, network behavior, PostgreSQL concurrency, and
external service etiquette remain deployment gates.

## Phase 34 production AI provider coverage

Unit coverage exercises OpenAI, Anthropic, and Gemini response envelopes with fake transports,
provider-specific usage normalization, structured JSON rejection, status/error classification,
response bounds, model allowlist behavior, explicit live opt-in, and secret-safe error text.
Governance unit coverage exercises exact pricing/unknown-cost behavior, monthly token/cost budgets,
and bounded provider/model circuit opening. Existing AI unit coverage remains green, and the AI
foundation integration test covers the Review-scoped usage endpoint and policy response. No live
provider call or credential is used. The combined AI integration shard timed out without output
after 300 seconds and is recorded as `ENVIRONMENT_BLOCKED`, not as a pass.

## Phase 35 document processing and storage coverage

Unit coverage verifies opaque-key/path traversal rejection, atomic local storage, verified
put/get/head/list behavior, corruption detection, the vendor-neutral S3 adapter boundary,
canonical parser limits, deterministic chunk-manifest hashes, malformed GROBID fixture handling,
and HTTPS/private-host retrieval policy. Integration coverage verifies upload-ID/key alignment,
restricted content authorization, verified content retrieval, parser-run history, corruption and
repair retry transitions, reconciliation read-only behavior, and foreign-tenant non-enumeration.

Migration coverage upgrades and downgrades the SQLite chain through `20260819_0036` and asserts
the new processing-run metadata columns. No live GROBID, S3 service, malware scanner, external
retrieval, or PostgreSQL concurrency claim is made. Those remain deployment/environment gates.

## Phase 36 collaboration and operational UX coverage

Backend integration coverage verifies the ordered Review-scoped screening-round index and foreign-
organization not-found behavior alongside existing blinded queue, decision, conflict, and
progression tests. Frontend API tests verify that bearer and organization headers are sent, a
reviewer queue can load while membership/QC/workflow sections are explicitly restricted, and no
restricted response is treated as ready data. ESLint, TypeScript, Vitest (10 tests), and the
Next.js production build pass. The focused tenant test passes with `--no-cov`; running that single
test through the repository's default coverage gate is not a full-suite coverage measurement and
fails the 85% threshold by design. The full pytest command emitted no output and timed out after
424 seconds; exact descendants were inspected and terminated safely, so this is recorded as an
environment limitation rather than a test pass.

## Phase 37 deployment and operational coverage

Unit/API coverage verifies production configuration rejection for local auth/SQLite/debug or
insecure CORS, migration-head readiness, correlation-ID and traceparent bounds, redacted metrics,
security headers, authentication `429` behavior, and worker disposal/poll shutdown. Existing
Alembic coverage upgrades the full linear SQLite chain through `20260819_0036` and downgrades to
base. `docker compose config`, PostgreSQL migration/constraint/concurrency checks, image and
dependency scanners, TLS/proxy behavior, OIDC, external object storage/malware scanning, and
backup/restore remain environment/deployment gates and must be recorded as blocked rather than
claimed as passes when unavailable.

## Deployment-readiness PostgreSQL migration correction

The first disposable PostgreSQL upgrade exposed real portability defects in migrations
`20260819_0033` and `20260819_0035`: unconditional batch rewrites attempted to drop unique
constraints still referenced by tenant-scoped foreign keys. Both migrations now take direct
PostgreSQL paths for column/check-constraint changes and retain SQLite batch paths. The focused
SQLite migration upgrade/downgrade test remains required; an optional
`POSTGRES_TEST_DATABASE_URL` integration test runs the complete Alembic upgrade against an explicitly
disposable PostgreSQL target. A live disposable upgrade is required evidence for this deployment
program and is not replaced by the SQLite result.

The PostgreSQL deployment check also requires Alembic's target metadata to import the reporting
records; metadata omissions are treated as migration drift. Migration `20260819_0036` is covered
by the same full-chain upgrade/downgrade test.

Deployment container validation also verifies that the worker does not inherit the API HTTP
healthcheck: Compose uses a process-level worker check, while the persisted worker heartbeat remains
the database-backed operational signal.

The frontend container healthcheck uses explicit IPv4 loopback so a healthy server is not falsely
reported unavailable by image-local `localhost` resolution.

## SG-002 malware scanner coverage

Malware coverage uses a deterministic fixture adapter for repository tests and the provider-neutral
ClamAV TCP adapter for protocol tests. It covers clean and standard EICAR live detection, bounded
timeouts, unavailable endpoints, scanner errors, append-only retry history, exact content-hash
eligibility, infected-content blocking before parser/canonical writes, tenant and authorization
boundaries, generic redacted responses, migration metadata, and scanner readiness. The disposable
ClamAV service is official `clamav/clamav:1.4.6`, pinned by Compose digest, with no host port and
its image scanned by Trivy for HIGH/CRITICAL vulnerabilities. EICAR is generated only in disposable
runtime memory and is never committed.
