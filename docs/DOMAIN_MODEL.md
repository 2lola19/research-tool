# Domain Model

Domain modules will be introduced by phase rather than creating empty tables early.

Core aggregate boundaries are Organization, Review, Protocol, Search Strategy, Article, Study, Screening Round, Document, Extraction Schema, Risk-of-Bias Assessment, and Analysis. Article represents a publication or citation record. Study represents the underlying investigation and may link to multiple Articles.

Cross-cutting records include Actor, Audit Event, Scientific Provenance, AI Run, Prompt Version, Model Version, Workflow Run, Job, and Job Event. These remain separate from scientific entities even when linked by foreign keys.

Tenant-owned aggregates carry organization ownership and review scope. Immutable versioned aggregates carry a logical identity plus monotonically increasing version and approval state.

