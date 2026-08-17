# Security

The local foundation uses environment configuration, validates input, separates liveness from dependency readiness, applies restricted CORS, emits request identifiers, and avoids secrets in source.

Upcoming identity work must use established password hashing, short-lived sessions/tokens, organization-scoped RBAC, review membership checks, and negative tenant-isolation tests. Uploaded files require MIME/signature validation, size limits, generated storage keys, malware-scanning compatibility, and no direct path trust.

Phase 2 implements local development/test authentication with scrypt password hashing and short-lived HMAC-signed bearer tokens. Local authentication cannot be configured for staging or production. Tokens identify a user but do not cache roles or organization access. Every tenant request requires `X-Organization-ID` and resolves the active database membership again, so removal revokes an already-issued token's tenant access immediately.

Tenant-owned repository calls require organization scope. Cross-organization and unauthorized same-organization review lookups return the same not-found response to prevent identifier inference. Owner/Administrator have organization-wide review visibility; Lead Reviewer, Reviewer, Statistician, and Viewer visibility is ownership/assignment scoped, with independent mutation permissions. See ADR-005 for the accepted policy.

The local Next.js sign-in route exchanges credentials server-to-server, verifies organization context before establishing a session, and stores the bearer token and organization ID in HTTP-only, SameSite=Lax cookies. Browser code never receives or persists the token. Production sets Secure cookies. Review ownership transfer, archive/restore, and member changes repeat backend authorization and same-tenant membership checks.

Production hardening will add secure headers, rate limiting, signed object access, TLS termination, secret management, dependency scanning, backup/restore tests, and security-event monitoring. Authentication must never be weakened to make tests pass.

Export creation is restricted to Owner, Administrator, and assigned Lead Reviewer roles; metadata
and downloads still require active Review access and tenant scope. Artifact downloads recompute the
SHA-256 checksum before returning bytes. CSV cells beginning with spreadsheet formula prefixes are
neutralized, XLSX text is emitted as inline strings rather than formulas, filenames are generated
from sanitized project slugs, and export responses are served through an authenticated server-side
proxy in the UI.

Identification sources, executions, event histories, citation links, and raw artifacts repeat
Organization and Review scope in persistence and repository predicates. Composite foreign keys
reject cross-tenant sources, strategies, translations, citations, actors, and correction links.
Raw artifact reads authorize the Review before resolving the opaque storage key and verify size and
SHA-256 before returning bytes. Completed execution fields and all discovery links are append-only;
corrections preserve the original scientific record.

Risk of Bias routes use centralized `MANAGE_ROB_INSTRUMENT`, `PERFORM_ROB_ASSESSMENT`, and
`ADJUDICATE_ROB` permissions. Ordinary assessors can retrieve only their own assessment records;
authorized comparison is the reveal boundary. Every instrument, version, assessment, evidence,
comparison, and adjudication lookup repeats Organization and Review scope, and foreign direct IDs
return not-found semantics. Evidence locations are accepted only when their Document's Article has
an active link to the assessment Study. Viewers cannot mutate; reviewers cannot approve instruments
or adjudicate; completed submissions cannot be silently edited.

Outcome configuration uses centralized `MANAGE_OUTCOMES`, `HARMONIZE_OUTCOMES`, and
`PREPARE_SYNTHESIS` permissions. Every definition, version, window, unit, scale, mapping, estimate,
candidate set, and readiness query repeats Organization and Review scope. Composite foreign keys
also constrain Study, extraction value, protocol version, evidence location, mapping sources, and
candidate estimates to the same tenant/review. Effect evidence must resolve through an Article in the
target Study Family. Foreign and cross-review identifiers return not-found semantics, viewers cannot
mutate, and scientific history is append-only. Context-keyed unit conversion prevents a generic unit
rule from crossing analytes or dimensions.

Statistical synthesis uses centralized `MANAGE_ANALYSIS` and `RUN_ANALYSIS` permissions. Owner,
Administrator, assigned Lead Reviewer, and assigned Statistician may configure/run; all reads still
require active Review access. Every specification, set, selected estimate, run, weight, sensitivity
result, and artifact lookup repeats Organization and Review scope, with composite foreign keys as a
second boundary. Cross-review candidate/estimate IDs and foreign direct IDs return not-found
semantics. Forest bytes are resolved only after Review authorization and are served through an
authenticated server proxy. Terminal records are immutable and artifact checksums are verified
before use; no statistical provider receives tenant credentials or direct database authority.

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

Screening assistance requires an active Review member with an assigned screening record and an approved
protocol. Policy management, evaluation, and error taxonomy use centralized AI permissions; suggestion
generation and retrieval additionally verify assignment ownership. Every read repeats organization and
Review predicates, and foreign Review, assignment, proposal, dataset, evaluation, and case-result IDs
use not-found semantics.

The blinding boundary is enforced server-side. `BLINDED_AI` never serializes suggestion structure,
rationale, confidence, or evidence before the reviewer decision; `ASSISTED` and post-decision reveal
accesses are recorded. Proposal and evaluation tables have composite tenant/review foreign keys,
immutable ORM guards, and constrained modes/values. Article text is framed as untrusted source data,
evidence quotes must occur in the supplied title/abstract, exclusion criteria must come from the
approved protocol, and no provider receives credentials or workflow mutation authority.

Phase 25 repeats scope through exact Document/version, processing run, and chunk manifest. Only the
assigned reviewer reads assignment/direct-proposal content; BLINDED_AI returns no suggestion or
structured output before human decision and refuses evaluation leakage. Organization, Review,
Article, assignment, protocol, document, run, and chunk composition is checked before execution,
reveal, acceptance, or evaluation. Generic AI creation, proposal, decision, and run-list routes do
not expose either screening task, and the proposal's originally pinned mode governs disclosure even
if the Review policy later changes. Stale proposals cannot be accepted.

Providers receive bounded structured data with no tools, filesystem, shell, browser, network,
database, or arbitrary retrieval. Paper instructions and URLs remain inert quoted data. Secret
markers, oversized input/output, unknown criteria, foreign IDs, fabricated chunks/pages/sections, and
non-verbatim quotes fail deterministically. PDF bytes and storage paths are not prompt input.
