# SG-003 GROBID and Document Parser Validation

Status: `GROBID_GATE_EXTERNAL_REQUIRED`

Validated at: `2026-08-20`
Scope: SG-003 only. SG-004 and later gates were not started.

## Classification

`GROBID_GATE_EXTERNAL_REQUIRED`

The repository-side parser boundary, malware ordering, processing provenance,
chunk manifest, readiness, failure taxonomy, authorization, and retry behavior
are implemented and focused-tested. A direct live parse could not be completed
because the disposable official GROBID service could not be safely brought to
readiness on this host. This is an environment/service-capacity blocker, not a
claim that live parsing passed.

## Selected service and isolation

- Image: `grobid/grobid:0.9.1-crf`
- Selected immutable Linux amd64 manifest:
  `sha256:eb306e6d494f6f7e89b35bbaf3b4925afd58c6a5638c775f2a1c35bfd3c5db0d`
- Docker image ID and repository digest matched that digest after pull.
- Architecture: `linux/amd64`; Docker server architecture was `amd64`.
- Configured GROBID version: `0.9.1`.
- Provider identity emitted by the adapter: `grobid-0.9.1+adapter-1`.
- GROBID was placed in the project-private Compose network with no host port.
- The disposable overlay uses the real `/api/health` HTTP readiness probe,
  `init`, `core=0`, two CPUs, and a four-GB memory bound. The four-GB bound
  follows the upstream full-text memory guidance in the [official Docker
  guidance](https://github.com/grobidOrg/grobid/blob/master/doc/Grobid-docker.md).
- The reproducible topology is
  [`compose.sg003.yaml`](compose.sg003.yaml). The root Compose topology was
  not given a permanent GROBID service.

The official service documents `/api/health` as readiness, `/api/version` as
version identity, and `/api/processFulltextDocument` as the full-text TEI
endpoint: [GROBID service API](https://grobid.readthedocs.io/en/latest/Grobid-service/).

## Live startup evidence

1. The first isolated start used the lightweight CRF image with a two-GB bound.
   It remained non-ready while loading models, then exited with code `137` and
   `OOMKilled=true` before port `8070` opened. The container health log showed
   repeated connection refusal to `127.0.0.1:8070`; service logs ended during
   native model initialization.
2. The overlay was corrected to the upstream full-text four-GB memory
   recommendation and a 300-second readiness start period. `docker compose
   config --quiet` passed and the image was retried once.
3. During the first four-GB retry, Docker Desktop's Linux engine began returning
   HTTP `500 Internal Server Error` for container inspection, listing, and
   teardown calls. After Docker recovered without repair, one final bounded
   four-GB retry was observed to exit with code `137` and `OOMKilled=true`; its
   logs ended while loading the CRF segmentation model and port `8070` still
   refused connections. No `/api/health` `200` response, GROBID version
   response, or parser request was obtained. Docker/WSL was not restarted or
   repaired, per gate scope.

An initial teardown attempt was blocked while the engine was returning 500.
After Docker recovered without repair, the exact `research-tool-sg003` project
was removed with its disposable volumes and private network. No broad Docker
cleanup was attempted. The remaining operator action is to provide a supported
private GROBID runtime or approved endpoint with equivalent readiness and
resource guarantees.

## Image vulnerability scan

- Scanner image: `aquasec/trivy:0.74.0`
- Scanner image digest:
  `sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969`
- Target: the exact selected GROBID manifest above.
- Scan policy attempted: vulnerability scanner, `HIGH,CRITICAL`, unfixed
  findings included, no suppression.
- Result: **4 findings: HIGH=3, CRITICAL=1**. The Ubuntu 24.04 OS layer had
  zero findings. The four Java findings were `CVE-2026-54399` (httpcore5 5.4,
  HIGH; fixed in 5.4.3), `CVE-2026-54428` (httpcore5-h2 5.3.6, HIGH; fixed in
  5.4.3), `CVE-2025-14813` (Bouncy Castle 1.79 inside jruby-complete,
  CRITICAL; fixed versions published), and `CVE-2026-10050` (Jetty Security
  12.1.9, HIGH; fixed in 12.1.10). The current image contains the affected
  versions, so the findings are unresolved for this exact image; no waiver or
  suppression was applied. The first scan timed out during Java DB download,
  but the final exact scan completed after the Docker runtime recovered.

## Test document

No runtime PDF was acquired. Because the live service never became ready, no
public scholarly PDF was downloaded or generated, and there is no PDF hash,
byte size, TEI artifact, or parser output to report. This avoids retaining a
runtime document that did not contribute live evidence.

## Application changes and local evidence

- Added the provider-neutral live `GrobidDocumentParser` HTTP adapter with
  pinned version identity, health/version probes, multipart full-text request,
  bounded request/response sizes, timeout mapping, unavailable/provider/
  unsupported/invalid-output classification, and local TEI normalization.
- Kept GROBID as a parser only. It does not create or replace Article, Study,
  screening, extraction, Risk-of-Bias, or canonical scientific interpretation.
- Added canonical parsed-content hashing and persisted it with the append-only
  processing run. Successful provenance now links document hash, parser/version,
  processing-run ID, parsed-content hash, and chunk-manifest hash.
- Added the live-parser migration and raised the expected migration head to
  `20260820_0038`.
- Added `/health/processing-ready`, which checks database, malware scanner, and
  parser readiness. Application liveness and ordinary application readiness do
  not fail solely because the optional parser is unavailable.
- Added a disposable, private, digest-pinned GROBID Compose overlay. No raw TEI,
  PDF, credentials, scanner database, or internal service address is exposed by
  the application API.

Local focused evidence passed:

- `tests/unit/test_document_parsers.py` — provider protocol, TEI structure,
  title/abstract/body normalization, page/section metadata, output limits,
  timeout and provider failure taxonomy, canonical hash determinism.
- Health, config, security, and migration tests — parser readiness distinction,
  staging parser requirement, tenant-safe health behavior, and migration
  upgrade/downgrade through `20260820_0038`.
- `ruff check .`, `ruff format --check .`, strict `mypy backend workers`, and
  `python -m compileall -q backend workers` passed.
- Existing SG-002 evidence and focused document tests establish that only an
  exact current-hash malware result of `CLEAN` can make a document parser
  eligible. `INFECTED`, `ERROR`, `TIMEOUT`, `UNAVAILABLE`, altered-content, and
  retry paths remain fail-closed. These are not live GROBID results.

## Evidence not claimed

Because the service and scan gate were unavailable, this run does **not** claim:

- live GROBID health, runtime version, or successful PDF parse;
- live title, abstract, body, page/block/section output;
- live parsed-output hash, processing-run ID, chunk-manifest identity, or
  evidence reconstruction;
- live GROBID timeout, unavailable, malformed-response, parser-error, retry, or
  idempotency behavior;
- live cross-tenant parser-result access protection;
- zero HIGH/CRITICAL findings for the exact GROBID image.

## Required external rerun

Provide one of the following without changing the provider-neutral boundary:

1. A supported private disposable GROBID service using the pinned official image
   and enough runtime memory for `/api/processFulltextDocument`, plus an exact
   Trivy result; or
2. An approved private GROBID endpoint with health/version evidence and an
   operator-owned vulnerability disposition for its exact image.

Then rerun with one openly shareable scholarly PDF, recording only source,
license/type, SHA-256, byte size, bounded parser metadata, processing-run and
manifest hashes. A successful external rerun must exercise malware `CLEAN`
ordering, live parse, failure/timeout handling, retry/idempotency, tenant
scoping, and evidence reconstruction before SG-003 can be changed to PASS.
