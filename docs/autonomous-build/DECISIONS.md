# Autonomous Build Decisions

This file records material roadmap, architecture, scientific, security, and validation decisions
made during the autonomous V1 completion program. Ordinary implementation choices remain in the
relevant phase report or ADR.

## 2026-08-18 - Phase 27 scientific and architectural boundary

- Risk-of-Bias assistance is an advisory projection over the existing Phase 18 instrument,
  assessment, and declarative domain-rule services. No parallel canonical RoB system was added.
- The AI task may propose only instrument-permitted signalling answers, exact grounded evidence,
  rationale, confidence, or abstention. Domain and overall suggestions are computed only from
  validated answers by the existing deterministic rules, and remain non-canonical.
- A human answer disposition is the only entry point that can call the existing canonical answer
  service. AI proposals never satisfy independent assessment, adjudication, or submission.
- Blinded mode withholds proposal content through assignment-scoped and direct-object reads and
  records disclosure/access events. Accepted values retain the AI run, evidence, validation, and
  human provenance chain.
- Evaluation metrics are descriptive safety diagnostics, including grounding, abstention,
  coverage, confusion, calibration description, and dangerous-underestimation queues; they do not
  create thresholds or scientific decisions.

## 2026-08-18 - Phase 28 canonical outcome boundary

- Outcome assistance is an advisory projection over the existing `OutcomeService`; no parallel
  mapping, conversion, effect-calculation, pooling, or analysis substrate was created.
- The task accepts only a mapping candidate, a reported-effect candidate, or abstention. Exact
  source chunks and bounded quotes are mandatory for non-abstaining output. Canonical outcome
  version allowlists are filtered before the provider sees them, and deterministic validation
  rejects identity changes, unsupported references, calculations, and unsafe effect metadata.
- Human `ACCEPTED` dispositions require a valid candidate of the matching canonical kind. Invalid
  proposals require `EDITED` plus an explicit human payload; both routes call the existing
  `OutcomeService`, preserving its tenant, evidence, compatibility, and immutable-write rules.
- The UI extends the existing outcomes workspace with typed API access and explicit payload-based
  human disposition. It does not present AI output as canonical or let the browser calculate
  scientific values.

## 2026-08-19 - Phase 29 certainty boundary

- Certainty assistance is an advisory projection over the existing immutable framework and
  `CertaintyService`; it does not create a second certainty engine or claim complete official GRADE
  support.
- Deterministic preparation pins the assessor-owned in-progress assessment, evidence profile,
  included Studies, explicit processed Documents, parser/chunk inputs, and hashes. The provider may
  summarize evidence or suggest only exact framework-permitted domain choices with evidence.
- AI cannot produce final/candidate certainty, thresholds, publication-bias inference,
  upgrades/downgrades, statistical calculations, adjudication, or submission. Human `ACCEPTED` and
  `EDITED` dispositions require an explicit domain payload and call `CertaintyService.save_domain`.
- Evaluation stores descriptive grounding/agreement, abstention, unsupported-adjustment, and
  high-risk metrics outside canonical certainty state. The workspace exposes pinned proposals and
  requires a human disposition; no browser-side scientific calculation was added.

## 2026-08-19 - Phase 30 read-only Review copilot boundary

- The Review copilot is a read-only advisory projection over allowlisted Review, deterministic
  PRISMA, and workflow read models. It does not create a second workflow/scientific state machine,
  expose job payloads, retrieve arbitrary content, or write canonical state.
- Explicit task keys cover project status, workflow blockers, and provenance navigation. The
  context assembler is deterministic, bounded, hashed, and citation-indexed before provider
  execution; user/source text is untrusted data and providers have no tools.
- Non-abstaining output must cite exact supplied citation IDs. Fabricated citations, unsupported
  actions, oversized answers, invalid confidence, and unexplained abstention are rejected. Query
  and policy records are append-only and tenant/Review scoped.
- The frontend exposes policy, query, and immutable activity history while directing users to the
  existing canonical domain surfaces for any action. The offline deterministic provider abstains
by default; live providers and arbitrary retrieval remain deferred.

## 2026-08-19 - Phase 33 scholarly provider boundary

- OpenAlex, PubMed E-utilities, Europe PMC, and the deterministic fixture implement the existing
  provider protocol. A small allowlisted HTTP transport owns timeouts, response limits, retries,
  rate limits, redirect rejection, and polite identification; provider SDKs and arbitrary URLs are
  out of scope.
- Provider execution is explicit and disabled by default. Normalizers create `ParsedCitation`
  records only through the existing citation/provenance service; raw response bytes remain a
  checksum-verified SearchExecution artifact, and provider attempts remain append-only operational
  history.
- Provider/version/query/filter/attempt metadata is retained without credential parameters.
  Partial bounded pagination is represented honestly as `PARTIAL`; no adapter changes canonical
  search intent, Articles, Studies, screening, analysis, or human checkpoints.
- ADR-032 records the boundary. HTTPX is accepted only as an infrastructure transport dependency;
  live provider calls remain a deployment gate and are not used in tests.

## 2026-08-19 - Phase 34 production AI provider boundary

- OpenAI Chat Completions, Anthropic Messages, and Gemini Generate Content use repository-owned
  provider adapters and a bounded HTTP transport. Fixed HTTPS endpoints, response limits, timeout,
  safe status classification, and no-tool structured requests keep vendor behavior outside domain
  logic; no provider SDK or arbitrary URL is accepted.
- Live execution requires an explicit enable flag and environment-backed secret. Provider/model
  allowlists and structured-generation capabilities are checked before the run; task routing pins
  one model/provider in the immutable policy snapshot, and fallback is disabled.
- Existing append-only AI attempts are the usage/cost and failure history. Provider usage is
  normalized without inventing missing fields; exact decimal cost is recorded only with versioned
  prices and known usage. Tenant token/cost budgets and bounded provider/model circuits fail closed.
- AI output remains advisory. Existing deterministic validators, human decisions, provenance, audit,
  workflow state, and scientific domain services remain the only canonical acceptance boundaries.
  ADR-033 records the decision; live credentials and paid/network validation remain deferred.

## 2026-08-19 - Phase 31 durable worker boundary

- Durable execution extends the existing workflow job contract with explicit payload schema/version,
  bounded attempts, tenant/review-scoped leases, persisted heartbeats, and separate worker health;
  it does not create a second scientific or workflow state machine.
- Claims require an exact allowlisted handler signature and bounded worker capacity. Completion,
  failure, requeue, and lease expiry append operational job events; attempt history withholds lease
  capabilities from ordinary reads and copilot context.
- The deterministic local runner and `--once` CLI execute only registered offline handlers. Future
  scientific handlers must call existing domain/provenance services; Temporal, live providers, and
  richer retry/resume/reconciliation semantics remain Phase 32 or later.

## 2026-08-18 — baseline and control plane

- Observed the expected clean Phase 26 baseline at `ff5e1bb`; no newer valid work needed
  reconciliation.
- Created a durable autonomous-build control plane before Phase 27 implementation. The definitive
  remaining roadmap was written after inspecting the actual repository rather than copying the
  provisional phase list. The envelope remains Phases 27–38, with durable jobs and recovery split
  across Phases 31–32 and offline-safe provider/storage/parser hardening in Phases 33–35.

## 2026-08-19 — Phase 32 recovery boundary

- Phase 32 keeps workflow definitions/version hashes, retry/backoff/timeout policy, dead-letter
  state, step checkpoints, recovery idempotency, and reconciliation in operational workflow tables.
- Automatic retries are limited to explicitly retryable transient/timeout/lease-loss classes. A
  permanent or unknown failure is dead-lettered; manual recovery requires an authorized reason,
  idempotency key, and an explicit bounded attempt budget when exhausted.
- Resume is idempotent and respects pause/cancel/human-checkpoint boundaries. Reconciliation is
  read-only diagnostics; it never replays a scientific write or resolves a human checkpoint.
- This boundary is recorded in ADR-031. No Temporal/cloud runtime, provider credential, or new
  scientific decision authority was introduced.

## 2026-08-19 — Phase 35 document and storage boundary

- Original PDF bytes remain the immutable source artifact. Verified local storage and the
  vendor-neutral S3-compatible protocol own atomic writes, opaque-key validation, and SHA-256/size
  checks; no vendor SDK or storage credential enters domain code.
- Document IDs and storage keys are generated together and persisted together. Parser processing
  is bounded and append-only: missing/corrupt bytes, invalid output, limits, and timeouts create
  classified failed runs, while repair/retry creates a new run and never rewrites history.
- Canonical title, abstract, and body blocks are materialized deterministically before bounded
  manifests and evidence persistence. Restricted document classes require screening permission;
  reconciliation is read-only and cannot delete or silently repair artifacts.
- External source URLs are HTTPS/private-host validated but not fetched in this phase. GROBID,
  OCR, malware scanning, live S3/PostgreSQL, and production retrieval remain deployment gates.
  ADR-034 records the decision.

## 2026-08-19 - Phase 36 collaboration and operational UX boundary

- The Review operations surface is a server-rendered read model over existing Review, screening,
  workflow, PRISMA, provenance, and membership APIs. It does not create a browser-side workflow
  state machine or authorization model.
- The screening-round index is Review-access scoped; reviewer queue reads remain assignment-scoped,
  QC outcomes remain manager-scoped, and unrevealed peer/AI content is never reconstructed by the
  UI. Assignment and conflict adjudication are forwarded through authenticated server actions to
  the existing screening service.
- Operational freshness, loading, error, and stale-reconciliation labels are explicitly non-
  scientific metadata. No new UI ADR is needed because the design follows the existing Next.js
  server-component boundary. Phase 37 now owns deployment and observability readiness.
