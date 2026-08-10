# ADR-011: Persist Blinded Screening as Immutable Decisions and Derived Outcomes

- Status: Accepted
- Date: 2026-08-10

## Context

Independent title/abstract and full-text screening must prevent one reviewer from being influenced by another, preserve every consequential judgment, resolve disagreement explicitly, and remain reconstructable after a protocol or workflow changes. A mutable status field on an Article cannot represent reviewer independence, conflicts, or adjudication history safely.

## Decision

Model screening as tenant- and review-scoped rounds. A round declares its stage, sequence, blinding policy, and required independent decision count. Assignments bind one Article to one active, authorized reviewer. Each assignment accepts one immutable include/exclude decision; exclusions require a reason.

Before a reviewer decides, their queue exposes neither other reviewers' decisions nor a derived outcome. Once the required decisions exist, a deterministic consensus function appends an include, exclude, or conflict outcome. Conflicts require one immutable human adjudication before a round can close.

Progression from a closed title/abstract round to a later open full-text round is an idempotent, append-only record derived only from consensus includes or adjudicated includes. Confirmed duplicate relationships identify one retained Article; only the suppressed Article is excluded from assignment. Decisions, outcomes, adjudications, closures, and progressions are linked to provenance or audit history.

## Consequences

- Tenant/review composite foreign keys prevent identifiers from crossing ownership boundaries.
- Reviewer queues remain blinded while a decision is pending; manager outcome views do not disclose individual decisions.
- The current foundation accepts blinded rounds only. Unblinded rounds are rejected until a separate explicit reveal policy is modeled, so a stored configuration cannot silently weaken confidentiality.
- Decisions and adjudications are final. Corrections require a future superseding-round design rather than history mutation.
- Round closure fails while assigned Articles lack outcomes or conflicts lack adjudication.
- Screening progression is reproducible and cannot silently add excluded or suppressed duplicate Articles.
