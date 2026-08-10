# ADR-010: Make Deduplication Reviewable and Non-Destructive

- Status: Accepted
- Date: 2026-08-10

## Context

Automatic merging can erase citation-source differences, distort flow counts, and make false-positive duplicate decisions difficult to reverse. Fuzzy matching is especially unsuitable as an irreversible write.

## Decision

Run a deterministic, versioned candidate generator over a hashed Article snapshot. Match exact normalized DOI, then exact PMID, then normalized title/year, then high-threshold title similarity. Persist immutable candidate pairs with reason and score.

Humans append one final confirm/reject decision per candidate. Confirmation identifies which member of the pair is retained, but never deletes, overwrites, or merges either Article or its source records. Downstream queues suppress only the non-retained member while preserving all history.

## Consequences

- Replaying the same algorithm and Article snapshot returns the same run.
- Algorithm upgrades create new runs rather than modifying old candidates.
- System-generated candidates and human decisions have separate provenance.
- Transitive cluster derivation is deferred until downstream queue construction needs it.
