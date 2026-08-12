# ADR-019: Deterministic statistical synthesis and immutable runs

## Status

Accepted 2026-08-12.

## Context

Phase 19 establishes semantic compatibility and analysis readiness but deliberately performs no
pooling. Statistical synthesis must consume only those harmonized records, preserve every
scientifically consequential choice, enforce Study independence, remain reproducible after upstream
changes, and permit a future independently deployed R/metafor provider without moving application
domain state into that service.

## Decision

An `AnalysisSpecification` is a Review-scoped logical analysis whose immutable versions explicitly
pin outcome/timepoint, population, intervention/comparator, Study designs, effect measure, model,
heterogeneity estimator, confidence-interval method, transformation, zero-event and missing-variance
policies, adjustment/population rules, estimate-selection rule, dependency policies, minimum Study
count, and prediction-interval request. No route or renderer supplies hidden scientific defaults.

An immutable `AnalysisSet` contains an explicit subset of one already evaluated Phase 19 candidate
set. Creation and execution both resolve the live harmonized estimates and reapply compatibility,
verification, Study-independence, variance, adjustment, population, zero-event, multi-arm, cluster,
and crossover checks. The canonical input payload excludes presentation metadata and is hashed with
sorted-key compact JSON plus canonical decimal strings.

`StatisticalSynthesisEngine` is a provider-neutral contract. Phase 20 implements
`NativeDeterministicSynthesisEngine`, identified as `native-inverse-variance/meta-analysis-1`. It
supports inverse-variance fixed-effect synthesis and random-effects synthesis with the explicit
DerSimonian-Laird between-Study variance estimator. Normal-quantile confidence intervals are
explicit. Ratio measures use the logarithmic analysis scale and are back-transformed for
presentation; identity-scale measures remain untransformed. The engine returns structured weights,
Q, degrees of freedom, Q p-value, tau-squared, tau, I-squared, an eligible prediction interval, and
diagnostics. Leave-one-out calculations reuse the same engine and are linked to the parent run.

Every execution creates a new `MetaAnalysisRun`; a completed or failed run is terminal and immutable.
Runs retain specification/set identity, algorithm/provider versions, deterministic input and result
hashes, timestamps, actor, diagnostics, weights, and sensitivity results. Historical output is never
rewritten. A read-time staleness check compares the current canonical input and specification
history while retaining the reproducible historical result.

Forest rendering consumes a `ForestPlotModel` built from a completed result; it performs no
statistics. Generated SVG bytes are an immutable tenant-scoped artifact with renderer version,
input hash, generation timestamp, size, and SHA-256 checksum.

## Supported methods and explicit boundaries

- Pooling supports RR, OR, HR, RD, MD, and explicitly defined SMD records when Phase 19 supplies a
  valid estimate and analysis-scale variance.
- Random-effects support is limited to DerSimonian-Laird with normal confidence intervals. REML,
  Paule-Mandel, Hartung-Knapp, and other alternatives remain future providers/versions.
- Zero-event records are blocked unless the specification explicitly excludes double-zero records.
  Counts are never modified and no continuity correction is implemented.
- Dependent multi-arm, unadjusted cluster, and incompatible crossover configurations are blocked;
  no arm splitting, invented ICC, or paired-variance approximation occurs.
- General subgroup inference, RoB filtering, meta-regression, publication-bias inference, and network
  meta-analysis are deferred. The engine/result contract can add typed child analyses without
  changing canonical Review state.

## Numerical reproducibility

Input and persisted output values use canonical decimal serialization and retain full computational
precision until presentation. Mathematical functions required by normal and chi-square inference
are isolated and versioned. Golden fixtures record independently derived equations and expected
fixed/random results, weights, confidence intervals, Q, I-squared, tau-squared, transformations,
prediction intervals, and leave-one-out results with explicit tolerances.

## Consequences

Scientific choices and results are inspectable, versioned, tenant-scoped, and reproducible. A future
metafor service must accept the canonical payload and return the structured result contract; it may
not receive database authority or expose raw R objects. Phase 20's bounded native implementation is
not a substitute for the wider estimator and dependency-policy validation required by advanced
analysis phases.
