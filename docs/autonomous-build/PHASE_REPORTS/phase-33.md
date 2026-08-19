# Phase 33 Report - Production Scholarly Search/Retrieval Provider Integrations

## Objective

Implement provider-neutral scholarly adapters for OpenAlex, PubMed E-utilities, Europe PMC, and an
offline fixture while preserving exact SearchExecution query/filter history, raw response
integrity, tenant scope, and scientific provenance.

## Implemented

- Added capability metadata and provider contracts for OpenAlex, PubMed, Europe PMC, and a bounded
  deterministic fixture provider.
- Added an HTTPX-backed transport behind a repository-owned protocol with fixed HTTPS host
  allowlists, redirect/SSRF rejection, bounded response bytes, timeout, rate-limit, retry/backoff,
  polite user-agent, and secret-safe request fingerprints.
- Added provider normalizers for JSON/XML result shapes and deterministic normalized citation import
  through the existing CitationImportService; no destructive Article merge or provider-specific
  canonical search semantics were introduced.
- Added explicit opt-in provider execution routes, bounded pagination settings, raw response
  artifacts, `COMPLETED`/`PARTIAL` result handling, provider/version/query provenance, and tenant-
  scoped append-only `search_provider_attempts` history.
- Added migration `20260819_0034`, ADR-032, API/database/security/provenance/testing/open-source
  documentation, and deterministic provider fixtures.

## Validation

- `ruff check .`: PASS.
- `ruff format --check .`: PASS (362 files).
- `mypy backend workers`: PASS (230 source files).
- `python -m compileall -q backend workers`: PASS.
- Provider unit fixtures: PASS (7 tests).
- Search execution integration: PASS (4 tests), including explicit opt-in and attempt/artifact
  persistence; existing search/citation/config/routing regression: PASS (17 tests).
- SQLite migration upgrade/downgrade: PASS through `20260819_0034`.
- Full `pytest -q`: `ENVIRONMENT_BLOCKED_TIMEOUT_NO_OUTPUT_384_SECONDS`; exact pytest descendants
  were inspected and terminated safely; no assertion result is claimed.
- Scientific, security, provenance, tenant, secret, and generated-artifact reviews: PASS.
- Live provider calls, credentials, Docker, PostgreSQL concurrency, and external service behavior
  remain deployment/environment gates. No GitHub operation is authorized.

## Checkpoint

Implementation and required validation are complete. The validated local implementation checkpoint
exists:

- Commit: `1687da9d5f4da9332786692e5085a856848b9c99`
- Message: `feat: add provider-neutral scholarly search integrations`
- Worktree after implementation checkpoint: clean before metadata reconciliation
- GitHub operation: none

The execution state and this report were reconciled in the follow-on metadata checkpoint. The next
implementation phase is Phase 34, production AI provider integrations and routing/cost governance.
