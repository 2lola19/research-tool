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
## Phase 22 reporting and reproducibility foundation

Phase 22 adds a deterministic reporting layer over canonical Review state. Versioned `ReportSpecification`
records request explicit report types/sections/formats; immutable `ReportSnapshot` records source references,
source hashes, renderer version, and scientific-content hash; `ReportArtifact` stores exact JSON, HTML, XLSX,
and reproducibility-ZIP bytes with independent file checksums. Reporting readiness is report-type-specific and
supports explicitly labelled drafts. Report generation never recalculates PRISMA, Risk of Bias, certainty, or
meta-analysis results.

The reproducibility package validator checks deterministic relative paths, manifest schema, per-file SHA-256
checksums, package hash, and source identity without database mutation. Structured scientific records are
included; full-text binaries, raw provider bytes, secrets, environment files, storage keys, and runtime files
are excluded by default. Scientific staleness hashes cover canonical upstream scientific tables only; generated
provenance, exports, UI metadata, and report artifacts do not make an otherwise unchanged report stale.

A dedicated reporting workspace supports readiness, report type, package preview, generation, current/stale
status, checksum metadata, and authenticated downloads. Phase 22 is not a mature manuscript authoring system;
AI writing, living-review automation, PDF/DOCX, restricted document redistribution, and provider execution remain
deferred.

## Phase 23 AI provider foundation

Phase 23 adds a provider-neutral, task-oriented AI execution substrate with immutable model and prompt versions, bounded run/attempt lifecycles, input/prompt/response hashes, structured validation, append-only proposals and human decisions, usage/cost metadata, policy ceilings, tenant scoping, and accepted-AI provenance in reporting packages. The only executable workflow is an offline deterministic search-query draft proposal; it never mutates SearchStrategyVersion or another canonical scientific domain. Real providers, credentials, production scientific AI tasks, autonomous tools, and auto-accept remain deferred. AI provenance supports reconstruction of what was requested, returned, validated, and accepted but does not claim bit-for-bit model reproducibility.

## Phase 24 governed AI screening assistance

`AIScreeningPolicyVersion` is an immutable Review-scoped policy selecting `OFF`, `BLINDED_AI`, or
`ASSISTED` and a bounded request batch. `AIScreeningProposalLink` binds an AI proposal to one
screening assignment, Article, approved protocol snapshot, criterion hashes, citation hash, task
version, and assistance mode. It is not a ScreeningDecision and cannot change screening workflow.

`AIScreeningAccess` records assignment-scoped assisted and post-decision reveal events.
`AIScreeningDecisionLink` records the canonical human decision, interaction, and explicit disagreement
classification. `ScreeningEvaluationDataset` and its cases are independent human-curated reference
records. `ScreeningEvaluationResult` and immutable case results retain deterministic metrics and the
proposal dimensions used for evaluation. Error classifications append human review taxonomy without
mutating the model output or reference case.

## Phase 25 AI full-text eligibility assistance

`AIFullTextProposalLink` is an immutable provenance bridge, not a decision. It binds one proposal to
one full-text assignment, Article, acquired Document artifact version, successful parser run, approved
protocol, parser representation, and deterministic chunk snapshot. `PRIMARY_FULL_TEXT`, `SUPPLEMENT`,
`APPENDIX`, and `OTHER_SUPPORTING_DOCUMENT` preserve future multi-document semantics without merging
Article and Study. Cross-report Study Family evidence remains disabled by default.

Readiness blocks absent, unprocessed, failed, or textless documents. MAYBE and ABSTAIN carry structured
missing-information reasons; missing information is not exclusion. Evidence uses scoped chunk IDs,
nullable parser page/section metadata, and exact-verifiable quotes. Staleness is a derived current-view
property over immutable history. Evaluation reference records remain distinct from ScreeningDecision,
Article, Study, and StudyFamily.
## Governed AI extraction assistance

`AIExtractionProposal` is an immutable advisory projection over an existing human `ExtractionRun`; it
is not an `ExtractionValue`. The authoritative contract is the exact `ExtractionSchemaVersion`.
Proposal fields preserve reported value, normalized typed value, unit/option identity, explicit
missingness, evidence spans, and validation state. An accepted or edited field becomes canonical only
when the human actor calls the existing manual extraction service. Human field-review events and
blinded reveal events are append-only, while ordinary extraction revision, verification, and
adjudication semantics remain unchanged. Study and Article stay distinct; every source names both its
Article and Document.

## Governed AI Risk-of-Bias assistance

`AIRobProposalLink` is an immutable advisory bridge over an assessor-owned `RiskOfBiasAssessment`.
It pins the Study, approved immutable `RiskOfBiasInstrumentVersion`, exact signalling questions and
allowed choices, explicit Study Family source Documents, parser snapshot, selected/omitted chunks,
validation results, and derived provisional rule outputs. `AIRobSourceRecord` and
`AIRobEvidenceRecord` preserve Article/Document/parser/block identity and exact quotes.

`AIRobAnswerReviewRecord` stores a human disposition without changing the original AI proposal. An
accepted or edited signalling answer calls the existing `RiskOfBiasService`; AI never creates a
canonical domain judgment, overall judgment, assessment submission, comparison, or adjudication.
`AIRobEvaluationDataset` and its immutable results are separate from Studies, Articles, assessments,
and canonical RoB decisions. The demonstration instrument remains explicitly incomplete.

## Governed AI outcome harmonization assistance

`AIOutcomeProposalLink` is an immutable advisory bridge between one AI proposal and a verified
extraction value, Study, immutable OutcomeDefinitionVersion, and explicitly scoped processed
Documents. It records source/parser/chunk snapshots, validation results, and staleness inputs; it
is not an `OutcomeMapping` or `EffectEstimate`.

`AIOutcomeReviewRecord` stores a human disposition and optional canonical subject link. Only an
explicit human payload can call `OutcomeService.create_mapping` or
`OutcomeService.create_effect_estimate`; AI never performs conversion, derivation, pooling, or
analysis readiness. Evaluation datasets/results and error classifications are independent
quality records. Outcome and extraction versions remain immutable, and Study and Article remain
distinct entities.

## Governed AI certainty-of-evidence assistance

`AICertaintyProposalLink` is an immutable advisory bridge between an AI proposal and an assessor-
owned in-progress `CertaintyAssessment`. It pins the immutable OutcomeDefinitionVersion and
CertaintyFrameworkVersion, evidence profile, included Studies, Article/Document/parser/block
sources, selected/omitted chunks, validation results, and staleness hashes. It is not a certainty
assessment, domain judgment, final certainty, or Summary-of-Findings row.

`AICertaintyReviewRecord` stores the human disposition and optional canonical subject link. Only an
explicit human domain payload can invoke `CertaintyService.save_domain`; AI cannot choose the final
certainty, calculate thresholds, infer publication bias, adjudicate, or submit an assessment.
Evaluation datasets/results and error classifications are separate quality records. Certainty
framework versions and canonical assessments remain immutable and tenant/review scoped.

## Read-only Review copilot

`AICopilotPolicy` versions bounded query/context limits for a Review. `AICopilotQuery` is an
append-only advisory interaction containing an explicit task key, user query, deterministic context
snapshot/hash, source citations, optional AI run/proposal links, validated answer snapshot, status,
and audit-facing requester identity. It is not a Review, workflow transition, scientific judgment,
Article, Study, evidence value, or report artifact.

The context assembler consumes allowlisted Review, PRISMA, and workflow read models. It omits
workflow payloads and does not create a second project-status or scientific state machine. Exact
citation IDs resolve only to the snapshot's canonical source locators; abstention is a valid result.
