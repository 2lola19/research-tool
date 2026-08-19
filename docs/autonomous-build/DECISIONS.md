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

## 2026-08-18 — baseline and control plane

- Observed the expected clean Phase 26 baseline at `ff5e1bb`; no newer valid work needed
  reconciliation.
- Created a durable autonomous-build control plane before Phase 27 implementation. The definitive
- remaining roadmap was written after inspecting the actual repository rather than copying the
  provisional phase list. The envelope remains Phases 27–38, with durable jobs and recovery split
  across Phases 31–32 and offline-safe provider/storage/parser hardening in Phases 33–35.
