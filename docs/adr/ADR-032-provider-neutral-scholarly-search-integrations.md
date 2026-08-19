# ADR-032: Provider-neutral scholarly search integrations

- Status: Accepted
- Date: 2026-08-19

## Context

Search intent and translated queries are canonical scientific records, while a scholarly
provider's HTTP syntax, pagination, availability, and response shape are external acquisition
details. Live provider calls must not turn a vendor SDK, an arbitrary URL, or a transient response
into canonical scientific state. Reproducibility also requires retaining the exact raw response,
normalization boundary, provider version, and every bounded request attempt.

## Decision

- Implement OpenAlex, PubMed E-utilities, Europe PMC, and an offline fixture behind the existing
  `SearchProvider` protocol. Domain services depend on the protocol and a small HTTP transport,
  never on a provider SDK.
- Provider capability metadata is versioned in the registry: fixed HTTPS base URL, exact host
  allowlist, pagination support, maximum page size, media type, and credential requirement.
- Provider execution is explicit and disabled by default. Configuration supplies only bounded
  timeout, page, response, retry, rate-limit, polite-identification, and environment-backed
  credential values. Redirects, private/loopback addresses, arbitrary hosts, oversized responses,
  unbounded pagination, and header injection are rejected.
- HTTP failures use a bounded retry taxonomy. Rate limits, timeouts, and transient server/network
  failures may retry with capped backoff; permanent, invalid-response, and blocked failures do not.
- Adapters normalize provider records into `ParsedCitation` without changing canonical search
  semantics. The existing citation import service creates tenant-scoped source records and
  provenance. A completed/partial `SearchExecution` retains its exact query, filters, import
  linkage, and checksum-verified raw response artifact.
- Every request attempt appends an immutable tenant/Review-scoped attempt record containing
  provider/version, page and attempt number, safe request fingerprint, timestamps, status,
  failure class, response size/hash, and a bounded safe note. Secrets never enter fingerprints,
  raw artifacts, API responses, or logs.

## Consequences

Fixture adapters and injected transports make provider behavior testable without credentials or
live APIs. Live execution remains a deployment and operational gate; provider result totals can
produce `PARTIAL` execution status when configured pagination bounds are reached. Canonical
Article, Study, screening, and analysis state remains separate from provider acquisition history.
Adding another provider requires a new capability/version, deterministic normalizer fixtures,
security review, and migration/API documentation where persistence is needed.
