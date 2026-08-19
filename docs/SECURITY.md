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
## Phase 26 extraction isolation and disclosure controls

Every schema, assignment, Study, Article, Document, processing run, block, proposal, reference case,
and evaluation lookup is scoped to organization and review before use. Allowed source documents are
explicit; cross-report use additionally requires a canonical shared Study. Foreign IDs fail closed.
BLINDED_AI withholds values, missingness, confidence, evidence, and validation through assignment,
direct proposal, generic AI, and evaluation paths until human submission. Prompt framing treats paper
instructions as inert content, inputs are bounded, secret markers remain blocked, and providers have no
filesystem, network, browser, database, shell, or arbitrary tools.

## Phase 27 Risk-of-Bias isolation and disclosure

Every RoB AI policy, proposal link, source, evidence span, access event, answer review, evaluation
dataset, case, result, and error classification repeats Organization/Review scope and uses composite
foreign keys. Readiness requires the current actor to own the assessor-owned assessment, use an
approved instrument version, and name only processed Documents linked to the Study Family. Foreign
tenant, Review, assessor, Article, Document, parser, block, and evaluation identifiers fail closed.

The generic AI create/list/direct-proposal routes reject or omit `ROB_SUGGESTION`. Dedicated serializers
withhold structured answers, rationale, confidence, evidence, validation, domain, and overall fields
for BLINDED_AI until canonical submission; direct IDs do not bypass this rule. ASSISTED access is
assignment-scoped and audited. Stale instrument, assessment, parser, block, or selected-text inputs
cannot be accepted. Source text is untrusted, bounded, secret-screened, and passed to a no-tools
provider adapter. AI cannot satisfy dual assessment, adjudicate disagreement, or mutate canonical RoB
state.

## Phase 30 read-only copilot security

Copilot task registry, policy, query, and direct-object routes require active organization
membership, Review access, and the existing AI review permission; policy creation additionally
requires AI-management permission. Foreign organization/Review/query identifiers fail closed.
Composite foreign keys and path-scoped reads prevent cross-tenant enumeration.

The assembler allowlists Review metadata, deterministic PRISMA values/readiness, workflow states,
and source-reference counts; workflow job payloads and arbitrary retrieval are excluded. User query
and project/source text are framed as untrusted data, secret markers and size limits remain active,
and providers receive no tools. Exact supplied citation IDs are required for non-abstaining answers.
The generic AI route rejects the task, and no copilot endpoint can transition workflow state, write
scientific data, calculate statistics, or generate manuscript content.

## Phase 28 AI outcome security

Outcome assistance uses active organization membership and Review-scoped authorization for every
policy, readiness, proposal, review, evaluation, and error operation. Proposal links require the
source Document to belong to the Review and its Article to be linked to the target Study. Composite
foreign keys and path-scoped direct-object reads prevent cross-tenant and cross-review access.

Generic AI endpoints reject the outcome task. The frontend cannot write canonical scientific state
through an AI route: explicit human dispositions are passed to `OutcomeService`, which rechecks
Study, extraction, OutcomeDefinitionVersion, allowed references, source mappings, evidence, and
immutability. Invalid or stale proposals cannot be accepted; edited dispositions must include a
human canonical payload. AI cannot calculate, convert, infer missing components, pool, or alter
analysis readiness.

## Phase 29 AI certainty security

Certainty assistance requires active organization membership, Review access, the assessor-owned
in-progress assessment, an immutable framework version, included Study identities, and explicit
processed source Documents whose Articles belong to those Studies. Every policy, readiness,
proposal, review, evaluation, and error query is tenant/Review scoped; composite foreign keys and
path-scoped identifiers fail closed across tenants, Reviews, assessments, frameworks, Documents,
Articles, and evaluation records.

The generic AI routes reject the certainty task. Source text is untrusted, bounded, secret-screened,
and passed to a no-tools provider adapter. Deterministic validation rejects fabricated or mismatched
evidence, unsupported domains/magnitudes, stale inputs, candidate/final certainty, thresholds,
publication-bias inference, and statistical calculations. Only an explicit human disposition can
call the canonical certainty service; stale or invalid proposals cannot be accepted, and AI cannot
write final certainty, submit, compare, adjudicate, or create Summary-of-Findings state.

## Phase 31 durable worker security

Worker claims require an exact registered task/version/payload-schema signature, tenant/Review
scope, an active worker registration, and available bounded capacity. Lease tokens are unique
capabilities used only for the matching worker attempt; attempt history and copilot context never
serialize them. API claim payloads are allowlisted and redacted by the handler registry, and result
and failure snapshots are size-bounded JSON.

Foreign Review and organization identifiers fail closed before claim, attempt mutation, or requeue.
Heartbeat, completion, failure, requeue, and expiry are operational JobEvents, not scientific
provenance. Scientific handlers remain behind their existing service authorization and provenance
requirements; a worker cannot autonomously approve evidence, change protocol or workflow meaning,
or replace a human checkpoint. The local runner uses only deterministic offline handlers and no
provider credentials.

## Phase 32 recovery security

Retry policy accepts only bounded numeric values and an explicit failure-class allowlist. Automatic
retry is limited to transient, timeout, and lease-loss classes; permanent and unknown failures are
dead-lettered. Manual recovery requires the existing workflow-controller authorization, tenant and
Review scope, a reason, and a durable idempotency key. Exhausted jobs require an explicit bounded
additional-attempt budget, and recovery operations are retained for audit.

Step checkpoints and reconciliation diagnostics are scoped by organization, Review, and workflow
run. Definition hashes prevent silent version substitution. Reconciliation is read-only, lease and
timeout recovery is bounded, and no route returns lease capabilities or scientific payloads. The
local `--recover-expired` worker command is operational only; it does not approve human checkpoints
or invoke provider credentials.

## Phase 33 scholarly provider security

Provider execution is disabled by default and requires an explicit deployment setting plus the
existing search-controller authorization. The registry permits only fixed HTTPS provider hosts;
the transport rejects schemes, credentials, non-443 ports, private/loopback addresses, arbitrary
hosts, and redirects. Requests use bounded timeouts, page counts, page sizes, aggregate raw bytes,
response bytes, retry attempts, capped backoff, and rate limiting. User-agent/contact values reject
header injection.

OpenAlex, PubMed, and Europe PMC adapters receive only the exact stored query and bounded filters.
Optional PubMed credentials are environment-backed `SecretStr` values; secret parameters are
excluded from request fingerprints and never stored in raw artifacts, logs, or API responses.
Raw responses are checksum-verified tenant-scoped artifacts. Normalized records enter the existing
citation import/provenance path, while provider attempts are append-only operational history.
Provider adapters cannot alter canonical search strategy, protocol, Article, Study, screening, or
analysis state and live network execution is not used by tests.

## Phase 34 production AI provider security

OpenAI, Anthropic, and Gemini adapters use fixed HTTPS endpoints and a repository-owned transport;
arbitrary provider URLs, redirects, tools, retrieval, filesystem, shell, browser, and database
authority are unavailable. Responses are byte-bounded and provider failures are classified without
including response bodies or credentials in error messages. API keys are `SecretStr` settings read
from environment-backed configuration and are never placed in model configuration, run snapshots,
attempt history, registry responses, logs, or provenance.

Live execution requires an explicit enable flag, a selected provider, an allowlisted model
identifier, structured-output capability, and (unless explicitly governed otherwise) versioned
input/output prices. Task routing is pinned and fallback is disabled. Organization-scoped attempt
history enforces monthly token/cost budgets and opens a bounded provider/model circuit after
repeated failures. Unknown usage/cost is surfaced rather than guessed; budget or circuit blocks
fail closed. AI remains advisory and human/domain-service boundaries are unchanged.

## Phase 35 document and object-storage security

Document authorization is evaluated before storage-key resolution or byte access. Uploads require
an exact PDF media type, signature, bounded size, simple filename, generated tenant/review/article
key, and post-write SHA-256/size verification. Local writes are atomic; the S3-compatible adapter
accepts only the vendor-neutral client protocol and validates returned keys. No storage SDK,
credential, or arbitrary object URL is admitted into domain code.

Processing reads verify the persisted checksum and size, bound parser execution and canonical
output, classify missing/integrity/invalid/limit/timeout failures, and preserve the original
artifact for retry or manual investigation. External document URLs are HTTPS-only and reject
credentials, fragments, invalid ports, loopback/private/link-local/reserved hosts, and local host
names; Phase 35 does not fetch them automatically. Restricted, paywalled, licensed, and user-
uploaded classes require screening permission for content download.

Storage reconciliation is tenant/review-scoped, returns counts and document identifiers only, and
is read-only: it never deletes or rewrites an object. Parser manifests contain bounded hashes and
metadata rather than unbounded source bytes. Malware scanning remains an explicit deployment
boundary and no clean-scan claim is made by the local fixture.

## Phase 36 operational workspace security

The Review operations UI treats the backend as the sole authorization and blinding authority. The
round index first resolves active organization membership and Review access; membership, QC,
workflow-control, queue, and provenance sections are independently allowed or marked restricted
when the server denies them. A foreign Review or direct round identifier is never converted into a
client-side permission decision or a data-bearing error.

Assignment and adjudication submissions are authenticated Next.js server actions that forward only
bounded form values to the existing screening endpoints. The UI never accepts a reviewer role,
reveals peer decisions, or performs consensus/scientific calculations in the browser. Workflow
payloads are not displayed; operational failure messages are presented as bounded status metadata.
Loading, service errors, stale reconciliation warnings, and mutation rejection are explicit, and no
failed read is rendered as a successful scientific state.

## Phase 37 deployment and operational security

Staging and production settings fail closed unless they use a non-local authentication provider,
PostgreSQL, an explicit migration-head readiness check, non-debug logging, and HTTPS non-wildcard
CORS origins. API responses add baseline security headers; production adds HSTS under the assumption
that TLS is terminated by an approved proxy. The application does not trust arbitrary forwarded
headers from clients.

Request middleware validates bounded request IDs, accepts only a valid W3C `traceparent` trace ID,
and emits structured method/route/status/duration logs without bodies, bearer tokens, tenant IDs,
query strings, or provider responses. The metrics endpoint uses route labels with UUID/numeric
segments redacted and is intended for an internal scrape path.

Password-token issuance has a bounded process-local rate limiter. It is an additional safeguard,
not distributed abuse prevention; multi-replica deployment must add an edge or shared-store limit.
Worker termination preserves durable lease/recovery semantics and never turns operational retry into
an automatic scientific replay. Secret management, OIDC, TLS, malware scanning, object storage,
dependency/image scanning, and backup encryption remain controlled-deployment gates.
