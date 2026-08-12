# Roadmap

1. **Foundation (source complete; live stack environment-blocked):** repository, API, database/migrations, frontend, local containers, provider contracts, quality gates.
2. **Identity and multi-tenancy (complete):** local authentication, organizations, memberships/RBAC, actor context, tenant tests.
3. **Review Projects (complete):** tenant-owned project metadata, review members, ownership transfer, archive/restore, dashboard shell.
4. **Workflow State Machine (complete):** persisted workflow runs, explicit transitions, checkpoints, and transition invariants.
5. **Provenance Ledger (complete):** append-only audit/provenance/AI-run registries.
6. **Protocol Engine (complete):** immutable structured protocol versions and approval checkpoints.
7. **Search Strategy Domain (complete):** canonical search concepts and deterministic provider translators/fixtures.
8. **Citation Import (complete):** RIS/BibTeX/CSV source records with import provenance.
9. **Deduplication (complete):** deterministic identifiers followed by reviewable, non-destructive fuzzy candidates.
10. **Screening Foundation (complete):** reviewer queues, blinded immutable decisions, deterministic conflicts, adjudication, and full-text progression.
11. **Documents and full-text foundation (verified):** storage/validation, canonical parser adapter, evidence locations, warnings, and manual full-text eligibility.
12. **Study families (verified):** stable Study identity and non-destructive multi-Article relationships.
13. **Versioned extraction schemas (verified):** typed, immutable schema versions with explicit missingness metadata.
14. **Manual extraction (verified):** Study-level typed values with Article/Document evidence and provenance.
15. **Extraction verification (verified):** deterministic comparison, explicit conflicts, and human adjudication history.
16. **Deterministic PRISMA and reproducible export foundation (implemented):** database-derived flow counts, immutable snapshots, readiness blockers, portable CSV/XLSX/JSON/RIS artifacts, manifests, and checksums.
17. **Search execution and identification-source provenance (implemented):** structured source classes, immutable repeated executions, exact query/provider/method/status history, import discovery links, raw artifacts, deterministic PRISMA grouping, and search documentation exports/UI.
18. **Risk of Bias foundation (verified):** versioned declarative instruments, Study-design compatibility, multi-Article evidence, independent blind assessments, deterministic disagreement, human adjudication, and reproducible exports.
19. **Outcome/effect-estimate harmonization (verified):** versioned outcomes, explicit extraction mappings, Review-specific timepoints/units/scales, structured reported/derived effects, immutable candidate sets, and deterministic readiness without pooling.
20. **Deterministic meta-analysis foundation (implemented):** versioned explicit specifications,
    revalidated Study-independent sets, fixed-effect and DerSimonian-Laird random-effects synthesis,
    heterogeneity/prediction diagnostics, leave-one-out sensitivity, and reproducible SVG artifacts.
21. **GRADE/certainty foundation (recommended; not started):** structured versioned certainty
    criteria linked to immutable synthesis runs, RoB, inconsistency, indirectness, imprecision, and
    publication-bias judgments with independent human review. It must not silently reinterpret or
    recalculate Phase 20 results.
22. **Advanced analysis/reporting (deferred):** additional estimators, dependency policies,
    subgroups, meta-regression, publication-bias inference, network meta-analysis, and mature reports.

Each milestone must meet the definition of done in the master specification before progression.
