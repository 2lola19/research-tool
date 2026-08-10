# ADR-013: Canonical document processing and GROBID adapter boundary

## Status

Accepted

## Context

Full-text PDFs are source artifacts, not normalized scientific evidence. The
platform preserves original bytes and checksums while allowing parser output
to evolve independently of Article and Study records.

GROBID is a strong candidate for scholarly PDF parsing. The official project
converts scholarly documents to structured TEI/XML and exposes service
interfaces. It is distributed under Apache-2.0. References:

- https://github.com/grobidOrg/grobid
- https://grobid.readthedocs.io/en/latest/getting_started/
- https://github.com/grobidOrg/grobid/blob/master/doc/Frequently-asked-questions.md

## Decision

Keep the application boundary as:

```text
PDF -> parser provider -> canonical document model -> document blocks/evidence locations
```

`DocumentParser` is the application protocol. `GrobidTeiParser` adapts
representative TEI/XML fixtures into the canonical model without exposing TEI
types to domain services. `FixtureDocumentParser` provides deterministic local
tests and development behavior while live PDF parsing is deferred.

The original PDF is stored under an opaque tenant/review/article key in the
object-storage abstraction. Parsed blocks and future normalized outputs are
separate records and never overwrite the source bytes.

## GROBID evaluation

- Input: scholarly PDF bytes.
- Output: TEI/XML containing bibliographic metadata, sections, paragraphs,
  references, and other parser-supported structures.
- Integration: isolated service boundary, then a local adapter; no GROBID SDK
  types or TEI schema become application-domain contracts.
- Operations: official Docker images bundle models and runtime resources; the
  full image is intended for better accuracy but requires more local resources.
  Live execution is not required because Docker is environment-blocked.
- Strengths: scholarly-document focus, structured TEI output, service boundary,
  and an established adapter ecosystem.
- Limitations: parser/model changes can alter normalization; PDFs may be
  malformed, scanned, or structurally ambiguous; coordinates are optional.
- Fallback: retain the original file, mark processing failure with the parser
  error, and keep manual evidence locations available when possible.

## Consequences

- Document provenance retains source, actor, checksum, parser, and processing
  run information.
- Parser upgrades require a new parser version and explicit reprocessing
  policy; historical source files are not rewritten.
- Full GROBID deployment and PostgreSQL-specific execution remain deferred
  until the environment blocker is removed.
