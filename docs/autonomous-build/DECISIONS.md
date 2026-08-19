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

## 2026-08-18 — baseline and control plane

- Observed the expected clean Phase 26 baseline at `ff5e1bb`; no newer valid work needed
  reconciliation.
- Created a durable autonomous-build control plane before Phase 27 implementation. The definitive
- remaining roadmap was written after inspecting the actual repository rather than copying the
  provisional phase list. The envelope remains Phases 27–38, with durable jobs and recovery split
  across Phases 31–32 and offline-safe provider/storage/parser hardening in Phases 33–35.
