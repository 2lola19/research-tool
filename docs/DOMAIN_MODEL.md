# Domain Model

Domain modules will be introduced by phase rather than creating empty tables early.

## Identity and tenancy

- `User` is a global login identity with a normalized unique email and active state.
- `Organization` is the tenant root.
- `Membership` joins a User to an Organization with one of six organization roles. Removal is soft so security history is retained; removed memberships cannot create actor context.
- `LocalCredential` is a development/test authentication record isolated from the User so a production authentication provider can replace it.
- `ActorContext` is request-scoped application state resolved from a signed identity plus a current active Membership. It is never persisted as client-authored data.
- `ReviewMembership` grants access to one Review inside the same Organization. It does not replace organization membership.

`Review` is introduced in Phase 2 and expanded by the Review Projects milestone with tenant ownership, creator, owner, title, organization-unique project slug, description, timestamps, and administrative archive metadata. Ownership transfer is constrained to an active same-organization member. Archive state is project administration, not scientific workflow state; the workflow subsystem remains separate.

Core aggregate boundaries are Organization, Review, Protocol, Search Strategy, Article, Study, Screening Round, Document, Extraction Schema, Risk-of-Bias Assessment, and Analysis. Article represents a publication or citation record. Study represents the underlying investigation and may link to multiple Articles.

Cross-cutting records include Actor, Audit Event, Scientific Provenance, AI Run, Prompt Version, Model Version, Workflow Run, Job, and Job Event. These remain separate from scientific entities even when linked by foreign keys.

`WorkflowRun` identifies a versioned workflow execution within one Review. `WorkflowJob` identifies a versioned, idempotent task and contains operational input only. `JobEvent` is ordered operational history. `HumanCheckpoint` is a separately resolved decision record; it is not embedded in mutable job payload state and does not substitute for scientific provenance.

`PromptVersion`, `AIRun`, `ScientificProvenance`, and `AuditEvent` form distinct immutable ledgers. Prompt versions describe instructions, AI runs capture executions, scientific provenance relates a scientific subject to sources/method/actor, and audit events describe application changes. Generic ledger references do not merge Article, Study, or other scientific aggregates.

`ProtocolVersion` is immutable structured scientific content containing the objective, research question, eligibility criteria, outcomes, study designs, and analysis plan. `ProtocolDecision` is a separate final human approval or rejection. Revisions always create a new version; no status update rewrites an earlier approved version.

`SearchStrategyVersion` captures provider-neutral concept groups and typed terms, pinned to an approved ProtocolVersion. `SearchTranslation` is the exact output of one deterministic provider translator version. Provider query syntax never replaces canonical search intent.

`IdentificationSource` is the structured identity and PRISMA classification of a database,
register, website, organization, citation-searching method, reference list, author contact, manual
import, or other source. `SearchExecution` records what was actually run: source/provider, optional
strategy and translation, exact query, restrictions, acquisition method, execution date, software
version, actor, and append-only status events. `SearchExecutionCitationLink` retains every imported
source-record discovery path, including multiple providers for the same eventual Article.
`SearchExecutionArtifact` preserves optional raw provider/file bytes through tenant-scoped object
storage with SHA-256 integrity metadata. Terminal executions are immutable; explicit corrections
create a superseding execution while ordinary updates remain independent historical executions.

`CitationImportBatch` is one losslessly retained RIS, BibTeX, or CSV input. `CitationSourceRecord` is the provider/export row and raw metadata. `Article` is the normalized publication record created from that row. Similar Articles may coexist until a separate deduplication decision; Article is never collapsed into Study.

`DeduplicationRun` records the exact algorithm and Article snapshot. `DuplicateCandidate` is a system-generated pair, score, and reason. `DeduplicationDecision` is the human confirmation or rejection and names the retained Article when confirmed. Confirmation is a relationship, not a destructive merge.

`ScreeningRound` defines one ordered title/abstract or full-text stage and its independent-decision threshold. `ScreeningAssignment` binds an authorized reviewer to one Article without disclosing peer decisions. `ScreeningDecision` is immutable. `ScreeningOutcome` is a deterministic consensus/conflict result, `ScreeningAdjudication` is the final human resolution of a conflict, and `ScreeningProgression` records idempotent movement of eligible Articles into a later full-text round.

`Document` is a stored full-text/retrieval record for one Article source. Multiple Documents may belong to one Article, preserving publisher, repository, user-uploaded, external-link, and supplementary relationships without merging Articles. The original file is retained in object storage under an opaque key with MIME type, size, SHA-256, source, actor, and access metadata. `DocumentProcessingRun` records parser/version/status and errors. Canonical `DocumentBlock` rows represent normalized sections, paragraphs, and future tables/figures; `DocumentEvidenceLocation` provides reusable page/section/block citations. `DocumentWarning` records retraction, correction, concern, or invalid-file warnings without deleting evidence.

`FullTextScreening` pins a document decision to an approved ProtocolVersion. `FullTextCriterionJudgment` stores independent PASS, FAIL, UNCLEAR, or NOT_APPLICABLE results with reasons and optional evidence locations. The final INCLUDE, EXCLUDE, or MAYBE decision is derived deterministically from criterion judgments and remains separately auditable and provenance-linked.

`Study` is the stable identity for an underlying investigation within a Review. `StudyArticleLink` relates one Study to one Article with a role such as PRIMARY, PROTOCOL, FOLLOW_UP, SUBGROUP, or SECONDARY_ANALYSIS. Links retain method, actor, reason, confidence, and source evidence; unlinking is a timestamped soft change, so Article records and family history remain intact.

`ExtractionSchema` owns reusable review-specific definitions. Each `ExtractionSchemaVersion` is immutable and stores ordered typed field metadata, allowed options, requiredness, units, and a content hash. Scientific missingness is explicit rather than represented only by SQL NULL.

`ExtractionRun` pins one extractor's work to a Study and schema version. `ExtractionValue` stores typed columns, explicit missingness, linked source Article and/or Document evidence, selected evidence text, and audit/provenance references. A Study extraction may source different fields from different linked Articles.

`ExtractionVerification` compares two runs deterministically. Equal canonical values become MATCHED; value or evidence disagreement creates an `ExtractionConflict` containing both original snapshots. Adjudication updates only the conflict/verification state and appends provenance; original extraction values are never overwritten.

`AnalysisSpecification` owns immutable versions of the scientific synthesis policy. Each version
pins a canonical outcome/timepoint, population and comparison, eligible designs, effect measure,
model/estimator, transformation, interval method, zero-event/variance/adjustment rules, explicit
selection policy, dependency safeguards, and minimum Study count. `AnalysisSet` materializes one
explicit, revalidated estimate per Study from a Phase 19 synthesis candidate and retains its
canonical input hash plus synthesis-specific exclusions; it never changes systematic-review
eligibility.

`MetaAnalysisRun` is an immutable execution snapshot linked to one specification version and
AnalysisSet. A run retains terminal status, provider/algorithm versions, input/result hashes,
structured pooled output, diagnostics, Study weights, and leave-one-out children. Historical runs
remain reproducible when later upstream corrections make them stale. `AnalysisArtifact` contains a
renderer-only forest plot whose version, checksum, and generation time link back to the run.

`RiskOfBiasInstrument` is a Review-scoped logical method. Each immutable
`RiskOfBiasInstrumentVersion` stores ordered domains and signalling questions, instrument-specific
answer/domain/overall choices, compatible Study designs, optional guidance, declarative suggestion
rules, and a content hash. A separate append-only decision approves or rejects a version; the
bundled demonstration randomized-study definition validates the engine but is not complete RoB 2.

`RiskOfBiasAssessment` pins one independent assessor, Study, approved instrument version, round, and
revision. Structured `RiskOfBiasAnswer` and domain-judgment records retain rationale, deterministic
suggestions, explicit final judgments, override reasons, and optional existing Document evidence
locations. Evidence may span protocol, primary, follow-up, and supplementary Articles in the active
Study Family. Submitted records are immutable; an explicit superseding revision preserves the
original. `RiskOfBiasComparison` records deterministic signalling/domain/overall differences after
authorized reveal, and append-only adjudication stores a final verified snapshot without overwriting
either independent assessment.

`PrismaSnapshot` is an immutable, algorithm-versioned derivation from eligible SearchExecutions and
their citation-source links, citation records,
deduplication decisions, screening outcomes, report retrieval/full-text decisions, and active Study
links. Counts distinguish source records, Article reports, and Study investigations. Readiness
blockers prevent incomplete workflow state from being presented as final.

`ExportArtifact` preserves exact CSV, XLSX, JSON, or RIS bytes with a deterministic manifest,
PRISMA snapshot reference, SHA-256 checksum, media metadata, creator, audit event, and scientific
provenance. Artifacts are append-only; creating another export never rewrites an earlier file.

`OutcomeDefinition` is a Review-scoped canonical outcome identity. Immutable
`OutcomeDefinitionVersion` records endpoint type, direction, protocol role, compatible effect
measures, allowed units/scales, expected timepoint windows, optional protocol version, and content
hash. `TimepointWindow`, `UnitDefinition`, and `MeasurementScale` are immutable Review scientific
configuration; no universal window, analyte conversion, or scale transform is inferred.

`OutcomeMapping` is an append-only relationship from one Study extraction value to one canonical
outcome version. It preserves the reported value/unit/time/anchor, normalized value/unit/duration,
conversion and timepoint rule versions, optional scale and sign transformation, actor, rationale,
method, confidence, and extraction-verification state. Corrections create a successor mapping.

`EffectEstimate` preserves a reported or deterministically derived structured estimate, its
components, natural/log variance scale, adjustment state, analysis population, timepoint, unit,
scale, evidence, calculation version, and zero-event pattern. Tenant-scoped source links retain every
mapping used. `SynthesisCandidateSet` is an immutable future-analysis selection, while
`AnalysisReadinessSnapshot` records a deterministic status and ordered structured blockers. Neither
entity performs statistical pooling.

Tenant-owned aggregates carry organization ownership and review scope. Immutable versioned aggregates carry a logical identity plus monotonically increasing version and approval state.

CertaintyFramework is a Review-scoped logical human appraisal framework whose immutable versions
define explicit starting rules, downgrade domains, upgrade considerations, allowed magnitudes, and
content hashes. DecisionThresholdVersion records optional outcome-specific thresholds without
inventing defaults.

CertaintyAssessment targets one OutcomeDefinitionVersion and optional timepoint, plus an exact
current MetaAnalysisRun/specification when quantitative synthesis is used. Independent assessors
record explicit starting certainty, structured human domain judgments, deterministic candidate
certainty, separate final certainty, and override rationale. Submission stores an evidence
snapshot/hash and becomes immutable; corrections supersede rather than rewrite. CertaintyComparison
is the explicit blind reveal boundary and preserves deterministic disagreements. Human adjudication
appends a final snapshot without mutating either assessment. SummaryOfFindingsSnapshot stores a
structured outcome row and explicitly marks unsupported absolute effects unavailable.