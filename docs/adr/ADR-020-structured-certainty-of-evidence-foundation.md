# ADR-020: Structured certainty-of-evidence foundation

## Status

Accepted 2026-08-12.

## Context

Phase 20 produces immutable statistical results but does not determine how certain reviewers should
be in an outcome-specific body of evidence. Certainty judgments must preserve independent human
reasoning, evidence context, disagreement, revisions, and upstream staleness without turning
heterogeneity, interval width, one Study's Risk of Bias, or missing publication-bias tests into
automatic scientific decisions.

## Decision

A Review-scoped CertaintyFramework owns immutable, content-hashed versions. The bundled
GRADE-compatible foundation provides the five downgrade domains (Risk of Bias, inconsistency,
indirectness, imprecision, and publication bias), three structured upgrade considerations, and
explicit evidence-body starting rules. It validates the generic engine and does not claim complete
official GRADE support.

A CertaintyAssessment targets one immutable outcome version and optional timepoint window. When
quantitative synthesis exists, it also pins the exact Phase 20 specification version and completed,
current MetaAnalysisRun; narrative evidence instead names Review-scoped Studies explicitly.
Decision thresholds are optional, outcome-pinned, independently versioned records. No threshold is
invented by the application.

Assessors record every domain choice and rationale. The deterministic candidate calculation applies
only the explicit magnitudes chosen by the assessor, with floor/ceiling bounds. The assessor records
the final certainty separately and must explain any departure from the candidate. No LLM or
automatic statistical rule supplies a judgment.

Independent assessor content remains blind. An authorized adjudicator can see only comparison
candidate identity/target metadata until an explicit comparison record reveals two current submitted
revisions. Comparison deterministically preserves starting, domain, and final differences.
Adjudication appends a final selected snapshot and never changes either submission.

Submitted assessments are immutable. Corrections create a superseding revision. Evidence snapshots
include framework/outcome/threshold hashes, the exact Phase 20 result and hashes, included Study
identities, current submitted RoB revisions and comparison/adjudication history, and declared
publication-bias evidence. Read-time hashes expose later analysis or RoB changes as staleness.

Evidence Profiles and Summary-of-Findings rows are structured snapshots. The foundation reports
absolute effects as unavailable because no validated baseline-risk calculation is implemented.
Stale certainty evidence cannot create a new current Summary-of-Findings snapshot.

## Consequences

Certainty remains outcome/evidence-body scoped, human-first, reproducible, and tenant isolated.
GRADE consumes Phase 18 and Phase 20 evidence but duplicates neither subsystem and performs no
statistical recalculation. JSON/XLSX exports advance to review-export-6; CSV/RIS Article semantics
remain unchanged. Advanced official framework content, baseline-risk methods, publication-bias
inference, network meta-analysis, and AI-generated decisions remain out of scope.