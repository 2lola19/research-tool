# ADR-018: Versioned outcome harmonization and deterministic analysis readiness

Status: Accepted
Date: 2026-08-11

## Context

Verified extraction values are not automatically suitable for statistical synthesis. Similar labels
may describe different endpoint definitions, time anchors, populations, scales, units, or effect
measures. Mathematical convertibility alone is therefore insufficient, and a future meta-analysis
engine must not consume raw extraction values without a scientific compatibility boundary.

## Decision

- Separate Review-scoped logical outcomes from immutable, content-hashed outcome versions. Each
  mapping and estimate remains pinned to the version used at the time; changes create another
  version.
- Represent Review-specific timepoint windows, structured units, and measurement scales as immutable
  scientific configuration. Preserve reported values, units, durations, anchors, and direction
  before recording any normalized representation.
- Permit unit conversion only where source and target share an explicit dimension, context, and base
  unit. Record both rule versions. Analyte-dependent conversions require an analyte/context-specific
  definition and can never use a generic concentration rule.
- Treat direction reversal as an explicit, reason-bearing transformation. Do not infer scale
  equivalence or standardize different scales merely because SMD exists.
- Store effect estimates as structured records with an explicit measure, reported/derived origin,
  variance scale, adjustment state, analysis population, timepoint, unit/scale, source mappings,
  evidence, and typed components. Normalized association tables enforce tenant/review foreign keys
  from estimates to mappings and from candidate sets to estimates.
- Implement only foundational deterministic calculations: RR, OR, and RD from 2x2 data and MD from
  group means. Where SDs and sample sizes are present, calculate sampling variance. Persist Decimal
  results at 12 decimal places using half-even rounding under `effect-foundation-1`. RR/OR variances
  are explicitly marked `LOG`; RD/MD variances are `NATURAL`.
- Never apply an implicit continuity correction. Zero or boundary cells are retained as structured
  patterns and, where the requested estimate cannot be derived safely, generate a readiness blocker.
- Represent a synthesis candidate as an immutable selection of estimates for one outcome version,
  effect measure, timepoint/window, and population label. Evaluation appends an immutable
  `analysis-readiness-1` snapshot with structured blockers; it does not pool estimates.
- Default readiness requires verified/adjudicated extraction provenance. It detects incompatible
  outcome/effect/timepoint/unit/scale, missing variance/sample size, adjusted/unadjusted or population
  mixing, zero-event policy needs, and multiple estimates from one Study.
- Keep Risk of Bias accessible but separate. High RoB does not exclude a Study unless a future,
  explicitly versioned analysis policy says so. PRISMA counting is unchanged.
- Use the existing provenance and audit ledgers for every consequential mapping, conversion,
  derivation, and readiness snapshot. Future AI may propose values only through this same boundary.

## Consequences

The future analysis engine receives explicit candidate sets rather than raw extractions, while
original scientific observations remain reconstructable. JSON/XLSX exports advance to
`review-export-4`; CSV and RIS Article semantics remain unchanged. Pooled estimates, heterogeneity,
forest plots, meta-regression, and statistical policy selection remain Phase 20 work. PostgreSQL
execution of the composite constraints remains environment-blocked; the full SQLite chain is
validated locally.
