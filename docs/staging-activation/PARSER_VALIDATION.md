# GROBID and Document Parser Validation

Status: ENVIRONMENT_BLOCKED

## Local evidence

The focused parser suite passed. It exercised the deterministic fixture PDF
marker, representative GROBID TEI normalization, title/abstract/body blocks,
malformed and empty TEI rejection, parser limits, and deterministic chunk
manifest hashing. The document integration suite also passed using the local
FixtureDocumentParser and verified document upload, structure preservation,
authorization, duplicate rejection, corruption repair, and retry behavior.

The repository contains the provider-neutral DocumentParser boundary and
GrobidTeiParser, but no live GROBID container and no non-sensitive PDF fixture
file in the checkout. The GROBID_URL example is configuration only. No OCR,
figure extraction, or parser feature was added.

## Required external evidence

Supply a disposable GROBID endpoint or image and a representative
non-sensitive scholarly PDF. Rerun health and parser version identity, bounded
timeout, title/abstract/body extraction, page/section/block reconstruction,
processing-run metadata, chunk manifests, content hashes, retry and unavailable
behavior, and evidence reconstruction. Store only hashes and bounded metadata;
do not commit the PDF or parser output.
