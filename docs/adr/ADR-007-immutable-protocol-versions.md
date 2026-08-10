# ADR-007: Model Protocol Revisions as Immutable Versions

- Status: Accepted
- Date: 2026-08-10

## Context

An approved systematic-review protocol is a consequential scientific record. Editing it in place would make later search, screening, and analysis decisions impossible to reconstruct. Marking an older approved row as superseded would itself rewrite approved history.

## Decision

Store every protocol revision as a new immutable `ProtocolVersion` with a review-local monotonic version and a SHA-256 hash of canonical structured content. Store approval or rejection as one separate append-only `ProtocolDecision` per version.

A version without a decision is pending. A rejected version remains historical and a correction creates a new version. More than one historical version may be approved; the current approved protocol is derived as the highest approved version rather than by mutating earlier approvals.

Protocol creation and decisions are restricted to review controllers. Approval and rejection append both audit and scientific-provenance records in the same request transaction.

## Consequences

- Approved content, decisions, and hashes cannot be edited or deleted through ORM operations.
- Downstream domains can pin the exact protocol version and hash they followed.
- Revisions consume additional rows but preserve scientific history.
- Concurrent version creation relies on a database uniqueness constraint and may be retried by a future orchestration command.
