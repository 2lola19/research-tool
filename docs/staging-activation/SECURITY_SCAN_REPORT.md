# Security Scan Report

Status: COMPLETE_WITH_EXTERNAL_GATES

## Tool availability and baseline

- npm 12.0.2 / Node v24.16.0: npm audit --omit=dev --audit-level=high
  passed with zero production findings.
- pip-audit 2.10.1 was installed into the existing repository project virtual
  environment without administrator or host changes. Trivy 0.74.0 was run as
  a disposable container using its project-scoped cache volume
  research-tool-staging-activation_trivy_cache.
- Docker Scout 1.23.1 is installed, but quickview requires Docker ID
  authentication. No login was attempted.
- The names-only high-risk scan searched tracked content for private-key and
  cloud-access-key patterns and found no matches. No secret values were printed
  or stored.

## Findings and dispositions

1. pip-audit initially found PYSEC-2026-1845 in pytest 8.4.2, fixed by pytest
   9.0.3. This was a development/test dependency, not a runtime application
   dependency, but it was fixed minimally by changing pyproject.toml to
   pytest>=9.0.3,<10. The project environment now has pytest 9.1.1;
   pip-audit reports no known vulnerabilities and pip check passes. The
   focused backend/API and boundary suites passed afterward.
2. The previous backend runtime image had nine HIGH Debian util-linux-family
   findings plus bundled toolchain findings. backend/Dockerfile now upgrades
   the affected Debian packages and removes pip from the final runtime. Fresh
   backend, worker, and migrate images have zero HIGH/CRITICAL Trivy findings.
3. The previous frontend runtime image had one CRITICAL and six HIGH Node
   toolchain findings. frontend/Dockerfile now removes npm, npx, corepack, and
   Yarn from the final standalone runtime. The fresh frontend image has zero
   HIGH/CRITICAL Trivy findings.
4. The official postgres:17-alpine image, digest
   sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73,
   has one CRITICAL and 21 HIGH findings in /usr/local/bin/gosu, installed
   Go stdlib v1.24.6. The official postgres:17-bookworm image, digest
   sha256:84560e3b9c6874893fc4e2854f5dc3e7c1a37bc9d1dfd7a8c641310ae22ba5ad,
   has the same gosu finding profile. This is not silently waived: the
   approved staging image owner must provide a remediated digest or a
   documented security exception.

## Exact scan evidence

- pip-audit --local --progress-spinner off: PASS after the pytest fix; the
  local package review-platform is skipped because it is not published on PyPI.
- npm audit --omit=dev --audit-level=high: PASS, zero vulnerabilities.
- Trivy image scans with scanners=vuln, severity=HIGH,CRITICAL,
  ignore-unfixed: backend, worker, migrate, and frontend PASS at zero
  HIGH/CRITICAL; PostgreSQL remains blocked by the gosu findings.
- docker compose config --quiet: PASS. No scanner output, runtime database,
  quarantine data, or credentials were added to the repository.

The unresolved PostgreSQL image findings and unavailable Docker Scout account
are external/operator gates. They prevent READY_FOR_CONTROLLED_STAGING but do
not indicate an application-code vulnerability after the recorded fixes.

## 2026-08-20 SG-001 targeted refresh and disposition

This addendum is the authoritative SG-001 evidence and corrects the earlier
aggregate-only PostgreSQL scan record. The earlier evidence is preserved. The
repository baseline was HEAD
`6fdb35f526a1ea9c54a46eb86bde4d3b0e4740ad` with a clean worktree. Compose
still declares `postgres:17-alpine`; no Compose/config change was made because
no supported official digest passed the gate.

### Exact image and refreshed scan

The intended Compose tag resolves locally and in the official registry to
`postgres@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73`.
The evaluated platform is Linux amd64. It is PostgreSQL 17.11 on Alpine 3.24.1,
with `/usr/local/bin/gosu` 1.19 built with Go 1.24.6. The official image
manifest and source are recorded by the Docker Official Images entry for
PostgreSQL 17 and the generated
`17/alpine3.24/Dockerfile`.

The running `research-tool-readiness-db-1` container is an older, untagged local
image ID `sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193`
(PostgreSQL 17.10, gosu 1.19, Go 1.24.6). It has no retained registry
RepoDigest. It was scanned by that immutable local image ID and returned the
same 22 gosu findings. This corrects any earlier implication that the running
container had the `18cfe3...` image ID; the Compose tag and the running
container were not reconciled by restarting the project because the current
official digest is not clean.

The exact final-digest command was equivalent to:

`docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v research-tool-staging-activation_trivy_cache:/root/.cache/trivy aquasec/trivy@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969 image --quiet --scanners vuln --pkg-types os,library --severity HIGH,CRITICAL --format json postgres@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73`

Trivy was 0.74.0. No `ignore-unfixed` option or suppression was used. The
Trivy vulnerability database metadata was `UpdatedAt=2026-08-20T00:55:38Z`
and `DownloadedAt=2026-08-20T05:08:45Z`. The scan created at
`2026-08-20T08:43:54Z` found 22 findings: one CRITICAL and 21 HIGH, all in
`/usr/local/bin/gosu` as Go `stdlib v1.24.6`; the Alpine OS target had zero
HIGH/CRITICAL findings. Trivy's source for these records is the Go Vulnerability
Database (`https://pkg.go.dev/vuln/`) surfaced through the Aqua Vulnerability
Database URLs.

### Complete HIGH/CRITICAL finding record for the final digest

| Advisory | Severity | Affected module/path | Installed | Fixed version(s) | Scanner mapping | Disposition |
|---|---|---|---|---|---|---|
| CVE-2025-68121 | CRITICAL | stdlib / crypto/tls | v1.24.6 | 1.24.13, 1.25.7, 1.26.0-rc.3 | GO-2026-4337 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2025-61726 | HIGH | stdlib / net/url | v1.24.6 | 1.24.12, 1.25.6 | GO-2026-4341 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2025-61729 | HIGH | stdlib / crypto/x509 | v1.24.6 | 1.24.11, 1.25.5 | GO-2025-4155 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-25679 | HIGH | stdlib / net/url | v1.24.6 | 1.25.8, 1.26.1 | GO-2026-4601 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-27145 | HIGH | stdlib / crypto/x509 | v1.24.6 | 1.25.11, 1.26.4 | GO-2026-5037 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-32280 | HIGH | stdlib / crypto/x509 | v1.24.6 | 1.25.9, 1.26.2 | GO-2026-4947 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-32281 | HIGH | stdlib / crypto/x509 | v1.24.6 | 1.25.9, 1.26.2 | GO-2026-4946 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-32283 | HIGH | stdlib / crypto/tls | v1.24.6 | 1.25.9, 1.26.2 | GO-2026-4870 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-33811 | HIGH | stdlib / net | v1.24.6 | 1.25.10, 1.26.3 | GO-2026-4981 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-33814 | HIGH | stdlib / net/http/internal/http2 | v1.24.6 | 1.25.10, 1.26.3 | GO-2026-4918 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-33818 | HIGH | stdlib / encoding/asn1 | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | GO-2026-5972 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-39820 | HIGH | stdlib / net/mail | v1.24.6 | 1.25.10, 1.26.3 | GO-2026-4986 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-39821 | HIGH | stdlib / x/net/idna | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | GO-2026-5026 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-39822 | HIGH | stdlib / os | v1.24.6 | 1.25.12, 1.26.5, 1.27.0-rc.2 | GO-2026-4970 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-39836 | HIGH | stdlib / net | v1.24.6 | 1.25.10, 1.26.3 | GO-2026-4971 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-42499 | HIGH | stdlib / net/mail | v1.24.6 | 1.25.10, 1.26.3 | GO-2026-4977 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-42504 | HIGH | stdlib / mime | v1.24.6 | 1.25.11, 1.26.4 | GO-2026-5038 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-56853 | HIGH | stdlib / net/http | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | GO-2026-6089 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-56858 | HIGH | stdlib / html/template | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | GO-2026-6091 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-56859 | HIGH | stdlib / encoding/xml | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | GO-2026-6088 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-56860 | HIGH | stdlib / net/url | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | GO-2026-6218 | NOT_AFFECTED_REACHABILITY_PROVEN |
| CVE-2026-56862 | HIGH | stdlib / crypto/tls | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | GO-2026-6090 | NOT_AFFECTED_REACHABILITY_PROVEN |

For every row above, the scanner/source is Trivy 0.74.0's `gobinary` scanner
with `DataSource.ID=govulndb`, the canonical Go Vulnerability Database at
`https://pkg.go.dev/vuln/`; the Trivy primary URL is the corresponding Aqua
Vulnerability Database NVD record. The `GO-*` value is the exact Go advisory
mapping extracted from that row's Trivy references.

All 22 records have Trivy status `fixed` because fixed Go toolchain versions
are published. This is not a scanner false-positive finding: the old Go
stdlib build metadata is present in the gosu binary. The disposition is based
on the bounded reachability evidence below, not on suppressing the scanner.

### Reachability and actual invocation

- A. Vulnerable code/package presence: Trivy detected the Go stdlib module
  metadata in `/usr/local/bin/gosu`; `go version -m` on the exact upstream
  `gosu-amd64` release reported `go1.24.6`, module `github.com/tianon/gosu
  v1.19.0`, `github.com/moby/sys/user v0.1.0`, and `golang.org/x/sys v0.1.0`.
  The binary SHA-256 was
  `52c8749d0142edd234e9d6bd5237dff2d81e71f43537e2f4f66f75dd4b243dd0`, matching
  the upstream 1.19 amd64 release asset and the binary in both official image
  variants.
- B. Package/import evidence: each Trivy CVE maps to the GO advisory shown in
  the table. `govulncheck -mode binary` scanned the Go 1.24.6 standard library
  and the three recorded modules; source mode scanned the upstream 1.19 source.
- C. Reachable path: `govulncheck@v1.7.0 -mode binary` reported no symbol
  vulnerabilities. The 22 mapped advisories appeared only in its module/package
  informational results, with no reachable symbol result. Source mode likewise
  reported no vulnerabilities. This is a binary-specific result for Linux
  amd64 gosu 1.19, not a general claim about arbitrary Go programs.
- D. Official entrypoint behavior: the official PostgreSQL entrypoint invokes
  `exec gosu postgres "$BASH_SOURCE" "$@"` only when the container starts as
  root. gosu performs user setup, `exec.LookPath`, and `syscall.Exec`, after
  which gosu is no longer resident. The invoked path does not use TLS,
  HTTP/HTTP2, URL, x509, mail, MIME, template, XML, ASN.1, DNS, or the other
  vulnerable APIs listed above.

The upstream source used for this check is
`https://github.com/tianon/gosu/tree/1.19`, including `main.go` and `go.mod`.
The official entrypoint is
`https://github.com/docker-library/postgres/blob/master/docker-entrypoint.sh`.
Go's documentation describes binary-mode govulncheck as symbol-based and
documents its limitations; those limitations are why this remains a bounded
assessment rather than a blanket waiver.

### Official PostgreSQL 17 candidate comparison

Registry manifest resolution and local amd64 pulls were performed for the
currently supported 17.11 aliases. Equivalent aliases share the same immutable
manifest digest and were scanned once per unique digest.

| Official tag aliases | amd64 image digest | PostgreSQL / base | gosu | Trivy HIGH/CRITICAL result | Compatibility |
|---|---|---|---|---|---|
| `postgres:17`, `17-trixie`, `17.11`, `17.11-trixie` | `sha256:e38411452a464af89e5adadb8d223bf53b898d47d6ef918b2d58c08707350449` | 17.11 / Debian 13.6 | 1.19 / Go 1.24.6 | 80 total: 18 CRITICAL, 62 HIGH; 58 Debian plus 22 gosu | health and migration PASS |
| `postgres:17-bookworm`, `17.11-bookworm` | `sha256:84560e3b9c6874893fc4e2854f5dc3e7c1a37bc9d1dfd7a8c641310ae22ba5ad` | 17.11 / Debian 12.15 | 1.19 / Go 1.24.6 | 74 total: 20 CRITICAL, 54 HIGH; 52 Debian plus 22 gosu | health and migration PASS |
| `postgres:17-alpine`, `17-alpine3.24`, `17.11-alpine`, `17.11-alpine3.24` | `sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73` | 17.11 / Alpine 3.24.1 | 1.19 / Go 1.24.6 | 22 total: 1 CRITICAL, 21 HIGH; 0 Alpine plus 22 gosu | health, migration, and 54 tenant tests PASS |
| `postgres:17-alpine3.23`, `17.11-alpine3.23` | `sha256:9ae4e8f8d0284836a505f0b2e825144e32e20499856e7dc5f7b99e19d10eedd6` | 17.11 / Alpine 3.23.5 | 1.19 / Go 1.24.6 | 22 total: 1 CRITICAL, 21 HIGH; 0 Alpine plus 22 gosu | health and migration PASS |

Changing from Alpine 3.24 to Alpine 3.23 does not change gosu. The Debian
variants are worse under the refreshed database. No currently supported
official PostgreSQL 17 digest with acceptable HIGH/CRITICAL evidence was found;
no older patch was selected and no unofficial/custom database image was used.

### Upstream status and bounded security-owner handoff

Upstream gosu's latest release remains 1.19, released 2025-09-23 and built on
Go 1.24.6. The current official PostgreSQL 17.11 Dockerfiles still set
`GOSU_VERSION 1.19` and verify the downloaded binary's signature. Go fixed
toolchains are available upstream (including Go 1.24.13), and Trivy's fixed
metadata is accurate for the standard-library advisories. No newer gosu release
or upstream-remediated official PostgreSQL 17 image that rebuilds gosu with a
fixed toolchain was available at this review.

This is a security exception handoff, not organizational acceptance. The SG-001
classification is `POSTGRES_IMAGE_GATE_ACCEPTED_RISK_REQUIRED` because the
scanner still reports one CRITICAL and 21 HIGH records on the exact official
digest, even though the bounded binary/entrypoint analysis proves no reachable
vulnerable symbols for the actual gosu use. A security owner must explicitly
accept or reject this exact digest; the repository does not self-authorize that
decision.

Risk assessment for all 22 records above:

- Exploit preconditions: an attacker would need the gosu process to execute the
  corresponding vulnerable API with crafted TLS, URL, certificate, DNS,
  HTTP/2, ASN.1, mail, MIME, OS-root, network, template, XML, or related input.
  The Windows-specific NUL path additionally requires a Windows build. None of
  those inputs or API paths are present in the official Linux amd64 entrypoint
  invocation.
- Actual role: root-startup privilege drop from root to the `postgres` user,
  followed by direct `exec` of the entrypoint/PostgreSQL process. The official
  Dockerfile performs release-signature verification, the binary hash matches
  the upstream asset, and the image contains no setuid or setgid bit on gosu.
- Reachability evidence: exact binary SHA match, `go version -m`, gosu source
  inspection, official entrypoint inspection, and govulncheck source/binary
  scans described above.
- Compensating controls: use only the recorded official digest; keep the
  database private and non-public; do not pass attacker-controlled commands to
  the entrypoint; retain the official signature verification; rerun the exact
  scan before any tag/digest change; and do not suppress these findings.
- Residual risk: the image still contains an old Go stdlib and remains a
  scanner-visible CRITICAL/HIGH supply-chain exception. A future gosu usage,
  entrypoint change, architecture change, image tag drift, or analysis blind
  spot could invalidate the bounded result.
- Re-review/expiration trigger: re-review no later than 2026-09-19 and earlier
  on any newer official PostgreSQL digest, gosu release, Go/Trivy database
  update affecting these advisories, entrypoint or command change, architecture
  change, or movement from private staging to network-exposed deployment.

Required human action: the security owner must record acceptance or rejection
for `postgres:17-alpine` at
`sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73`
and the 22 listed advisories. If rejected, staging remains blocked until an
upstream-remediated official digest is available. No Trivy ignore rule,
manual gosu replacement, or custom PostgreSQL base image was introduced.

### 2026-08-20 explicit security-owner decision

At `2026-08-20T10:18:43+01:00`, the security owner explicitly accepted the
bounded residual risk for controlled/private staging use of the exact official
image `postgres:17-alpine` at immutable digest
`sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73`,
Linux amd64 only. The decision relies on the evidence above: the 22 Trivy
HIGH/CRITICAL records remain visible in gosu 1.19's embedded Go standard
library, while source/binary govulncheck and official-entrypoint analysis found
no reachable vulnerable symbols in the deployed gosu invocation.

This is an explicit bounded risk acceptance, not a CVE waiver and not an
authorization to suppress Trivy findings. Scope is limited to controlled
private staging, this exact digest and architecture, the current official
PostgreSQL entrypoint, and no public-production authorization. Re-review is
required no later than `2026-09-19`, or immediately on any PostgreSQL digest,
gosu build/version, Go toolchain, architecture, entrypoint/invocation path,
scanner/advisory evidence, network/exposure-model, or upstream-remediation
change.

The SG-001 gate is therefore set to `ACCEPTED_BOUNDED_RISK`. The findings,
reachability dispositions, risk controls, and upstream remediation watch remain
unchanged; no image replacement, manual gosu replacement, or scanner
suppression was performed.

## 2026-08-20 SG-002 malware-scanner security evidence

This addendum records the targeted SG-002 malware-scanning gate. It does not
change the SG-001 PostgreSQL findings or waive any vulnerability.

### Scanner image and vulnerability scan

- Provider: official `clamav/clamav` image, version `1.4.6`, Compose reference
  `clamav/clamav:1.4.6@sha256:c3bfbf2a2c9abc1fc179e63832a9e8bfac901ede83853e3fa10acf6f1fb5c803`.
- Architecture: Linux amd64. Local image ID and immutable reference both
  resolved to `sha256:c3bfbf2a2c9abc1fc179e63832a9e8bfac901ede83853e3fa10acf6f1fb5c803`.
  Trivy identified Alpine `3.24.1`.
- Runtime version: `ClamAV 1.4.6`; the live `zVERSION` adapter response
  reported signature database `28098` after the disposable service refreshed
  its database. The service healthcheck is the official `clamdcheck.sh` and
  was healthy.
- Compose isolation: private service-network exposure only (`3310` exposed
  to the Compose network, no host port), named disposable signature volume,
  `2g` memory limit, and `2.0` CPU limit. No host antivirus, firewall, or
  Docker project outside Research Tool was changed.
- Scanner: Trivy `0.74.0` from immutable image digest
  `sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969`.
  Vulnerability DB `UpdatedAt=2026-08-20T00:55:38.477267043Z`,
  `DownloadedAt=2026-08-20T05:08:45.429790275Z`.
- Exact command target: `clamav/clamav@sha256:c3bfbf2a2c9abc1fc179e63832a9e8bfac901ede83853e3fa10acf6f1fb5c803`,
  scanners `vuln`, severity `HIGH,CRITICAL`, JSON output. Result: zero HIGH
  and zero CRITICAL findings. No scanner suppression or `ignore-unfixed` was
  used.

### Provider-neutral boundary and ordering

The repository-owned `MalwareScanner` protocol exposes only health and a
structured result with `CLEAN`, `INFECTED`, `ERROR`, `TIMEOUT`, and
`UNAVAILABLE`. The ClamAV TCP transport is isolated in the malware adapter;
document services do not consume ClamAV response strings. Detection names and
error messages are bounded and sanitized. No raw uploaded document or malware
payload is logged or persisted.

Upload writes the verified original bytes under the opaque document key and
creates `MALWARE_SCAN_PENDING`. Processing re-verifies the exact stored hash
and size, checks for an exact prior clean result, and only then invokes the
parser. A scan attempt is persisted before any result-driven transition.
`INFECTED` becomes `MALWARE_INFECTED`; operational failures become
`MALWARE_SCAN_FAILED`; neither creates a processing run or canonical block.
Only `CLEAN` permits `MALWARE_CLEAN`, parser execution, canonical blocks, and
scientific provenance. Scan attempts are append-only and separate from parser
runs, scientific provenance, and acquisition evidence. Changed/corrupt bytes
fail storage-integrity verification before scan eligibility and cannot reuse a
prior clean result.

### Test evidence

- `tests/unit/test_malware.py`: ClamAV protocol clean/infected parsing,
  unavailable endpoint, bounded timeout, scanner error, and deterministic
  test-provider outcomes: PASS.
- `tests/integration/test_documents.py`: clean metadata, EICAR-equivalent
  fixture detection path, parser/canonical-write blocking, unavailable/
  timeout/error fail-closed states, three-attempt retry bound, content-hash
  integrity, tenant isolation, manager-only diagnostics, restricted content,
  and redaction assertions: PASS.
- `tests/integration/test_migrations.py`: SQLite upgrade/downgrade through
  `20260820_0037`: PASS. Live Compose migration reached `20260820_0037 (head)`.
- `tests/api/test_health.py` and `tests/unit/test_health_service.py`: scanner
  readiness behavior: PASS. `GET /health/ready` on the Compose stack returned
  HTTP 200 with database and malware scanner both `up`.
- Live adapter clean scan against the Compose ClamAV service returned
  `CLEAN`, ClamAV `1.4.6`, signature DB `28098`.
- Live standard EICAR test content generated only in one-off container memory
  returned `INFECTED` / `Eicar-Test-Signature`. No EICAR file or repository
  artifact was created or committed.
- Ruff, Ruff format check, mypy (`backend workers`), compileall, Compose config,
  `git diff --check`, and the pinned ClamAV Trivy scan: PASS.

AUTHORITATIVE SG-002 CLASSIFICATION: `MALWARE_SCANNER_GATE_PASS`
