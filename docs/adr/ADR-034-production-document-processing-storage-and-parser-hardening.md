# ADR-034: Production Document Processing, Storage, and Parser Hardening

- Status: Accepted
- Date: 2026-08-19
- Scope: Phase 35 document acquisition, object storage, PDF parsing, and processing recovery

## Decision

Keep original document bytes, canonical parsed blocks, processing-run history, scientific evidence,
workflow state, and provenance as separate concerns. Introduce a small verified object-storage
protocol with an atomic local implementation and a vendor-neutral S3-compatible adapter boundary.
The application owns opaque tenant/review/article keys and persists the same generated Document ID
used in the storage key.

Every uploaded PDF is checked for simple filename, exact media type, bounded size, and PDF signature.
The storage boundary verifies SHA-256 and byte size on upload and retrieval. Authorization happens
before key resolution. Restricted content requires screening permission. Reconciliation is a
tenant/review-scoped read-only diagnostic and never deletes or rewrites objects.

Processing runs are append-only. Parser name/version, verified source hash/size, bounded canonical
output, deterministic versioned chunk-manifest hash, failure class, and timing are retained. Failed
storage, parser, limit, and timeout attempts remain visible; retry creates a new run and cannot
silently reprocess a successful document. External source URLs are validated as HTTPS and are not
automatically fetched in this phase.

## Rationale and boundaries

- S3-compatible behavior is expressed through a protocol, so domain code does not depend on a
  vendor SDK or arbitrary endpoint authority.
- Original bytes remain the immutable source artifact; parser output is derived and bounded.
- Deterministic manifest construction supports evidence reconstruction without storing unbounded
  parser output in an operational row.
- GROBID, OCR, malware scanning, external retrieval, live S3, and PostgreSQL concurrency remain
  deployment or later-phase validation gates. No live-service claim is made by local fixtures.
- The migration adds only processing-run metadata and preserves Article/Study separation and the
  existing provenance/audit boundaries.

## Consequences

The local fixture is suitable for deterministic tests and repair/reconciliation exercises, but it
is not a production malware scanner or cloud-storage integration. Production adapters must supply
the protocol, enforce equivalent integrity metadata, and undergo deployment-specific security and
availability validation before enablement.
