# Phase 35 Report — Document Processing, Object Storage, and PDF Hardening

Date: 2026-08-19

## Objective

Harden immutable document acquisition, verified object storage, bounded parser execution, canonical
processing history, evidence manifests, restricted-content access, and read-only reconciliation
without collapsing Document, Article, Study, workflow, or provenance state.

## Implementation

- Added a verified storage protocol with opaque-key validation, atomic local writes, checksum/size
  verification, metadata/list support, and a vendor-neutral S3-compatible adapter boundary.
- Aligned the persisted Document ID with the generated opaque storage key.
- Added parser limits, timeout/failure taxonomy, deterministic title/abstract/body materialization,
  and versioned chunk manifests with bounded block/text hashes and counts.
- Added append-only processing-run metadata, bounded retries, verified content retrieval,
  restricted-document authorization, HTTPS/private-host source URL validation, and read-only
  review-scoped storage reconciliation.
- Added migration `20260819_0035`, ADR-034, domain/database/security/provenance/API/testing/open-
  source documentation, and tenant/integrity/parser/storage coverage.

## Validation

- Repository Ruff check: PASS.
- Repository Ruff format check: PASS (374 files).
- Strict `mypy backend workers`: PASS (234 source files).
- Backend/worker compileall: PASS.
- Focused Phase 35 unit/integration/migration shard: PASS (24 tests).
- Full pytest gate: ENVIRONMENT_BLOCKED — no output after 424 seconds; the exact pytest/python
  descendants were inspected and terminated safely. No full-suite assertion result is claimed.
- Live GROBID, S3, malware scanning, external retrieval, PostgreSQL concurrency, and Docker remain
  deployment/environment gates; no live-service claim is made.
- Scientific, security, provenance, tenant-boundary, secret, generated-artifact, and scope reviews:
  PASS, subject to the documented live-service limitations.

## Checkpoint

Implementation and required reviews are complete. The validated local checkpoint is ready under the
truthful message:

`feat: harden document processing and object storage pipeline`

Local checkpoint: PASS — implementation commit
`05787fc4cf180ddb51c22c9c7b55f96c6d6e4a6b` exists with the truthful phase-specific message, contains
only the validated Phase 35 scope, and leaves the worktree clean. `EXECUTION_STATE.json` records the
same SHA as `CHECKPOINTED`; Phase 36 is the next resume point. No GitHub operation was authorized.
