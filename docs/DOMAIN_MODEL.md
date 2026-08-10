# Domain Model

Domain modules will be introduced by phase rather than creating empty tables early.

## Identity and tenancy

- `User` is a global login identity with a normalized unique email and active state.
- `Organization` is the tenant root.
- `Membership` joins a User to an Organization with one of six organization roles. Removal is soft so security history is retained; removed memberships cannot create actor context.
- `LocalCredential` is a development/test authentication record isolated from the User so a production authentication provider can replace it.
- `ActorContext` is request-scoped application state resolved from a signed identity plus a current active Membership. It is never persisted as client-authored data.
- `ReviewMembership` grants access to one Review inside the same Organization. It does not replace organization membership.

`Review` is introduced in Phase 2 with tenant ownership, creator, owner, title, and timestamps so ownership and access boundaries are enforceable. Later review-project work extends this aggregate rather than creating a second project entity.

Core aggregate boundaries are Organization, Review, Protocol, Search Strategy, Article, Study, Screening Round, Document, Extraction Schema, Risk-of-Bias Assessment, and Analysis. Article represents a publication or citation record. Study represents the underlying investigation and may link to multiple Articles.

Cross-cutting records include Actor, Audit Event, Scientific Provenance, AI Run, Prompt Version, Model Version, Workflow Run, Job, and Job Event. These remain separate from scientific entities even when linked by foreign keys.

Tenant-owned aggregates carry organization ownership and review scope. Immutable versioned aggregates carry a logical identity plus monotonically increasing version and approval state.
