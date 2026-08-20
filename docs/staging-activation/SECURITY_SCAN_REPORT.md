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
