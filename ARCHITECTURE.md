# Architecture

## Purpose

The platform manages the complete systematic-review lifecycle while keeping scientific records reconstructable. It is a modular monolith first, with explicit service boundaries that can move to separate processes only when scale or isolation justifies it.

## Five pillars

1. **Workflow orchestrator** owns stage progression, jobs, retries, idempotency, pauses, and human checkpoints. It coordinates engines but contains no scientific interpretation.
2. **Specialized research engines** own bounded scientific capabilities such as protocol design, search translation, citation ingestion, deduplication, screening, document normalization, extraction, verification, bias assessment, deterministic analysis, PRISMA, and reporting.
3. **Structured evidence store** uses normalized PostgreSQL records as canonical scientific state. Conversations and model responses are never canonical evidence.
4. **Provenance ledger** connects consequential outputs to source evidence, actor/model/prompt/version metadata, changes, and downstream use.
5. **Human checkpoints** make high-impact proposals reviewable, conflict-resolvable, and explicitly approvable.

## Non-negotiable separation

```text
HTTP/UI -> application use case -> specialized engine -> repository/provider contract
                                  |                 |
                                  |                 +-> scientific data
                                  +-> orchestrator ----> workflow state
                                  +-> provenance service -> provenance/audit
```

Workflow state, scientific data, and provenance use separate models and tables. Foreign keys link them where appropriate; a single serialized workflow blob must never become the evidence store.

## Runtime topology

- **Web:** Next.js App Router, TypeScript, Tailwind. Server Components fetch the FastAPI REST API for reads; interactive mutations will use a typed browser/API client where needed.
- **API:** FastAPI, Pydantic, SQLAlchemy 2, and Alembic.
- **Database:** PostgreSQL is the canonical relational store.
- **Workers:** Python processes consume orchestrated work through an `Orchestrator` interface.
- **Object storage:** `ObjectStorageProvider`, backed by the local filesystem in development and S3-compatible storage later.
- **AI:** `AIProvider` and task-specific AI services. Development defaults to a deterministic mock.
- **Scientific services:** document parsing and statistics remain isolated behind adapters; GROBID and R/metafor are candidates.

## Dependency direction

Domain contracts do not import FastAPI, SQLAlchemy sessions, vendor SDKs, or UI code. Infrastructure implements domain/provider contracts. Route handlers validate transport input, authorize, invoke an application service, and serialize output.

## Data and tenant boundaries

All tenant-owned scientific data is rooted in an Organization and Review. Repository methods require tenant context rather than relying on client-supplied identifiers alone. PostgreSQL constraints provide integrity; application authorization provides policy. Row-level security remains an evaluated defense-in-depth option.

## Versioning and history

Approved scientific artifacts are immutable. Updates create successors and retain previous versions. Audit events are append-only. Provenance is a scientific graph, not a log-message string.

## Orchestration decision

The initial adapter is lightweight and local so development needs only PostgreSQL. The contract includes stable workflow/job identifiers, idempotency keys, explicit states, and event history. Temporal remains the preferred durable adapter once Phase 4 exercises concrete workflows. See `docs/adr/ADR-002-workflow-orchestration.md`.

## Deployment posture

Local Docker Compose is primary. Containers run as non-root where practical, health/readiness are distinct, configuration comes from environment variables, and Next.js produces standalone output. Production cloud topology is intentionally deferred.

