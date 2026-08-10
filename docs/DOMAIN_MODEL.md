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

`CitationImportBatch` is one losslessly retained RIS, BibTeX, or CSV input. `CitationSourceRecord` is the provider/export row and raw metadata. `Article` is the normalized publication record created from that row. Similar Articles may coexist until a separate deduplication decision; Article is never collapsed into Study.

`DeduplicationRun` records the exact algorithm and Article snapshot. `DuplicateCandidate` is a system-generated pair, score, and reason. `DeduplicationDecision` is the human confirmation or rejection and names the retained Article when confirmed. Confirmation is a relationship, not a destructive merge.

`ScreeningRound` defines one ordered title/abstract or full-text stage and its independent-decision threshold. `ScreeningAssignment` binds an authorized reviewer to one Article without disclosing peer decisions. `ScreeningDecision` is immutable. `ScreeningOutcome` is a deterministic consensus/conflict result, `ScreeningAdjudication` is the final human resolution of a conflict, and `ScreeningProgression` records idempotent movement of eligible Articles into a later full-text round.

Tenant-owned aggregates carry organization ownership and review scope. Immutable versioned aggregates carry a logical identity plus monotonically increasing version and approval state.
