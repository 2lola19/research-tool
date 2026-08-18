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

## 2026-08-18 — baseline and control plane

- Observed the expected clean Phase 26 baseline at `ff5e1bb`; no newer valid work needed
  reconciliation.
- Created a durable autonomous-build control plane before Phase 27 implementation. The definitive
- remaining roadmap was written after inspecting the actual repository rather than copying the
  provisional phase list. The envelope remains Phases 27–38, with durable jobs and recovery split
  across Phases 31–32 and offline-safe provider/storage/parser hardening in Phases 33–35.
