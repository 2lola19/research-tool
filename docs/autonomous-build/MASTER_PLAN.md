# Research Tool V1 Completion — Master Plan

Status: definitive plan; Phase 27 checkpointed at `995c5af`; Phase 28 checkpointed locally at
`f475619`; Phase 29 checkpointed locally at `df0a74f`; Phase 30 checkpointed locally at
`c59a340`; Phase 31 checkpointed locally at `65de1a9`; Phase 32 is next

## Reconciled baseline and sequencing

Read-only inspection confirmed a clean `master` at `ff5e1bb feat: add governed AI structured
extraction assistance`. Phases 1–26 are represented in the implementation and status documents.
The provisional 27–38 envelope is retained, with the following repository-specific refinements:

- Phase 27 reuses the existing declarative Risk-of-Bias engine; it adds no second RoB substrate.
- Phases 28–29 add governed projections over the existing outcome and certainty services, not AI
  replacements for harmonization, statistics, or certainty judgment.
- Phase 30 is a read-only evidence-aware copilot with explicit citations and no canonical writes.
- Phase 31 adds durable job persistence/claiming and worker execution behind the existing workflow
  contracts; Phase 32 adds resumability, retry, recovery, and operational reconciliation.
- Phases 33–35 add provider/storage/parser adapters and hardening with offline deterministic mocks.
  Live external services and paid providers remain disabled unless separately authorized.
- Phase 37 and the final gate document PostgreSQL, Docker, backup, observability, and security
  checks honestly; lack of live infrastructure is an environment limitation, not a false pass.

## Global laws and completion policy

- Canonical scientific state remains human-authored or produced by an existing deterministic engine.
- AI output is an immutable, bounded, evidence-grounded proposal. It cannot silently mutate
  scientific state, adjudicate disagreement, satisfy independent review, fabricate evidence,
  invent thresholds, or recalculate immutable statistical results.
- Workflow state, scientific data, provenance, audit, AI execution, and operational jobs remain
  separate models and tables.
- Every tenant-owned query and mutation is scoped by organization and Review access, with direct-ID
  non-enumeration and composite tenant/review integrity where persistence is added.
- Existing immutable versions/records are never rewritten. Corrections create successors or
  append-only events. Approved protocol, instrument, framework, prompt, model, and task versions
  are immutable.
- Scientific writes carry provenance and audit records. Accepted AI suggestions enter canonical
  services only through explicit human actions, with the AI run/proposal chain retained.
- No paid provider, production credential, GitHub push, destructive Git operation, ACL change,
  Docker/WSL troubleshooting, or production mutation is part of autonomous implementation.
- Each phase requires focused tests, scientific/security/tenant/provenance review, documentation,
  a phase report, and a truthful local Git checkpoint when writable.

## Local Git checkpoint autonomy

The autonomous build runs with full local filesystem access. After a phase is
implementation-complete and its required validation, scientific, security, tenant, and provenance
reviews are complete, Codex may create a local Git checkpoint. GitHub remains out of scope: no
push, force-push, release publication, repository-setting change, remote change, branch/tag
deletion, history rewrite, or operation on another repository is authorized.

Permitted local operations include `git status`, `git diff`, `git diff --check`, `git add` for
intended phase files, staged-diff inspection, local `git commit`, and read-only `git log`/`git show`
inspection required to verify the checkpoint. Before every commit, Codex must confirm phase
completion and required reviews, record every required gate as `PASS` or truthfully as
`ENVIRONMENT_BLOCKED`, run `git status`, inspect the unstaged diff, run `git diff --check`, audit
for secrets and credentials, exclude unrelated files/temp directories/caches/generated runtime
artifacts/host files, stage only intended phase files, inspect staged stat and content, run
`git diff --cached --check`, commit with one truthful phase-specific message, verify the commit
and resulting worktree, and record the SHA in `EXECUTION_STATE.json` and the phase report before
continuing automatically.

Codex must never use `git reset --hard`, `git clean`, broad `git restore`, ACL or `.git`
permission changes, `git init`, repository recreation, global Git configuration changes, or
history-rewriting operations. A per-command safe-directory option may be used when Git reports
ownership ambiguity; it must not be persisted globally.

The current full-access environment means ordinary local commits are expected. A historical
`.git/index.lock` sandbox failure is not a stop condition: attempt the normal validated checkpoint
once. If Git mutation actually fails, diagnose non-destructively, check whether another Git process
is active, do not delete a lock blindly or perform ACL surgery, preserve all work, set
`commit_pending: true` and `checkpoint_status: CHECKPOINT_PENDING`, record `LOCAL_COMMIT_PENDING`,
and stop only at that durable checkpoint for the minimum manual intervention.

## Cost-aware model policy

Use the currently selected model for normal implementation. Do not stop merely because another
model may be stronger, and do not switch models autonomously. Escalate only when a genuinely
unresolved scientific, security, migration, or architectural issue cannot be resolved
confidently. If escalation is required, preserve all work, update `EXECUTION_STATE.json`, set
`status: MODEL_ESCALATION_RECOMMENDED`, explain the exact unresolved issue, and stop at a durable
checkpoint.

## Shared phase definition of done

For every phase, the implementation must have focused unit/integration tests, relevant migration
upgrade/downgrade coverage, tenant and authorization checks, immutable/provenance/audit checks,
updated domain/database/API/security/AI documentation as applicable, a validation-log entry, a
phase report, and no unresolved critical/high scientific or security finding. `PASS`,
`ENVIRONMENT_BLOCKED`, and `DEFERRED` are recorded separately. A blocked gate is never represented
as a pass.

## Phase 27 — Governed AI Risk-of-Bias Assistance

Objective: provide bounded, evidence-grounded signalling-answer proposals against the exact
approved `RiskOfBiasInstrumentVersion`, while keeping human assessments, deterministic domain
rules, comparison, and adjudication authoritative.

Dependencies: Phases 18 and 23–26; existing `RiskOfBiasService`, document evidence locations,
Study Family links, AI execution/proposal ledgers, and `MockAIProvider`.

Scope: immutable RoB policy and assignment-scoped proposal links; exact Review/Study/Study Family,
instrument/version, domain/question choices and rules, Article/Document/processing/parser/chunk
input snapshots and hashes; deterministic output/evidence validation; OFF/BLINDED_AI/ASSISTED
disclosure; human review/reveal events; canonical acceptance only through existing RoB answer and
domain services; structured evaluation with agreement/confusion, grounding, abstention, coverage,
calibration description, domain error analysis, and dangerous-underestimation queue.

Non-goals: complete RoB 2/ROBINS-I or another published instrument, an AI assessor, autonomous
domain/overall judgment, AI adjudication, automatic submission, cross-Study evidence, OCR, live
providers, or replacement of declarative RoB rules.

Architecture: add a RoB-specific advisory projection over `AIOutputProposal` and the existing RoB
service. AI may propose only allowed signalling answers plus evidence and abstention; domain and
overall suggestions are computed by the existing deterministic rule functions from validated
answers. A valid proposal is never a `RiskOfBiasAssessment`.

Scientific/security/provenance requirements: pin all scientific identities and hashes; validate
evidence through Document → Article → active Study Family → Study; withhold every proposal field
through assignment and direct-ID routes in BLINDED_AI; keep the two human assessors independent;
record task/model/prompt/run/input/validation and human disposition; reject stale proposals.

Migration/API/frontend: add a linear migration for policy, proposal/source/evidence/access/link,
evaluation/reference/case-result/error tables with composite tenant/review constraints; add
`/api/v1/ai/risk-of-bias` policy/readiness/proposal/reveal/field-review/evaluation/queue routes;
extend the RoB workspace with readiness, proposal review, disclosure, staleness, and safety metrics.

Tests/gates: deterministic validation and rule-consumption unit tests; assignment, direct-ID,
blinding, stale-input, human-acceptance, dual-assessor, tenant, migration, evaluation, and RoB
non-mutation integration tests; backend/frontend standard gates subject to recorded Windows/Docker
environment blockers.

Definition of done: all proposal outputs are bounded and grounded; no canonical RoB mutation occurs
without an explicit human call to the existing service; complete focused validation and report.

Stop conditions: unresolved risk of AI leakage, unsupported evidence, duplicate RoB authority,
cross-tenant access, or any critical scientific/security defect.

Expected docs/ADR: ADR-026; update implementation status, domain/database/API/provenance/security,
AI architecture, testing, roadmap, and open-source component evaluation.

## Phase 28 — Governed AI Outcome/Effect-Estimate Harmonization Assistance

Objective: help humans identify candidate outcome mappings and structured reported components while
preserving explicit compatibility decisions and deterministic effect derivation.

Dependencies: Phases 19, 23, 26, and completed Phase 27 control-plane patterns.

Scope: immutable outcome-assistance policy and assignment/proposal links pinning Review, Study,
verified extraction value, outcome version, timepoint/unit/scale definitions, allowed mappings,
Document evidence/chunks, and task/model/prompt/input hashes; proposal validation for reported value,
units, timing, population, effect-measure components, and exact evidence; human disposition through
existing outcome mapping/estimate services; deterministic readiness and safety evaluation.

Non-goals: AI conversion, imputation, pooling, continuity correction, scale equivalence, hidden
time-window decisions, statistical recalculation, automatic mapping, or changing canonical outcomes.

Architecture/security/provenance: the AI link is advisory and tenant-scoped; source and normalized
values remain distinct; only deterministic existing conversion rules may normalize after a human
accepts a proposal. Preserve all input and evidence references and reject stale extraction/outcome
versions. Add only the minimum migration/API/UI surface needed for review and evaluation.

Tests/gates: exact type/unit/time/evidence validation, unsupported conversion, stale-input,
cross-review, human-service acceptance, unchanged synthesis readiness, evaluation/high-risk tests,
migrations and standard gates.

Definition/stop/docs: complete only when canonical outcome mappings and effect estimates remain
human/deterministic; stop on any hidden derivation or scientific boundary violation; ADR-027 and
relevant docs/report.

## Phase 29 — Governed AI Certainty-of-Evidence/GRADE Assistance

Objective: provide evidence-grounded drafting assistance for certainty rationales and explicit
domain considerations without making certainty decisions.

Dependencies: Phases 20–22, 21 certainty foundation, 23–28.

Scope: policy/proposal links pin framework version, outcome/timepoint/evidence body, current RoB
and analysis snapshots, included Studies, declared publication-bias evidence, and source locations;
bounded suggestions for evidence summaries, candidate domain rationales, and abstention; strict
validation against allowed framework domains/magnitudes; human review and canonical writes only via
certainty services; evaluation of grounding, unsupported downgrade/upgrade, abstention, calibration
description, and high-risk errors.

Non-goals: automatic downgrade/upgrade, invented thresholds, publication-bias inference, pooled
effect recalculation, certainty adjudication, official complete GRADE claim, or hidden baseline-risk
calculation.

Security/provenance/migration/API/UI/tests: same immutable tenant-scoped proposal pattern; every
output cites current pinned sources and is stale when upstream hashes change; add focused tables,
routes, workspace review, deterministic evaluation and migration/authorization tests.

Definition/stop/docs: human final certainty and adjudication remain canonical; stop for any
untraceable recommendation or stale evidence leak; ADR-028 and all relevant documentation.

## Phase 30 — Evidence-Aware Review Copilot / Project Intelligence

Objective: offer a read-only, evidence-cited project assistant for navigation, status explanation,
workflow blockers, and provenance-aware summaries across the Review.

Dependencies: canonical lifecycle through Phase 29 and the AI execution foundation.

Scope: explicit query/task registry, bounded deterministic context assembler, allowlisted canonical
read models, source citations and evidence locations, answer/abstention validation, snapshot hashes,
access/audit/provenance, review/member policy, and UI activity/history. Consequential questions must
link to records and stale context is labelled.

Non-goals: arbitrary SQL/search/tools, hidden retrieval, canonical mutation, scientific calculation,
unreviewed manuscript generation, cross-tenant context, or treating conversation as evidence.

Architecture/security: read-only use-case service over allowlisted repositories; provider receives
bounded structured context and no tools. Store minimal immutable task/output metadata, never secrets
or full restricted documents. Workflow payloads are never exposed. Context hashes are compared on
read and responses label changed canonical context as stale. Tests cover query authorization,
citations, staleness, prompt injection, tenant isolation, and no-write invariants. ADR-029/docs as
needed.

## Phase 31 — Durable Background Jobs and Worker Execution

Objective: turn the current workflow/job lifecycle shell into a durable PostgreSQL-backed claimable
worker contract without moving scientific decisions into workers.

Dependencies: workflow state machine, orchestration contracts, storage/parser boundaries, and
AI/search/document services.

Scope: job handler registry, persisted attempts/leases/heartbeats, idempotency, bounded concurrency,
claim/complete/fail/requeue, worker health, deterministic local runner, and explicit job payload
schema/version. Scientific jobs call domain services and carry provenance; worker state is separate.

Non-goals: autonomous scientific acceptance, unbounded queues, provider credentials, mandatory
Temporal deployment, or replacing HTTP authorization.

Security/provenance/migration/API/tests: tenant/review job ownership and payload redaction; audit
operational transitions and link scientific events; linear migration, worker endpoints/CLI, retry and
crash-recovery tests, and no cross-tenant claims. ADR-030/docs.

## Phase 32 — Workflow Orchestration, Resumability, Retry and Operational Recovery

Objective: make multi-step review workflows resumable and recoverable across interruption.

Dependencies: Phase 31 durable jobs and existing workflow checkpoints.

Scope: explicit workflow definitions/versioning, step checkpoints, retry taxonomy/backoff, timeout,
dead-letter/manual recovery, idempotent resume, pause/cancel boundaries, reconciliation diagnostics,
and recovery APIs/worker commands. Human checkpoints remain explicit and separate.

Non-goals: silent replay of consequential writes, hidden state blobs, arbitrary workflow transitions,
or production Temporal/cloud operations.

Security/provenance/tests: authorize each control operation, redact payloads, retain ordered event
history, protect scientific idempotency, test crash/retry/lease loss/stale version/tenant cases and
full migration chain. ADR-031/docs.

## Phase 33 — Production Scholarly Search/Retrieval Provider Integrations

Objective: implement provider-neutral scholarly adapters for configured OpenAlex/PubMed/Europe PMC or
equivalent sources while retaining exact SearchExecution and raw provenance.

Dependencies: search strategy/translation/execution domain, durable jobs, network policy.

Scope: HTTP protocol adapters with timeout/rate-limit/retry classification, bounded pagination,
polite identification, response normalization into citation source records, raw artifact integrity,
provider capability metadata, fixture providers, and explicit opt-in configuration.

Non-goals: credentials hidden in code, destructive imports, unbounded crawling, provider-dependent
canonical search semantics, or calling live APIs during implementation/tests.

Security/provenance/tests: SSRF/URL allowlists, response-size limits, secrets via environment only,
provider/model/version/query/attempt history, tenant-scoped artifacts, deterministic fixtures and
reconciliation tests. ADR-032/docs/open-source evaluation. Live execution may remain deferred.

## Phase 34 — Production AI Provider Integrations, Routing, Usage and Cost Governance

Objective: add safe provider adapters and explicit routing/budget policy while preserving the current
provider-neutral AI execution contract.

Dependencies: AI tasks 23–30, job/retry layer, configuration/secrets boundary.

Scope: adapter protocols for supported providers, model allowlists, task-to-model routing, timeout
and bounded retry, usage/cost normalization with honest unknown cost, attempt history, circuit/budget
limits, redaction, and deterministic no-network tests.

Non-goals: autonomous scientific decisions, silent consequential model fallback, training, paid calls,
credentials committed to source, or bypassing evidence/human boundaries.

Security/provenance/tests: secret/config audits, provider/model/prompt/task identifiers, cost ledger
separation from scientific data, explicit fallback policy, tenant budgets and failure classification.
ADR-033/docs. Live provider validation is deferred without credentials/authorization.

## Phase 35 — Production Document Processing/Object Storage/PDF Pipeline Hardening

Objective: harden immutable document acquisition, object storage, parser runs, evidence manifests,
and safe failure handling for production-like operation.

Dependencies: document foundation, provider adapters, durable jobs, storage contract.

Scope: S3-compatible adapter contract and local fixture, atomic upload/download verification,
content-type/size/signature policy, opaque keys, parser resource/time limits, retry/failure states,
versioned chunk manifests, restricted-document policy, and cleanup/reconciliation diagnostics.

Non-goals: OCR/computer vision, silent parser replacement, document redistribution, or claiming live
GROBID/PostgreSQL validation without the environment.

Security/provenance/tests: authorization before key resolution, checksum and malware-scan boundary,
SSRF-safe external retrieval, parser/task/source hashes, tenant tests, corrupted upload/reprocess
tests, migration/docs/ADR-034. Live GROBID/S3 remains environment-blocked if unavailable.

## Phase 36 — Collaboration, Assignment, Quality-Control and Operational UX Hardening

Objective: make human assignment, review queues, blinded states, error queues, job status, and
recovery controls usable without weakening scientific boundaries.

Dependencies: scientific AI workspaces, workflow/job APIs, existing Next.js review routes.

Scope: accessible queue/status/error/reveal screens, role-aware assignment and QC views, explicit
loading/error/stale states, provenance links, task filters, safe export/download affordances, and
frontend API typing/tests.

Non-goals: client-side authorization, client-side scientific calculations, bypassing blinding, or
new autonomous decisions.

Security/tests: server remains authority; test direct route/API leakage, role boundaries, tenant
isolation, stale banners, mutation error handling, lint/typecheck/Vitest/build. ADR/docs only if a
new UI architectural decision is needed.

## Phase 37 — Production Deployment, PostgreSQL Validation, Security, Observability, Backups and
Operational Readiness

Objective: prepare a controlled-deployment package and validate production-critical behavior where
the environment permits it.

Dependencies: Phases 31–36 and existing Compose/configuration.

Scope: production configuration audit, PostgreSQL migration/integrity validation, health/readiness,
structured logs/metrics/traces, audit retention, backup/restore runbook, secret handling, dependency
and container scans, rate limits, TLS/proxy assumptions, worker shutdown, and incident/recovery docs.

Non-goals: changing ACLs/WSL/Docker, provisioning paid infrastructure, using production credentials,
or claiming live readiness when checks are blocked.

Security/scientific/tests: threat/tenant/reproducibility review, migration upgrade/downgrade on
PostgreSQL if available plus SQLite chain, secret audit, health exercises, backup artifact checks,
and documented blockers. ADR-035/docs.

## Phase 38 — End-to-End V1 Validation, Scientific Benchmarking, Release Hardening and Launch Gate

Objective: validate the complete supported lifecycle and classify the release honestly.

Dependencies: all prior phases and their checkpoints.

Scope: end-to-end Review → protocol → search/execution provenance → citation/dedup → screening →
documents/full text → Study Family → extraction/verification → RoB → outcomes → analysis → certainty
→ PRISMA/reporting/reproducibility → governed AI → exports; deterministic scientific benchmarks;
backend/frontend/migration/security/tenant/provenance/staleness/export/secrets/operational review;
final reports and release checklist.

Non-goals: V2 features, silent limitation removal, live-provider claims without evidence, or GitHub
push.

Definition of done: create `V1_RELEASE_REPORT.md` with `READY_FOR_CONTROLLED_DEPLOYMENT`,
`READY_WITH_DOCUMENTED_LIMITATIONS`, or `NOT_READY`; all critical/high findings resolved or the
program stops with a blocker and durable state. Given known Docker/PostgreSQL/paid-provider limits,
the expected honest classification is `READY_WITH_DOCUMENTED_LIMITATIONS` unless the environment
changes.

## Durable state and recovery

`EXECUTION_STATE.json` is the machine-readable source for current phase/step, validations, blockers,
files, next action, and checkpoint state. `RECOVERY.md` requires a fresh session to read the
architecture, domain/security/AI/testing documents, current state, relevant ADRs, and Git status/log;
inspect partial files and resume from the first incomplete durable step. `VALIDATION_LOG.md`,
`DECISIONS.md`, `BLOCKERS.md`, and `PHASE_REPORTS/phase-XX.md` are the human-auditable trail.

`checkpoint_status` describes the current phase and is one of `NOT_READY`, `READY_FOR_CHECKPOINT`,
`CHECKPOINT_PENDING`, or `CHECKPOINTED`. Completed phase SHAs are retained in
`phase_checkpoints`; state and Git `HEAD` must be reconciled before resuming. If a state file claims
completion but its recorded local commit is absent, the phase is `CHECKPOINT_PENDING`, not silently
skipped.

## Current execution status

Phase 27 is locally checkpointed at `995c5af78996410ef9a04ddbe93b00ed3c52f79e`, Phase 28 is
locally checkpointed at `f47561973e697ac30a87c41a865d146b18e11246`, Phase 29 is locally
checkpointed at `df0a74fd2231e76d61f248b0e1fad398e7ee1566`, and Phase 30 is locally checkpointed
at `c59a340839c6fa12f2717681fa19ab41e3671ea1`. Phase 30 passed its focused backend, migration,
frontend, scientific, security, provenance, secret, and artifact gates; the full pytest no-output
timeout remains truthfully recorded as an environment limitation. Phase 31 implementation now
includes versioned payload metadata, durable attempts/leases/heartbeats, bounded worker capacity,
claim/complete/fail/requeue/expiry recovery, redacted claim responses, worker health, and the
deterministic local runner. Its focused backend/migration/security/provenance gates pass, the
full-suite timeout is documented, and the validated implementation checkpoint is local commit
`65de1a90ffbc81f3ed3ca1ac5f4ba030648f76d9`. The next safe action is Phase 32 planning. No GitHub
operation is authorized.
